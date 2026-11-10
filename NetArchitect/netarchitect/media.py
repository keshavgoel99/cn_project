"""Assignment's 10 Gb/s distance rules, with explicit optical limits."""

import math
from .errors import PhysicalDistanceViolationError, PlanningError


def select_media(distance_m, requested="auto", fiber_attenuation=None):
    if (type(distance_m) not in (int, float) or not 0 < distance_m <= 40000000
            or not math.isfinite(distance_m)):
        raise PlanningError("Distance must be a finite positive number of metres.")
    if requested not in {"auto", "copper", "om4", "os2"}:
        raise PlanningError("Medium must be auto, copper, om4, or os2.")
    if fiber_attenuation is not None and (type(fiber_attenuation) not in (int, float)
            or not math.isfinite(fiber_attenuation) or not 0.1 <= fiber_attenuation <= 1):
        raise PlanningError("Fibre attenuation must be 0.1-1 dB/km.")
    medium = requested
    if medium == "auto":
        medium = "copper" if distance_m <= 100 else "om4" if distance_m <= 400 else "os2"
    if medium == "copper":
        if distance_m > 100:
            raise PhysicalDistanceViolationError(
                f"Copper run {distance_m:g} m exceeds the 100 m 10GBASE-T channel limit; "
                "attenuation can prevent a reliable link. Use fibre.")
        return {"medium": "Cat6a", "transceiver": "10GBASE-T", "distance_m": distance_m,
                "reason": f"{distance_m:g} m <= 100 m: Cat6a supports the assignment's "
                          "10GBASE-T access channel (IEEE 802.3an). The channel includes patch leads."}
    if medium == "om4":
        if distance_m > 400:
            raise PhysicalDistanceViolationError(
                f"OM4 run {distance_m:g} m exceeds 400 m for 10GBASE-SR.")
        return {"medium": "OM4 MMF", "transceiver": "10GBASE-SR", "wavelength_nm": 850,
                "distance_m": distance_m,
                "reason": f"{distance_m:g} m <= 400 m: OM4 with 850 nm SR optics fits the "
                          "modal-bandwidth reach limit. Modal dispersion, not just attenuation, "
                          "limits multimode reach. Verify the installed channel loss."}
    if distance_m > 40000:
        raise PhysicalDistanceViolationError(
            f"{distance_m:g} m exceeds the supported 40 km ER reach; use a managed WAN "
            "or separately engineered optical transport.")
    optic, wavelength, budget, attenuation = (
        ("10GBASE-LR", 1310, 6.2, 0.4) if distance_m <= 10000
        else ("10GBASE-ER", 1550, 11.1, 0.3))
    if fiber_attenuation is not None:
        attenuation = fiber_attenuation
    # Planning assumptions, not a substitute for an OTDR/power test.
    loss = distance_m / 1000 * attenuation + 2 * 0.5 + 4 * 0.1
    margin = budget - loss
    if margin < 1:
        raise PhysicalDistanceViolationError(
            f"{optic} reach alone is insufficient: estimated loss {loss:.2f} dB, "
            f"budget {budget:.1f} dB leaves {margin:.2f} dB (<1 dB reserve). "
            "Use managed transport or engineer the optical path.")
    return {"medium": "OS2 SMF", "transceiver": optic, "wavelength_nm": wavelength,
            "distance_m": distance_m, "estimated_loss_db": round(loss, 2),
            "budget_db": budget, "margin_db": round(margin, 2),
            "reason": f"OS2 {optic} ({wavelength} nm) chosen for {distance_m:g} m. "
                      f"Estimated loss = {distance_m/1000:g} km x {attenuation} dB/km "
                      f"+ 2 connectors x 0.5 + 4 splices x 0.1 = {loss:.2f} dB; "
                      f"budget {budget} dB leaves {margin:.2f} dB. Minimum reserve is 1 dB. "
                      "Attenuation is a planning input, not a measured result. "
                      "Check actual optics, receiver overload/attenuator needs and measured loss."}
