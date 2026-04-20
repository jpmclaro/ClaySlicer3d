from __future__ import annotations

import math
from typing import List, Optional

import numpy as np

try:
    import trimesh
except ImportError as exc:  # pragma: no cover
    raise ModuleNotFoundError(
        "Dependencia trimesh ausente. Instale com `python -m pip install trimesh`."
    ) from exc


def ensure_ccw_xy(poly: np.ndarray) -> np.ndarray:
    if poly.shape[0] < 3:
        return poly
    x = poly[:, 0]
    y = poly[:, 1]
    area2 = float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))
    if area2 >= 0.0:
        return poly
    return poly[::-1].copy()


def polygon_perimeter(poly: np.ndarray) -> float:
    if poly.shape[0] < 2:
        return 0.0
    closed = np.vstack([poly, poly[0]])
    diffs = np.diff(closed, axis=0)
    return float(np.linalg.norm(diffs, axis=1).sum())


def resample_closed_arclength(poly: np.ndarray, npts: int) -> np.ndarray:
    if npts <= 1 or poly.shape[0] == 0:
        return poly[:1].copy()
    closed = np.vstack([poly, poly[0]])
    seg_lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    length = float(cumulative[-1])
    if length < 1e-9:
        return np.tile(poly[0], (npts, 1))
    targets = np.linspace(0.0, length, npts, endpoint=False)
    resampled: List[np.ndarray] = []
    for t in targets:
        idx = int(np.searchsorted(cumulative, t, side="right") - 1)
        idx = max(0, min(idx, len(poly) - 1))
        t0 = cumulative[idx]
        t1 = cumulative[idx + 1] if idx + 1 < len(cumulative) else length
        p0 = closed[idx]
        p1 = closed[idx + 1]
        if t1 - t0 < 1e-9:
            resampled.append(p0.copy())
        else:
            u = (t - t0) / (t1 - t0)
            resampled.append(p0 * (1.0 - u) + p1 * u)
    return np.asarray(resampled, dtype=float)


def kasa_circle_fit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    if x.size == 0:
        return np.zeros(2, dtype=float), 0.0
    x = x.reshape(-1, 1)
    y = y.reshape(-1, 1)
    a_matrix = np.hstack([2.0 * x, 2.0 * y, np.ones_like(x)])
    b_vector = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    cx, cy, c = sol.flatten()
    radius = float(math.sqrt(max(c + cx * cx + cy * cy, 0.0)))
    return np.array([float(cx), float(cy)], dtype=float), radius


def extract_loops_global_xy(section: Optional[trimesh.path.Path3D]) -> List[np.ndarray]:
    loops: List[np.ndarray] = []
    if section is None:
        return loops
    vertices = np.asarray(section.vertices)
    for entity in section.entities:
        if not hasattr(entity, "points"):
            continue
        idx = np.asarray(entity.points, dtype=int)
        pts = vertices[idx][:, :2]
        if pts.shape[0] < 3:
            continue
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        loops.append(pts)
    return loops


def largest_loop_at(mesh: trimesh.Trimesh, z: float) -> Optional[np.ndarray]:
    section = mesh.section(plane_origin=[0.0, 0.0, float(z)], plane_normal=[0.0, 0.0, 1.0])
    loops = extract_loops_global_xy(section)
    if not loops:
        return None
    perimeters = [polygon_perimeter(loop) for loop in loops]
    poly = loops[int(np.argmax(perimeters))]
    return ensure_ccw_xy(poly)


def rotate_start_to_seam(poly: np.ndarray, center: np.ndarray, dir_unit: np.ndarray) -> np.ndarray:
    """Rotates the polygon so that the point angularly closest to seam direction comes first.

    For models with radial waves, using argmax(dot) can pick different wave crests per layer,
    causing seam drift. Using argmin of angular distance ensures stable seam placement.
    """
    if poly.shape[0] == 0:
        return poly
    vectors = poly - center
    # Compute signed angle of each point relative to seam direction
    seam_angle = math.atan2(dir_unit[1], dir_unit[0])
    angles = np.arctan2(vectors[:, 1], vectors[:, 0])
    # Angular difference normalized to [-pi, pi]
    diffs = angles - seam_angle
    diffs = (diffs + math.pi) % (2.0 * math.pi) - math.pi
    idx = int(np.argmin(np.abs(diffs)))
    if idx == 0:
        return poly
    return np.vstack([poly[idx:], poly[:idx]])


def rotate_start_to_point(poly: np.ndarray, target: np.ndarray) -> np.ndarray:
    if poly.shape[0] == 0:
        return poly
    diffs = poly - target
    idx = int(np.argmin(np.linalg.norm(diffs, axis=1)))
    if idx == 0:
        return poly
    return np.vstack([poly[idx:], poly[:idx]])


__all__ = [
    "ensure_ccw_xy",
    "polygon_perimeter",
    "resample_closed_arclength",
    "kasa_circle_fit",
    "largest_loop_at",
    "rotate_start_to_seam",
    "rotate_start_to_point",
]
