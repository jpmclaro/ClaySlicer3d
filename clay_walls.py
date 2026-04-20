from __future__ import annotations

from typing import List, Optional

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

import trimesh
from shapely.geometry import Polygon, MultiPolygon

from clay_geometry import EPSILON
from clay_models import MeshAnalysis, Point3D
from clay_mesh import MeshAnalyzer
from clay_settings import ClayPrintSettings
from clay_spiral_sampling import resample_closed_arclength, rotate_start_to_seam


def ensure_ccw_xy(poly: np.ndarray) -> np.ndarray:
    x = poly[:, 0]
    y = poly[:, 1]
    area2 = np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))
    return poly if area2 >= 0 else poly[::-1].copy()


def kasa_circle_fit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    x = x.reshape(-1, 1)
    y = y.reshape(-1, 1)
    A = np.hstack([2 * x, 2 * y, np.ones_like(x)])
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    a, b_, c = sol.flatten()
    cx, cy = float(a), float(b_)
    r = float(np.sqrt(max(c + cx * cx + cy * cy, 0.0)))
    return np.array([cx, cy], dtype=float), r


def rotate_start_to_point(poly: np.ndarray, target: np.ndarray) -> np.ndarray:
    if poly.shape[0] == 0:
        return poly
    diffs = poly - target
    idx = int(np.argmin(np.linalg.norm(diffs, axis=1)))
    if idx == 0:
        return poly
    return np.vstack([poly[idx:], poly[:idx]])

def offset_loop(loop: np.ndarray, offset: float) -> Optional[np.ndarray]:
    if offset <= EPSILON:
        return ensure_ccw_xy(loop.copy())
    try:
        poly = Polygon(loop)
    except Exception:
        return ensure_ccw_xy(loop.copy())
    if not poly.is_valid or poly.area <= EPSILON:
        return ensure_ccw_xy(loop.copy())
    buffered = poly.buffer(-offset)
    if buffered.is_empty:
        return ensure_ccw_xy(loop.copy())
    if isinstance(buffered, MultiPolygon):
        buffered = max(buffered.geoms, key=lambda g: g.area if g.is_valid else 0.0)
    coords = np.array(buffered.exterior.coords, dtype=float)
    if coords.shape[0] < 3:
        return ensure_ccw_xy(loop.copy())
    if np.allclose(coords[0], coords[-1]):
        coords = coords[:-1]
    if coords.shape[0] < 3:
        return ensure_ccw_xy(loop.copy())
    return ensure_ccw_xy(coords)



