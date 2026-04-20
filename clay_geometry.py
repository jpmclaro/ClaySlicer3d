from __future__ import annotations

import sys
from pathlib import Path



def _ensure_local_site_packages():
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / '.venv' / 'Lib' / 'site-packages',
        base_dir / 'venv' / 'Lib' / 'site-packages',
    ]
    for candidate in candidates:
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)



_ensure_local_site_packages()

import math
from typing import List, Sequence, Tuple

try:
    from shapely.geometry import (
        LinearRing,
        LineString,
        MultiPolygon,
        Point as ShapelyPoint,
        Polygon,
    )
    from shapely.ops import unary_union
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError('Dependencia Shapely ausente. Instale com `python -m pip install shapely` no ambiente que executa o viewer.') from exc

EPSILON = 1e-9


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance_xy(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def angle_of(point: Tuple[float, float], center: Tuple[float, float]) -> float:
    return math.atan2(point[1] - center[1], point[0] - center[0])


def angular_diff(a: float, b: float) -> float:
    diff = abs(a - b)
    return min(diff, 2.0 * math.pi - diff)


def rotate_points_to_target(points: List[Tuple[float, float]], target: Tuple[float, float]) -> List[Tuple[float, float]]:
    if not points:
        return points
    best_idx = min(range(len(points)), key=lambda i: distance_xy(points[i], target))
    if best_idx == 0:
        return points
    return points[best_idx:] + points[:best_idx]


def rotate_points_to_angle(points: List[Tuple[float, float]], center: Tuple[float, float], target_angle: float) -> List[Tuple[float, float]]:
    if not points:
        return points
    target_angle = math.atan2(math.sin(target_angle), math.cos(target_angle))
    best_idx = min(
        range(len(points)),
        key=lambda i: angular_diff(angle_of(points[i], center), target_angle),
    )
    if best_idx == 0:
        return points
    return points[best_idx:] + points[:best_idx]


def ensure_ccw(coords: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not coords:
        return []
    coords_list = list(coords)
    if distance_xy(coords_list[0], coords_list[-1]) > 1e-9:
        coords_list.append(coords_list[0])
    ring = LinearRing(coords_list)
    if ring.is_ccw:
        return list(ring.coords)[:-1]
    reversed_coords = list(ring.coords)[::-1]
    return reversed_coords[:-1]


def resample_ring(polygon: Polygon, sample_count: int) -> List[Tuple[float, float]]:
    if sample_count <= 1:
        x, y = polygon.exterior.coords[0]
        return [(x, y)]
    coords = ensure_ccw(polygon.exterior.coords)
    line = LineString(coords + [coords[0]])
    length = line.length
    if length <= EPSILON:
        x, y = coords[0]
        return [(x, y)] * sample_count
    step = length / sample_count
    samples: List[Tuple[float, float]] = []
    for i in range(sample_count):
        distance = i * step
        point = line.interpolate(distance, normalized=False)
        samples.append((point.x, point.y))
    return samples


def clamp_radial_transition(
    prev_point: Tuple[float, float],
    next_point: Tuple[float, float],
    center: Tuple[float, float],
    limit: float,
) -> Tuple[float, float]:
    if limit <= 0.0:
        return next_point
    rp = math.hypot(prev_point[0] - center[0], prev_point[1] - center[1])
    rn = math.hypot(next_point[0] - center[0], next_point[1] - center[1])
    dr = rn - rp
    if abs(dr) <= limit:
        return next_point
    target_r = rp + clamp(dr, -limit, limit)
    if rn <= EPSILON:
        return next_point
    scale = target_r / rn
    return (
        center[0] + (next_point[0] - center[0]) * scale,
        center[1] + (next_point[1] - center[1]) * scale,
    )


__all__ = [
    "EPSILON",
    "LinearRing",
    "LineString",
    "MultiPolygon",
    "Polygon",
    "ShapelyPoint",
    "unary_union",
    "clamp",
    "distance_xy",
    "angle_of",
    "angular_diff",
    "rotate_points_to_target",
    "rotate_points_to_angle",
    "ensure_ccw",
    "resample_ring",
    "clamp_radial_transition",
]
