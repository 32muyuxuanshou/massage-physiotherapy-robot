"""Deterministic triangle/triangle narrow-phase metrics.

The routines are independent of Blender so their predicates can be tested with
small synthetic fixtures.  They intentionally report geometric proxies rather
than claiming physical soft-tissue penetration depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np


@dataclass(frozen=True)
class PairResult:
    classification: str
    confirmed_overlap: bool
    contact_only: bool
    points: tuple[tuple[float, float, float], ...]
    segment_length_m: float
    coplanar_area_m2: float
    crossing_depth_proxy_a_m: float
    crossing_depth_proxy_b_m: float
    normal_angle_deg: float

    def as_dict(self) -> dict:
        return {
            "classification": self.classification,
            "confirmed_overlap": self.confirmed_overlap,
            "contact_only": self.contact_only,
            "intersection_points_world_m": [list(point) for point in self.points],
            "intersection_segment_length_m": self.segment_length_m,
            "coplanar_intersection_area_m2": self.coplanar_area_m2,
            "crossing_depth_proxy_a_m": self.crossing_depth_proxy_a_m,
            "crossing_depth_proxy_b_m": self.crossing_depth_proxy_b_m,
            "normal_angle_deg": self.normal_angle_deg,
        }


def _normal(triangle: np.ndarray) -> tuple[np.ndarray, float]:
    raw = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
    length = float(np.linalg.norm(raw))
    return (raw / length if length > 0.0 else raw), length


def _unique(points: list[np.ndarray], tolerance: float) -> list[np.ndarray]:
    unique: list[np.ndarray] = []
    for point in points:
        if not any(float(np.linalg.norm(point - existing)) <= tolerance for existing in unique):
            unique.append(point)
    return unique


def _point_in_triangle(point: np.ndarray, triangle: np.ndarray, tolerance: float) -> bool:
    v0 = triangle[1] - triangle[0]
    v1 = triangle[2] - triangle[0]
    v2 = point - triangle[0]
    dot00 = float(np.dot(v0, v0))
    dot01 = float(np.dot(v0, v1))
    dot11 = float(np.dot(v1, v1))
    dot20 = float(np.dot(v2, v0))
    dot21 = float(np.dot(v2, v1))
    denominator = dot00 * dot11 - dot01 * dot01
    if abs(denominator) <= 1e-24:
        return False
    u = (dot11 * dot20 - dot01 * dot21) / denominator
    v = (dot00 * dot21 - dot01 * dot20) / denominator
    bary_tolerance = max(1e-9, tolerance / max(np.sqrt(dot00), np.sqrt(dot11), 1e-12))
    return u >= -bary_tolerance and v >= -bary_tolerance and u + v <= 1.0 + bary_tolerance


def _edge_plane_points(
    triangle: np.ndarray,
    signed: np.ndarray,
    other: np.ndarray,
    tolerance: float,
) -> list[np.ndarray]:
    points: list[np.ndarray] = []
    for first, second in ((0, 1), (1, 2), (2, 0)):
        a, b = triangle[first], triangle[second]
        da, db = float(signed[first]), float(signed[second])
        if abs(da) <= tolerance and _point_in_triangle(a, other, tolerance):
            points.append(a)
        if abs(db) <= tolerance and _point_in_triangle(b, other, tolerance):
            points.append(b)
        if (da < -tolerance and db > tolerance) or (da > tolerance and db < -tolerance):
            factor = da / (da - db)
            point = a + factor * (b - a)
            if _point_in_triangle(point, other, tolerance):
                points.append(point)
    return points


def _polygon_area_2d(polygon: list[np.ndarray]) -> float:
    if len(polygon) < 3:
        return 0.0
    return abs(sum(
        float(polygon[index][0] * polygon[(index + 1) % len(polygon)][1]
              - polygon[(index + 1) % len(polygon)][0] * polygon[index][1])
        for index in range(len(polygon))
    )) * 0.5


def _orientation_2d(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _line_intersection_2d(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    direction_p = p2 - p1
    direction_q = q2 - q1
    denominator = float(direction_p[0] * direction_q[1] - direction_p[1] * direction_q[0])
    if abs(denominator) <= 1e-20:
        return (p1 + p2) * 0.5
    offset = q1 - p1
    factor = float(offset[0] * direction_q[1] - offset[1] * direction_q[0]) / denominator
    return p1 + factor * direction_p


def _clip_convex(subject: list[np.ndarray], clip_triangle: np.ndarray, tolerance: float) -> list[np.ndarray]:
    output = list(subject)
    clip_orientation = _orientation_2d(clip_triangle[0], clip_triangle[1], clip_triangle[2])
    sign = 1.0 if clip_orientation >= 0.0 else -1.0
    for index in range(3):
        clip_a = clip_triangle[index]
        clip_b = clip_triangle[(index + 1) % 3]
        input_polygon = output
        output = []
        if not input_polygon:
            break
        previous = input_polygon[-1]
        previous_inside = sign * _orientation_2d(clip_a, clip_b, previous) >= -tolerance
        for current in input_polygon:
            current_inside = sign * _orientation_2d(clip_a, clip_b, current) >= -tolerance
            if current_inside != previous_inside:
                output.append(_line_intersection_2d(previous, current, clip_a, clip_b))
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
    return output


def _restore_3d(point_2d: np.ndarray, dropped_axis: int, plane_point: np.ndarray, normal: np.ndarray) -> np.ndarray:
    point = np.zeros(3, dtype=np.float64)
    kept = [axis for axis in range(3) if axis != dropped_axis]
    point[kept] = point_2d
    numerator = float(np.dot(normal, plane_point) - sum(normal[axis] * point[axis] for axis in kept))
    point[dropped_axis] = numerator / normal[dropped_axis]
    return point


def _depth_proxy(signed: np.ndarray, tolerance: float) -> float:
    minimum, maximum = float(np.min(signed)), float(np.max(signed))
    if minimum < -tolerance and maximum > tolerance:
        return min(-minimum, maximum)
    return 0.0


def _max_distance(points: list[np.ndarray]) -> float:
    return max((float(np.linalg.norm(first - second)) for first, second in combinations(points, 2)), default=0.0)


def analyze_triangle_pair(triangle_a, triangle_b, tolerance: float = 1e-7) -> PairResult:
    a = np.asarray(triangle_a, dtype=np.float64)
    b = np.asarray(triangle_b, dtype=np.float64)
    normal_a, length_a = _normal(a)
    normal_b, length_b = _normal(b)
    if length_a <= 1e-15 or length_b <= 1e-15:
        return PairResult("DEGENERATE", False, False, (), 0.0, 0.0, 0.0, 0.0, 0.0)

    signed_a_to_b = (a - b[0]) @ normal_b
    signed_b_to_a = (b - a[0]) @ normal_a
    angle = float(np.degrees(np.arccos(np.clip(abs(float(np.dot(normal_a, normal_b))), -1.0, 1.0))))
    depth_a = _depth_proxy(signed_a_to_b, tolerance)
    depth_b = _depth_proxy(signed_b_to_a, tolerance)

    if (np.all(signed_a_to_b > tolerance) or np.all(signed_a_to_b < -tolerance)
            or np.all(signed_b_to_a > tolerance) or np.all(signed_b_to_a < -tolerance)):
        return PairResult("SEPARATED", False, False, (), 0.0, 0.0, depth_a, depth_b, angle)

    parallel = float(np.linalg.norm(np.cross(normal_a, normal_b))) <= 1e-8
    if parallel:
        if max(float(np.max(np.abs(signed_a_to_b))), float(np.max(np.abs(signed_b_to_a)))) > tolerance:
            return PairResult("PARALLEL_SEPARATED", False, False, (), 0.0, 0.0, depth_a, depth_b, angle)
        dropped = int(np.argmax(np.abs(normal_a)))
        kept = [axis for axis in range(3) if axis != dropped]
        projected_a = a[:, kept]
        projected_b = b[:, kept]
        polygon = _clip_convex([point.copy() for point in projected_a], projected_b, tolerance)
        polygon = _unique(polygon, tolerance)
        projected_area = _polygon_area_2d(polygon)
        area = projected_area / max(abs(float(normal_a[dropped])), 1e-12)
        points_3d = [_restore_3d(point, dropped, a[0], normal_a) for point in polygon]
        segment = _max_distance(points_3d)
        area_threshold = max(tolerance * tolerance * 4.0, 1e-14)
        confirmed = area > area_threshold
        contact = not confirmed and bool(points_3d)
        classification = "COPLANAR_AREA" if confirmed else "COPLANAR_CONTACT" if contact else "COPLANAR_DISJOINT"
        return PairResult(
            classification, confirmed, contact,
            tuple(tuple(float(value) for value in point) for point in points_3d),
            segment, area, depth_a, depth_b, angle,
        )

    points = _edge_plane_points(a, signed_a_to_b, b, tolerance)
    points.extend(_edge_plane_points(b, signed_b_to_a, a, tolerance))
    points = _unique(points, tolerance * 4.0)
    segment = _max_distance(points)
    confirmed = len(points) >= 2 and segment > tolerance * 4.0
    contact = bool(points) and not confirmed
    classification = "NONCOPLANAR_SEGMENT" if confirmed else "POINT_CONTACT" if contact else "NO_EXACT_INTERSECTION"
    if len(points) > 2:
        first, second = max(combinations(points, 2), key=lambda pair: float(np.linalg.norm(pair[0] - pair[1])))
        points = [first, second]
    return PairResult(
        classification, confirmed, contact,
        tuple(tuple(float(value) for value in point) for point in points),
        segment, 0.0, depth_a, depth_b, angle,
    )