class WallPlanner:
    def __init__(self, settings: ClayPrintSettings, mesh_analyzer: MeshAnalyzer):
        self.settings = settings
        self.mesh_analyzer = mesh_analyzer

    @staticmethod
    def _polydata_to_trimesh(polydata: vtk.vtkPolyData) -> Optional[trimesh.Trimesh]:
        triangle_filter = vtk.vtkTriangleFilter()
        triangle_filter.SetInputData(polydata)
        triangle_filter.Update()
        tri_output = triangle_filter.GetOutput()
        points = tri_output.GetPoints()
        if points is None or points.GetNumberOfPoints() == 0:
            return None
        vertices = vtk_to_numpy(points.GetData())
        polys = tri_output.GetPolys()
        if polys is None:
            return None
        cell_array = vtk_to_numpy(polys.GetData())
        if cell_array.size == 0:
            return None
        faces = cell_array.reshape(-1, 4)[:, 1:]
        try:
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        except Exception:
            return None
        return mesh

    def plan_spiral_walls(
        self,
        analysis: MeshAnalysis,
        polydata: vtk.vtkPolyData,
        start_point: Point3D,
    ) -> List[Point3D]:
        mesh = self._polydata_to_trimesh(polydata)
        if mesh is None:
            return []

        layer_height = max(EPSILON, self.settings.layer_height)
        start_z = float(start_point.z)
        heights: List[float] = [start_z]
        z_cursor = start_z + layer_height
        while z_cursor <= analysis.top_z + EPSILON:
            heights.append(z_cursor)
            z_cursor += layer_height
        if heights[-1] < analysis.top_z - layer_height * 0.25:
            heights.append(float(analysis.top_z))

        def largest_loop_at(mesh_obj: trimesh.Trimesh, z: float) -> Optional[np.ndarray]:
            section = mesh_obj.section(plane_origin=[0.0, 0.0, float(z)], plane_normal=[0.0, 0.0, 1.0])
            if section is None:
                return None
            loops: List[np.ndarray] = []
            vertices = section.vertices
            for entity in section.entities:
                if not hasattr(entity, "points"):
                    continue
                idx = np.asarray(entity.points, dtype=int)
                pts = vertices[idx][:, :2]
                if len(pts) >= 3:
                    if np.allclose(pts[0], pts[-1]):
                        pts = pts[:-1]
                    loops.append(pts)
            if not loops:
                return None
            perimeters = [float(np.sum(np.linalg.norm(np.diff(np.vstack([lp, lp[0]]), axis=0), axis=1))) for lp in loops]
            loop = loops[int(np.argmax(perimeters))]
            return ensure_ccw_xy(loop)

        offset_distance = max(0.0, getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width) * 0.5)
        raw_loops: List[Optional[np.ndarray]] = []
        for h in heights:
            loop = largest_loop_at(mesh, h)
            if loop is None:
                raw_loops.append(None)
                continue
            adjusted = offset_loop(loop, offset_distance)
            raw_loops.append(adjusted if adjusted is not None else ensure_ccw_xy(loop))
        first_valid_index = next((i for i, lp in enumerate(raw_loops) if lp is not None), None)
        if first_valid_index is None:
            return []

        center, _ = kasa_circle_fit(raw_loops[first_valid_index][:, 0], raw_loops[first_valid_index][:, 1])
        start_xy = np.array([start_point.x, start_point.y], dtype=float)
        seam_dir = start_xy - center
        if np.linalg.norm(seam_dir) <= EPSILON:
            seam_dir = np.array([1.0, 0.0], dtype=float)
        seam_dir = seam_dir / np.linalg.norm(seam_dir)

        processed_loops: List[Optional[np.ndarray]] = []
        seam_points: List[Optional[np.ndarray]] = []
        for loop in raw_loops:
            if loop is None:
                processed_loops.append(None)
                seam_points.append(None)
                continue
            resampled = resample_closed_arclength(loop, max(180, int(len(loop))))
            rotated = rotate_start_to_seam(resampled, center, seam_dir)
            seam_xy = rotated[0].copy() if rotated.shape[0] > 0 else None
            processed_loops.append(rotated)
            seam_points.append(seam_xy)

        # determine sample count
        reference_loop = processed_loops[first_valid_index]
        perimeter = float(np.sum(np.linalg.norm(np.diff(np.vstack([reference_loop, reference_loop[0]]), axis=0), axis=1)))
        step = max(0.3, min(perimeter / 400.0, 1.5))
        sample_count = max(180, int(perimeter / max(step, EPSILON)))

        rings: List[np.ndarray] = []
        z_values: List[float] = []
        prev_loop: Optional[np.ndarray] = None
        prev_z: Optional[float] = None
        for loop, seam_xy, z in zip(processed_loops, seam_points, heights):
            if loop is None:
                continue
            resampled = resample_closed_arclength(loop, sample_count)
            if seam_xy is not None and resampled.shape[0] > 0:
                resampled = rotate_start_to_point(resampled, seam_xy)
                resampled[0] = seam_xy.copy()
            rings.append(resampled)
            z_values.append(z)
            prev_loop = resampled
            prev_z = z

        if len(rings) < 2:
            return []

        prev_point = Point3D(start_point.x, start_point.y, start_point.z)
        path_points: List[Point3D] = []
        first_ring = rings[0]
        first_point = Point3D(float(first_ring[0][0]), float(first_ring[0][1]), z_values[0])
        path_points.append(first_point)
        prev_point = first_point

        # Ancoragem da parede: executar 1 volta plana no Z inicial da base
        # antes de iniciar a hélice de subida para evitar overhang/lacuna visual.
        for step_idx in range(1, sample_count + 1):
            p0 = first_ring[step_idx % sample_count]
            anchor_point = Point3D(float(p0[0]), float(p0[1]), z_values[0])
            if anchor_point.distance_to(prev_point) <= 1e-6:
                continue
            path_points.append(anchor_point)
            prev_point = anchor_point

        # Limite de avanço lateral apenas em seções com curvatura acentuada (não em taper reto)
        extrusion_width = max(EPSILON, getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width))
        # Fatores configuráveis com clamp de segurança
        lateral_fraction = max(0.1, min(1.0, getattr(self.settings, 'wall_lateral_fraction', 0.4)))
        curve_sensitivity = max(0.5, min(4.0, getattr(self.settings, 'wall_curve_sensitivity', 1.5)))
        max_lateral_per_rev = lateral_fraction * extrusion_width

        # Calcular variação de RAIO MÉDIO por par de anéis.
        # Raio médio = distância do centroide → imune ao componente tangencial.
        all_radial_disps = []
        for idx in range(len(rings) - 1):
            ra = rings[idx]
            rb = rings[idx + 1]
            r_a = float(np.mean(np.linalg.norm(ra - np.mean(ra, axis=0), axis=1)))
            r_b = float(np.mean(np.linalg.norm(rb - np.mean(rb, axis=0), axis=1)))
            all_radial_disps.append(abs(r_b - r_a))

        # Baseline = mediana de todos os pares → representa o "taper normal" da peça.
        # Zona curva tem deslocamentos muito acima desta mediana e toda ela dispara
        # (não só o pico isolado). Parede cônica reta fica abaixo e não dispara.
        baseline = float(np.median(all_radial_disps)) if all_radial_disps else 0.0
        # O limiar é o maior entre: o limite absoluto por volta e baseline × sensitivity.
        # Isso evita falsos positivos em peças muito planas (baseline próxima de zero).
        split_threshold = max(max_lateral_per_rev, baseline * curve_sensitivity)

        for idx in range(len(rings) - 1):
            ring_a = rings[idx]
            ring_b = rings[idx + 1]
            z_a = z_values[idx]
            z_b = z_values[idx + 1]
            delta_z = max(EPSILON, z_b - z_a)

            radial_disp = all_radial_disps[idx]

            # Sub-voltas em toda a zona onde o deslocamento supera o baseline × sensitivity
            num_revs = max(1, int(np.ceil(radial_disp / max_lateral_per_rev))) if radial_disp > split_threshold else 1

            for rev in range(num_revs):
                t_start = rev / num_revs
                t_end = (rev + 1) / num_revs
                z_start = z_a + delta_z * t_start
                z_end = z_a + delta_z * t_end
                for step_idx in range(1, sample_count + 1):
                    t_rev = step_idx / sample_count
                    t = t_start + (t_end - t_start) * t_rev
                    p_a = ring_a[step_idx % sample_count]
                    p_b = ring_b[step_idx % sample_count]
                    xy = (1.0 - t) * p_a + t * p_b
                    z_val = z_start + (z_end - z_start) * t_rev
                    point = Point3D(float(xy[0]), float(xy[1]), float(z_val))
                    if point.distance_to(prev_point) <= 1e-6:
                        continue
                    path_points.append(point)
                    prev_point = point

        return path_points


__all__ = ["WallPlanner"]

