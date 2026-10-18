"""SeeGuide Hazard Estimator
Evaluates corridor path obstruction and impending collisions by combining
fast-tier edge density with tracked object locations, zones, and looming growth rates.
"""

from typing import Any, Dict, List, Tuple


def estimate_hazard(
    fast_metrics: Dict[str, Any],
    tracked_objects: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calculates corridor blockage score and detects looming obstacles.

    Args:
        fast_metrics: Output from fast-tier containing quality, motion, corridor.
        tracked_objects: Output from tracker containing cls, conf, bbox, growth, zone.

    Returns:
        Dictionary with updated corridor metrics, hazard flag, and diagnostic reason.
    """
    edge_density = fast_metrics.get("corridor", {}).get("edge_density", 0.0)

    # Heuristic base obstruction from high-frequency edge complexity in walking path
    base_blocked = min(1.0, edge_density * 1.5)

    looming_hazard = False
    hazard_reason = None
    max_object_threat = 0.0

    for obj in tracked_objects:
        zone = obj.get("zone", "center")
        growth = obj.get("growth", 1.0)
        conf = obj.get("conf", 0.5)
        cls_name = obj.get("cls", "obstacle")

        # Looming hazard: expanding obstacle in the center walking corridor
        if zone == "center":
            threat = 0.3 * conf
            if growth >= 1.25:
                looming_hazard = True
                threat += 0.5 * (growth - 1.0)
                hazard_reason = f"approaching_{cls_name}_in_corridor"
            elif growth >= 1.10:
                threat += 0.25
            max_object_threat = max(max_object_threat, threat)
        elif zone in ("left", "right") and growth >= 1.4:
            # High lateral approach
            max_object_threat = max(max_object_threat, 0.2)

    total_blocked_score = min(1.0, max(base_blocked, max_object_threat))
    if looming_hazard:
        total_blocked_score = max(total_blocked_score, 0.75)

    total_blocked_score = round(float(total_blocked_score), 2)

    # Update corridor blocked score in fast_metrics
    if "corridor" in fast_metrics:
        fast_metrics["corridor"]["blocked_score"] = total_blocked_score

    return {
        "blocked_score": total_blocked_score,
        "looming_hazard": looming_hazard,
        "hazard_reason": hazard_reason,
    }
