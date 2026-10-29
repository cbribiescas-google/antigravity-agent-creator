# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Serve the reasoning_engine ``{class_method, input}`` contract over HTTP.

Exists to guarantee support for the Vertex AI Console Playground and Gemini
Enterprise (via ADK registration), which both invoke the engine through this
contract. Agent Engine forwards calls to ``/api/reasoning_engine`` (sync) and
``/api/stream_reasoning_engine`` (streaming); dispatch is limited to the
:class:`AdkApp` ``register_operations()`` methods so the wire output matches a
packaged Agent Engine.
"""

import inspect
import json
import logging
from typing import Any

from agentplatform.agent_engines.templates.adk import AdkApp
from fastapi import FastAPI, HTTPException, Request, encoders, responses
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.app_utils import services
from app.telemetry import incoming_ge_session_id_var

logger = logging.getLogger(__name__)


def _no_op_instrumentor_builder(project_id: str) -> None:
    """No-op so set_up() keeps the startup instrumentor and generate_content spans."""
    return None


async def _align_ge_session_in_kwargs(
    class_method: str, kwargs: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """Ensures every Gemini Enterprise App conversation keeps a stable session_id across turns.

    In `AdkApp.streaming_agent_run_with_events`, when Turn 1 arrives with no
    `session_id`, `AdkApp` defaults to creating a temporary `in_memory_session_service`
    session, returning its ID to Gemini Enterprise, and deleting it in `finally:`.
    On Turn 2, Gemini Enterprise sends that Turn-1 `session_id` back, which is
    missing from `VertexAiSessionService` and causes `AdkApp` to mint a new ID.

    Pre-creating the session in `services.get_session_service()` on Turn 1 and
    capturing the incoming `session_id` (or `ge_conversation_id` from replayed
    events) guarantees 1-to-1 alignment between a GE App conversation and the
    Antigravity conversation across all turns.
    """
    kwargs = dict(kwargs)
    if class_method == "streaming_agent_run_with_events" and isinstance(
        kwargs.get("request_json"), str
    ):
        try:
            req_data = json.loads(kwargs["request_json"])
            session_id = req_data.get("session_id") or req_data.get("sessionId")
            user_id = (
                req_data.get("user_id")
                or req_data.get("userId")
                or "default_user"
            )

            # Check replayed events for an established ge_conversation_id
            for ev in req_data.get("events") or []:
                if isinstance(ev, dict):
                    cm = ev.get("custom_metadata") or ev.get("customMetadata") or {}
                    if isinstance(cm, dict) and cm.get("ge_conversation_id"):
                        session_id = cm["ge_conversation_id"]
                        break

            # On Turn 1 (no session_id yet), pre-create a persistent session in
            # the shared session service so AdkApp does not use & delete an
            # ephemeral in-memory session.
            if not session_id:
                session_svc = services.get_session_service()
                created = await session_svc.create_session(
                    app_name="app",
                    user_id=user_id,
                )
                session_id = created.id
                req_data["session_id"] = session_id
                kwargs["request_json"] = json.dumps(req_data)

            return kwargs, str(session_id)
        except Exception as exc:
            logger.warning("Failed to align GE session in request_json: %s", exc)
            return kwargs, None

    session_id = kwargs.get("session_id")
    return kwargs, str(session_id) if session_id else None


def attach_reasoning_engine_routes(app: FastAPI) -> None:
    """Register reasoning_engine routes that dispatch to an AdkApp."""
    runtime: AdkApp | None = None
    streaming_methods: set[str] = set()
    sync_methods: set[str] = set()

    def get_runtime() -> AdkApp:
        nonlocal runtime, streaming_methods, sync_methods
        if runtime is None:
            from app.agent import app as adk_app

            # Reuse the process-wide services so sessions created here are
            # visible to the adk_api and A2A paths, and vice versa (see services.py).
            runtime = AdkApp(
                app=adk_app,
                session_service_builder=services.get_session_service,
                artifact_service_builder=services.get_artifact_service,
                instrumentor_builder=_no_op_instrumentor_builder,
            )
            runtime.set_up()
            operations = runtime.register_operations()
            streaming_methods = set(operations.get("stream", [])) | set(
                operations.get("async_stream", [])
            )
            sync_methods = set(operations.get("", [])) | set(
                operations.get("async", [])
            )
        return runtime

    def resolve_method(class_method: str, *, streaming: bool):
        rt = get_runtime()
        allowed = streaming_methods if streaming else sync_methods
        if class_method not in allowed:
            raise HTTPException(
                status_code=404,
                detail=f"Unsupported reasoning_engine method: {class_method!r}",
            )
        return getattr(rt, class_method)

    @app.post("/api/stream_reasoning_engine")
    async def stream_query(request: Request) -> responses.StreamingResponse:
        body = await request.json()
        class_method = body["class_method"]
        method = resolve_method(class_method, streaming=True)
        raw_kwargs = body.get("input") or {}
        kwargs, aligned_ge_session_id = await _align_ge_session_in_kwargs(
            class_method, raw_kwargs
        )
        incoming_ge_session_id_var.set(aligned_ge_session_id)
        stream = (
            await method(**kwargs)
            if inspect.iscoroutinefunction(method)
            else method(**kwargs)
        )

        async def generator():
            token = incoming_ge_session_id_var.set(aligned_ge_session_id)
            try:
                if hasattr(stream, "__aiter__"):
                    async for event in stream:
                        if (
                            aligned_ge_session_id
                            and isinstance(event, dict)
                            and "session_id" in event
                        ):
                            event["session_id"] = aligned_ge_session_id
                        yield json.dumps(encoders.jsonable_encoder(event)) + "\n"
                else:
                    async for event in iterate_in_threadpool(stream):
                        if (
                            aligned_ge_session_id
                            and isinstance(event, dict)
                            and "session_id" in event
                        ):
                            event["session_id"] = aligned_ge_session_id
                        yield json.dumps(encoders.jsonable_encoder(event)) + "\n"
            finally:
                try:
                    incoming_ge_session_id_var.reset(token)
                except ValueError:
                    incoming_ge_session_id_var.set(None)

        return responses.StreamingResponse(
            content=generator(), media_type="application/json"
        )

    @app.post("/api/reasoning_engine")
    async def query(request: Request) -> responses.JSONResponse:
        body = await request.json()
        method = resolve_method(body["class_method"], streaming=False)
        kwargs = body.get("input") or {}
        if inspect.iscoroutinefunction(method):
            output = await method(**kwargs)
        else:
            output = await run_in_threadpool(method, **kwargs)
        return responses.JSONResponse(
            content=encoders.jsonable_encoder({"output": output})
        )
