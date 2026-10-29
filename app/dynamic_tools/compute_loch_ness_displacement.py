from typing import Any

def compute_loch_ness_displacement(
    human_count: int = 8100000000,
    avg_human_mass_kg: float = 62.0,
    human_density_kg_m3: float = 985.0,
    loch_ness_volume_m3: float = 7450000000.0,
    loch_ness_surface_area_m2: float = 56400000.0,
) -> dict[str, Any]:
    """Computes human volumetric displacement and water-level rise inside Loch Ness.

    Args:
        human_count: Total number of people submerged.
        avg_human_mass_kg: Average mass per human in kilograms.
        human_density_kg_m3: Average human body density in kg/m^3.
        loch_ness_volume_m3: Volume of Loch Ness in cubic meters (~7.45e9 m^3).
        loch_ness_surface_area_m2: Surface area of Loch Ness in square meters (~5.64e7 m^2).

    Returns:
        Dictionary with total human volume, % of Loch Ness filled, and water level rise in meters.
    """
    per_human_m3 = float(avg_human_mass_kg) / float(human_density_kg_m3)
    total_human_m3 = float(human_count) * per_human_m3
    pct_filled = (total_human_m3 / float(loch_ness_volume_m3)) * 100.0
    water_rise_m = total_human_m3 / float(loch_ness_surface_area_m2)
    return {
        "human_count": int(human_count),
        "per_human_volume_m3": round(per_human_m3, 6),
        "total_human_volume_m3": round(total_human_m3, 2),
        "loch_ness_volume_m3": float(loch_ness_volume_m3),
        "percent_of_loch_filled": round(pct_filled, 4),
        "water_level_rise_m": round(water_rise_m, 4),
        "fits_entire_humanity": total_human_m3 < float(loch_ness_volume_m3),
    }
