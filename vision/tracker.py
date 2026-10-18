"""SeeGuide Obstacle Tracker
Tracks detected bounding boxes across video frames using IoU association,
calculating bounding box growth rate (looming) and horizontal zone assignment.
"""

from typing import Any, Dict, List, Optional, Tuple


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])

    inter_w = max(0.0, x_b - x_a)
    inter_h = max(0.0, y_b - y_a)
    inter_area = inter_w * inter_h

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def compute_bbox_area(bbox: List[float]) -> float:
    """Computes the area of bounding box [x1, y1, x2, y2]."""
    w = max(0.0, bbox[2] - bbox[0])
    h = max(0.0, bbox[3] - bbox[1])
    return w * h


def get_horizontal_zone(bbox: List[float], frame_width: int) -> str:
    """Classifies bounding box center into left, center, or right corridor zone."""
    if frame_width <= 0:
        return "center"
    center_x = (bbox[0] + bbox[2]) / 2.0
    norm_x = center_x / float(frame_width)
    if norm_x < 0.33:
        return "left"
    elif norm_x > 0.67:
        return "right"
    return "center"


class TrackedItem:
    """Internal representation of an active tracked obstacle."""

    def __init__(self, track_id: int, cls: str, conf: float, bbox: List[float]):
        self.track_id: int = track_id
        self.cls: str = cls
        self.conf: float = conf
        self.bbox: List[float] = bbox
        self.prev_area: float = compute_bbox_area(bbox)
        self.growth: float = 1.0
        self.age: int = 1


class Tracker:
    """IoU-based object tracker computing inter-frame bounding box growth."""

    def __init__(self, iou_threshold: float = 0.3):
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, TrackedItem] = {}
        self.next_id: int = 1

    def update(
        self,
        detections: List[Dict[str, Any]],
        frame_width: int,
        frame_height: int,
    ) -> List[Dict[str, Any]]:
        """Updates tracks with new detections and calculates growth and corridor zone.

        Args:
            detections: List of detections with keys: cls, conf, bbox.
            frame_width: Frame pixel width.
            frame_height: Frame pixel height.

        Returns:
            List of tracked items conforming to DetectedObject schema.
        """
        updated_tracks: Dict[int, TrackedItem] = {}
        unmatched_detections = list(range(len(detections)))
        matched_track_ids = set()

        # Match detections to existing tracks via IoU
        for d_idx in list(unmatched_detections):
            det = detections[d_idx]
            best_iou = 0.0
            best_track_id = None

            for t_id, track in self.tracks.items():
                if t_id in matched_track_ids:
                    continue
                if track.cls != det["cls"]:
                    continue

                iou = compute_iou(track.bbox, det["bbox"])
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_track_id = t_id

            if best_track_id is not None:
                curr_area = compute_bbox_area(det["bbox"])
                prev_area = self.tracks[best_track_id].prev_area
                growth = (curr_area / prev_area) if prev_area > 0 else 1.0

                track = self.tracks[best_track_id]
                track.bbox = det["bbox"]
                track.conf = det["conf"]
                track.prev_area = curr_area
                track.growth = round(growth, 2)
                track.age += 1

                updated_tracks[best_track_id] = track
                matched_track_ids.add(best_track_id)
                unmatched_detections.remove(d_idx)

        # Create new tracks for unmatched detections
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            track_id = self.next_id
            self.next_id += 1

            new_track = TrackedItem(
                track_id=track_id,
                cls=det["cls"],
                conf=det["conf"],
                bbox=det["bbox"],
            )
            updated_tracks[track_id] = new_track

        self.tracks = updated_tracks

        # Assemble output matching DetectedObject schema
        results = []
        for track in self.tracks.values():
            zone = get_horizontal_zone(track.bbox, frame_width)
            results.append({
                "cls": track.cls,
                "conf": round(track.conf, 2),
                "bbox": [round(c, 1) for c in track.bbox],
                "growth": round(track.growth, 2),
                "zone": zone,
            })

        return results

    def reset(self) -> None:
        """Resets active tracker state."""
        self.tracks.clear()
        self.next_id = 1
