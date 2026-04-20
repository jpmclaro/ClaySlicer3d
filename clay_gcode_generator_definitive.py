#!/usr/bin/env python
"""
Gerador de G-code modularizado inspirado nos algoritmos do OrcaSlicer.

Mantém a lógica especial da primeira camada (ponto central, micro espiral e
arco de ligação) e delega a geração das paredes a um planejador helicoidal
estilo Orca.
"""
from __future__ import annotations

import math
import os
from typing import List, Optional

import numpy as np
import vtk
from shapely.geometry import Polygon, MultiPolygon, Point

from clay_base_layers import BaseLayerBuilder
from clay_gcode_core import GCodeGenerator
from clay_geometry import clamp, EPSILON
from clay_mesh import MeshAnalyzer
from clay_models import MeshAnalysis, Point3D
from clay_parametric_path_planner import ParametricSpiralPlanner
from clay_settings import ClayPrintSettings
from clay_spiral_sampling import (
    largest_loop_at,
    polygon_perimeter,
    resample_closed_arclength,
    rotate_start_to_point,
)
from clay_walls import WallPlanner
from clay_walls_nonplanar import NonPlanarWallPlanner




def _offset_loop(loop: np.ndarray, offset: float) -> Optional[np.ndarray]:
    if offset <= EPSILON:
        return loop
    try:
        poly = Polygon(loop)
    except Exception:
        return loop
    if not poly.is_valid or poly.area <= EPSILON:
        return loop
    buffered = poly.buffer(-offset)
    if buffered.is_empty:
        return loop
    if isinstance(buffered, MultiPolygon):
        buffered = max(buffered.geoms, key=lambda g: g.area if g.is_valid else 0.0)
    coords = np.array(buffered.exterior.coords, dtype=float)
    if coords.shape[0] < 3:
        return loop
    if np.allclose(coords[0], coords[-1]):
        coords = coords[:-1]
    if coords.shape[0] < 3:
        return loop
    return coords
class ClayGCodeGenerator:
    def __init__(self, settings: ClayPrintSettings):
        self.settings = settings
        self.gcode_gen = GCodeGenerator(settings)
        self.mesh_analyzer = MeshAnalyzer(settings)
        self.base_builder = BaseLayerBuilder(settings, self.gcode_gen, self.mesh_analyzer)
        self.wall_planner = WallPlanner(settings, self.mesh_analyzer)
        self.nonplanar_planner = NonPlanarWallPlanner(settings, self.mesh_analyzer)
        self.apply_recentering = True
        self.last_overhang_report: List[dict] = []
        self._last_overhang_compensation_points: int = 0
        self.last_generation_metadata: dict = {}

    def analyze_mesh(self, polydata: vtk.vtkPolyData) -> MeshAnalysis:
        analysis = self.mesh_analyzer.analyze(polydata)
        analysis.contour_cache = {}
        return analysis

    def _slice_wall_into_layers(
        self,
        wall_points: List[Point3D],
        analysis: MeshAnalysis,
        approx_height: float,
    ) -> list[dict]:
        if not wall_points:
            return []
        layer_height = max(approx_height, 1e-6)
        base_z = float(analysis.base_z)
        layers: dict[int, list[int]] = {}
        for idx, pt in enumerate(wall_points):
            rel = max(0.0, float(pt.z) - base_z)
            bucket = int(math.floor(rel / layer_height + 1e-6))
            layers.setdefault(bucket, []).append(idx)
        layer_infos: list[dict] = []
        for bucket in sorted(layers.keys()):
            indices = layers[bucket]
            if not indices:
                continue
            pts_xy = [(float(wall_points[i].x), float(wall_points[i].y)) for i in indices]
            polygon = None
            if len(pts_xy) >= 3:
                try:
                    candidate = Polygon(pts_xy)
                    if candidate.is_valid and candidate.area > EPSILON:
                        polygon = candidate.buffer(0.0)
                except Exception:
                    polygon = None
            mean_z = sum(float(wall_points[i].z) for i in indices) / len(indices)
            layer_infos.append(
                {
                    'layer': bucket,
                    'indices': indices,
                    'polygon': polygon,
                    'mean_z': mean_z,
                }
            )
        return layer_infos

    def _generate_taper_closing(
        self,
        polydata: vtk.vtkPolyData,
        analysis: MeshAnalysis,
        last_wall_point: Point3D,
        prev_wall_point: Point3D | None,
    ) -> List[Point3D]:
        """Gera percurso final de taper mantendo o Z e reduzindo extrusão."""
        mesh = self.wall_planner._polydata_to_trimesh(polydata)
        if mesh is None:
            return []

        target_z = float(last_wall_point.z)
        loop = None
        for offset in [0.0, -0.05, -0.1, -0.2, -0.4, -0.8, -1.5]:
            loop = largest_loop_at(mesh, target_z + offset)
            if loop is not None:
                break
        if loop is None:
            loop = largest_loop_at(mesh, analysis.top_z)
        if loop is None:
            return []

        offset_distance = max(0.0, getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width) * 0.5)
        adjusted_loop = _offset_loop(loop, offset_distance)
        loop = adjusted_loop if adjusted_loop is not None else loop

        perimeter = polygon_perimeter(loop)
        step = max(0.3, min(perimeter / 400.0, 1.5))
        sample_count = max(180, int(perimeter / max(step, 1e-9)))
        ring = resample_closed_arclength(loop, sample_count)

        target_xy = np.array([last_wall_point.x, last_wall_point.y], dtype=float)
        ring = rotate_start_to_point(ring, target_xy)
        ring[0] = target_xy

        if prev_wall_point is not None:
            prev_vec = np.array([
                float(last_wall_point.x - prev_wall_point.x),
                float(last_wall_point.y - prev_wall_point.y),
            ], dtype=float)
            if np.linalg.norm(prev_vec) > EPSILON and sample_count > 1:
                next_vec = ring[1 % sample_count] - ring[0]
                if np.dot(prev_vec, next_vec) < 0.0:
                    ring = ring[::-1].copy()
                    ring = rotate_start_to_point(ring, target_xy)
                    ring[0] = target_xy

        total_turns = max(0.0, float(self.settings.end_taper_revolutions))
        if total_turns <= 0.0:
            return []
        full_turns = int(math.floor(total_turns))
        remainder = total_turns - full_turns

        taper_z = float(last_wall_point.z)
        taper_points: List[Point3D] = [
            Point3D(float(ring[0][0]), float(ring[0][1]), taper_z)
        ]

        def append_segment(count: int) -> None:
            for step_idx in range(1, count + 1):
                xy = ring[step_idx % sample_count]
                taper_points.append(Point3D(float(xy[0]), float(xy[1]), taper_z))

        for _ in range(full_turns):
            append_segment(sample_count)

        if remainder > 1e-6:
            partial_steps = max(2, int(round(sample_count * remainder)))
            append_segment(partial_steps)

        return taper_points

    def _analyze_overhangs(self, wall_points: List[Point3D], analysis: MeshAnalysis) -> tuple[list[dict], set[int]]:
        threshold = float(getattr(self.settings, 'max_overhang_angle_deg', 0.0))
        if threshold <= 0.0 or len(wall_points) < 3:
            return [], set()

        threshold = min(threshold, 89.5)
        threshold_rad = math.radians(threshold)
        tan_threshold = max(math.tan(threshold_rad), 1e-3)

        base_layer_height = float(getattr(self.settings, 'layer_height', 1.0))
        min_vertical = max(0.05, base_layer_height * 0.3)
        layers = self._slice_wall_into_layers(wall_points, analysis, base_layer_height)
        if len(layers) < 2:
            return [], set()

        print(
            f"[OVERHANG] Orca-like análise em {len(layers)} camadas | threshold={threshold:.1f}° | layer={base_layer_height:.3f}mm"
        )

        is_flagged = [False] * len(wall_points)
        angle_by_idx: dict[int, float] = {}

        for layer_idx in range(1, len(layers)):
            current = layers[layer_idx]
            lower = layers[layer_idx - 1]
            curr_poly = current.get('polygon')
            lower_poly = lower.get('polygon')
            if curr_poly is None or lower_poly is None:
                continue
            vertical_gap = max(min_vertical, current['mean_z'] - lower['mean_z'])
            if vertical_gap <= EPSILON:
                continue
            horizontal_allowance = vertical_gap / tan_threshold
            try:
                support_zone = lower_poly.buffer(horizontal_allowance, resolution=24)
                if support_zone.is_empty:
                    support_zone = lower_poly
                support_zone = support_zone.buffer(0.0)
            except Exception:
                support_zone = lower_poly

            for idx in current['indices']:
                if idx <= 0 or idx >= len(wall_points):
                    continue
                pt = wall_points[idx]
                pt_geom = Point(float(pt.x), float(pt.y))
                if support_zone.contains(pt_geom) or support_zone.touches(pt_geom):
                    continue
                horizontal_delta = pt_geom.distance(lower_poly)
                angle = math.degrees(math.atan2(max(horizontal_delta, 0.0), vertical_gap))
                if angle < threshold:
                    continue
                is_flagged[idx] = True
                is_flagged[idx - 1] = True
                angle_by_idx[idx] = angle
                angle_by_idx[idx - 1] = angle
                print(
                    f"[OVERHANG] layer={layer_idx} idx={idx} ΔXY={horizontal_delta:.3f}mm ΔZ={vertical_gap:.3f}mm -> ângulo={angle:.2f}°"
                )

        segments: list[dict] = []
        flagged: set[int] = set()
        current_segment: Optional[dict] = None

        for idx in range(1, len(wall_points)):
            if not is_flagged[idx]:
                if current_segment is not None:
                    segments.append(current_segment)
                    current_segment = None
                continue

            flagged.add(idx)
            prev_pt = wall_points[idx - 1]
            curr_pt = wall_points[idx]
            dist_3d = math.sqrt(
                (curr_pt.x - prev_pt.x) ** 2 + (curr_pt.y - prev_pt.y) ** 2 + (curr_pt.z - prev_pt.z) ** 2
            )
            if dist_3d <= EPSILON:
                continue

            if current_segment is None:
                current_segment = {
                    'start': idx - 1,
                    'end': idx,
                    'start_z': prev_pt.z,
                    'end_z': curr_pt.z,
                    'max_angle': angle_by_idx.get(idx, threshold),
                    'length_mm': dist_3d,
                }
            else:
                current_segment['end'] = idx
                current_segment['end_z'] = curr_pt.z
                current_segment['max_angle'] = max(current_segment['max_angle'], angle_by_idx.get(idx, threshold))
                current_segment['length_mm'] += dist_3d

        if current_segment is not None:
            segments.append(current_segment)

        print(f"[OVERHANG] Total segmentos detectados: {len(segments)}")
        for segment in segments:
            start_idx = max(0, int(segment.get('start', 0)))
            end_idx = min(len(wall_points) - 1, int(segment.get('end', start_idx)))
            segment['points'] = [
                (
                    float(wall_points[i].x),
                    float(wall_points[i].y),
                    float(wall_points[i].z),
                )
                for i in range(start_idx, end_idx + 1)
            ]
        return segments, flagged

    def _expand_support_indices(self, wall_points: List[Point3D], flagged: set[int]) -> set[int]:
        if not flagged:
            return set()
        support_layers = max(0, int(getattr(self.settings, 'overhang_support_layers', 0)))
        if support_layers <= 0:
            return set(flagged)
        support_height = support_layers * max(0.01, float(getattr(self.settings, 'layer_height', 1.0)))
        expanded = set(flagged)
        for idx in sorted(flagged):
            target_z = wall_points[idx].z
            min_z = target_z - support_height
            cursor = idx - 1
            while cursor >= 0 and wall_points[cursor].z >= min_z - 1e-6:
                expanded.add(cursor)
                cursor -= 1
        return expanded

    def _apply_overhang_compensation(
        self,
        wall_points: List[Point3D],
        indices: set[int],
        analysis: MeshAnalysis,
    ) -> dict[int, float]:
        if not indices:
            return {}
        base_width = float(getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width))
        extra_factor = clamp(float(getattr(self.settings, 'min_vertical_overlap', 0.0)), 0.0, 1.5)
        if base_width <= EPSILON or extra_factor <= EPSILON:
            return {}
        new_width = base_width * (1.0 + extra_factor)
        delta = max(0.0, (new_width - base_width) * 0.5)
        overrides: dict[int, float] = {}
        for idx in sorted(indices):
            overrides[idx] = new_width
            if delta <= EPSILON:
                continue
            pt = wall_points[idx]
            vec_x = pt.x - analysis.center_x
            vec_y = pt.y - analysis.center_y
            norm = math.hypot(vec_x, vec_y)
            if norm <= EPSILON:
                continue
            unit_x = vec_x / norm
            unit_y = vec_y / norm
            pt.x -= unit_x * delta
            pt.y -= unit_y * delta
        return overrides

    def _interpolate_radius_profile(
        self,
        z_rel: float,
        keyframes: list[tuple[float, float]],
        sharp_corners: bool,
        transition_len_mm: float,
    ) -> float:
        if not keyframes:
            return 1.0
        if z_rel <= keyframes[0][0]:
            return keyframes[0][1]

        # Cantos vivos: perfil linear por trechos sem blend local.
        if sharp_corners or transition_len_mm <= EPSILON or len(keyframes) < 3:
            for idx in range(1, len(keyframes)):
                z0, r0 = keyframes[idx - 1]
                z1, r1 = keyframes[idx]
                if z_rel <= z1:
                    if abs(z1 - z0) <= EPSILON:
                        return r1
                    t = (z_rel - z0) / (z1 - z0)
                    return r0 + (r1 - r0) * t
            return keyframes[-1][1]

        # Transição suave: blend local em torno de cada quebra de segmento.
        half_win = max(0.0, transition_len_mm * 0.5)
        for corner_idx in range(1, len(keyframes) - 1):
            zc, rc = keyframes[corner_idx]
            z_left, r_left = keyframes[corner_idx - 1]
            z_right, r_right = keyframes[corner_idx + 1]

            # Janela não pode invadir segmentos vizinhos completamente.
            left_room = max(EPSILON, zc - z_left)
            right_room = max(EPSILON, z_right - zc)
            local_half = min(half_win, left_room * 0.45, right_room * 0.45)
            if local_half <= EPSILON:
                continue

            z_a = zc - local_half
            z_b = zc + local_half
            if z_rel < z_a or z_rel > z_b:
                continue

            # Valor da reta do trecho anterior no ponto z_rel.
            t_prev = (z_rel - z_left) / max(EPSILON, zc - z_left)
            r_prev = r_left + (rc - r_left) * t_prev

            # Valor da reta do trecho seguinte no ponto z_rel.
            t_next = (z_rel - zc) / max(EPSILON, z_right - zc)
            r_next = rc + (r_right - rc) * t_next

            # Smoothstep para transição C1 visualmente suave.
            t = (z_rel - z_a) / max(EPSILON, z_b - z_a)
            t_smooth = t * t * (3.0 - 2.0 * t)
            return r_prev + (r_next - r_prev) * t_smooth

        for idx in range(1, len(keyframes)):
            z0, r0 = keyframes[idx - 1]
            z1, r1 = keyframes[idx]
            if z_rel <= z1:
                if abs(z1 - z0) <= EPSILON:
                    return r1
                t = (z_rel - z0) / (z1 - z0)
                return r0 + (r1 - r0) * t
        return keyframes[-1][1]

    def _build_parametric_profile(self) -> tuple[list[tuple[float, float]], float]:
        s = self.settings
        obj = str(getattr(s, 'parametric_object_type', 'plate')).strip().lower()

        if obj == 'cup':
            h = max(1.0, float(getattr(s, 'cup_height', 90.0)))
            r0 = max(0.5, float(getattr(s, 'cup_base_diameter', 55.0)) * 0.5)
            r1 = max(0.5, float(getattr(s, 'cup_top_diameter', 85.0)) * 0.5)
            return [(0.0, r0), (h, r1)], h

        if obj == 'jar':
            h_body = max(1.0, float(getattr(s, 'jar_body_height', 85.0)))
            h_neck = max(1.0, float(getattr(s, 'jar_neck_height', 20.0)))
            h = h_body + h_neck
            r0 = max(0.5, float(getattr(s, 'jar_base_diameter', 55.0)) * 0.5)
            r_mid = max(0.5, float(getattr(s, 'jar_max_body_diameter', 110.0)) * 0.5)
            r_top = max(0.5, float(getattr(s, 'jar_top_diameter', 70.0)) * 0.5)
            return [(0.0, r0), (h_body, r_mid), (h, r_top)], h

        if obj == 'bottle':
            h_body = max(1.0, float(getattr(s, 'bottle_body_height', 100.0)))
            h_shoulder = max(0.5, float(getattr(s, 'bottle_shoulder_height', 20.0)))
            h_neck = max(1.0, float(getattr(s, 'bottle_neck_height', 45.0)))
            h = h_body + h_shoulder + h_neck
            r0 = max(0.5, float(getattr(s, 'bottle_base_diameter', 55.0)) * 0.5)
            r_body_top = max(0.5, float(getattr(s, 'bottle_body_top_diameter', 80.0)) * 0.5)
            r_neck = max(0.5, float(getattr(s, 'bottle_neck_diameter', 36.0)) * 0.5)
            return [
                (0.0, r0),
                (h_body, r_body_top),
                (h_body + h_shoulder, r_neck),
                (h, r_neck),
            ], h

        # Default: plate
        h = max(1.0, float(getattr(s, 'plate_wall_height', 30.0)))
        r0 = max(0.5, float(getattr(s, 'plate_base_diameter', 60.0)) * 0.5)
        r1 = max(0.5, float(getattr(s, 'plate_top_diameter', 140.0)) * 0.5)
        return [(0.0, r0), (h, r1)], h

    def _generate_parametric_gcode(self) -> str:
        self.last_overhang_report = []
        self._last_overhang_compensation_points = 0
        self.last_generation_metadata = {}

        # No modo paramétrico, o perfil já é construído no centro da mesa.
        self.gcode_gen.extra_offset_x = 0.0
        self.gcode_gen.extra_offset_y = 0.0
        self.gcode_gen.extra_offset_z = 0.0

        planner = ParametricSpiralPlanner(self.settings)
        plan = planner.build_plan()

        gcode_lines: List[str] = []
        gcode_lines.extend(self.gcode_gen.generate_header())
        gcode_lines.append("; PARAMETRIC_MODE_START")
        gcode_lines.append(
            f"; PARAMETRIC_OBJECT type={plan.object_type} wall_height={plan.wall_height:.3f}"
        )
        gcode_lines.append(
            f"; PARAMETRIC_CORNERS sharp={int(plan.sharp_corners)} transition_mm={plan.transition_length_mm:.3f}"
        )
        gcode_lines.append(
            f"; PARAMETRIC_BASE_TRANSITION radius_mm={plan.transition_radius_mm:.3f}"
        )
        gcode_lines.append(
            f"; PARAMETRIC_BASE_TRANSITION_CURVE mode={plan.transition_curve_mode} strength={plan.transition_curve_strength:.2f}"
        )

        first_h = plan.first_layer_height
        wall_h = plan.wall_layer_height
        z0 = first_h

        gcode_lines.append(
            self.gcode_gen.move_to(0.0, 0.0, z0, speed=self.settings.travel_speed, extrude=False)
        )

        # Ponto central na base (responde ao checkbox "Ponto central na base" na aba Material)
        if bool(getattr(self.settings, 'enable_center_point_extrusion', True)):
            cp_w     = max(0.2, float(getattr(self.settings, 'center_point_width', self.settings.extrusion_width)))
            cp_dips  = max(1, int(getattr(self.settings, 'center_point_dips', 2)))
            cp_speed = self.settings.first_layer_speed * 0.3
            # Desce próximo ao leito (meia espessura do bico) sem extrusar
            z_dip = max(0.1, self.settings.nozzle_diameter * 0.5)
            rise  = max(0.01, z0 - z_dip)
            gcode_lines.append("; CENTER_POINT_START")
            gcode_lines.append(
                self.gcode_gen.move_to(0.0, 0.0, z_dip, speed=self.settings.travel_speed, extrude=False)
            )
            if cp_dips >= 2:
                # Primeira subida: fluxo reduzido (prime)
                gcode_lines.append(
                    self.gcode_gen.move_to(
                        0.0, 0.0, z0, speed=cp_speed, extrude=True,
                        layer_height_override=rise, extrusion_width_override=cp_w,
                        flow_multiplier=0.75,
                    )
                )
                gcode_lines.append(
                    self.gcode_gen.move_to(0.0, 0.0, z_dip, speed=self.settings.travel_speed, extrude=False)
                )
            # Subida final: fluxo pleno
            gcode_lines.append(
                self.gcode_gen.move_to(
                    0.0, 0.0, z0, speed=cp_speed, extrude=True,
                    layer_height_override=rise, extrusion_width_override=cp_w,
                    flow_multiplier=1.5,
                )
            )
            gcode_lines.append("; CENTER_POINT_END")

        # Base em espiral única (1 camada)
        gcode_lines.append("; BASE_SPIRAL_START")
        for idx, p in enumerate(plan.base_points):
            gcode_lines.append(
                self.gcode_gen.move_to(
                    p.x,
                    p.y,
                    p.z,
                    speed=self.settings.first_layer_speed if idx > 0 else self.settings.travel_speed,
                    extrude=idx > 0,
                    layer_height_override=first_h,
                    extrusion_width_override=self.settings.extrusion_width,
                )
            )
        gcode_lines.append("; BASE_SPIRAL_END")

        # Parede 100% espiral já planejada por rotina dedicada.
        gcode_lines.append("; WALLS_START")
        for p in plan.wall_points:
            gcode_lines.append(
                self.gcode_gen.move_to(
                    p.x,
                    p.y,
                    p.z,
                    speed=self.settings.wall_speed,
                    extrude=True,
                    flow_multiplier=self.settings.wall_flow_multiplier,
                    layer_height_override=wall_h,
                    extrusion_width_override=self.settings.other_layers_extrusion_width,
                )
            )

        gcode_lines.append("; WALLS_END")

        # Taper final paramétrico: N voltas extras com extrusão decrescente
        if self.settings.enable_end_taper and self.settings.end_taper_revolutions > 0 and plan.wall_points:
            gcode_lines.append("; TAPER_START - Fechamento suave (paramétrico)")
            last_wp = plan.wall_points[-1]
            r_last = math.hypot(last_wp.x, last_wp.y)
            z_last = float(last_wp.z)
            theta_last = math.atan2(last_wp.y, last_wp.x)
            res_deg = float(getattr(self.settings, 'vase_mode_resolution_deg', 2.0))
            spr_t = max(45, int(round(360.0 / max(0.5, res_deg))))
            dtheta_t = 2.0 * math.pi / spr_t
            total_taper_pts = int(self.settings.end_taper_revolutions * spr_t)
            for i in range(1, total_taper_pts + 1):
                theta_last += dtheta_t
                progress = i / total_taper_pts
                flow = max(0.0, 1.0 - progress)
                gcode_lines.append(
                    self.gcode_gen.move_to(
                        r_last * math.cos(theta_last),
                        r_last * math.sin(theta_last),
                        z_last,
                        speed=self.settings.wall_speed,
                        extrude=True,
                        flow_multiplier=flow * self.settings.wall_flow_multiplier,
                        layer_height_override=wall_h,
                        extrusion_width_override=self.settings.other_layers_extrusion_width,
                    )
                )
            gcode_lines.append("; TAPER_END")

        gcode_lines.append("; PARAMETRIC_MODE_END")
        gcode_lines.extend(self.gcode_gen.generate_footer())
        return "\n".join(gcode_lines)

    def generate_gcode(self, polydata: Optional[vtk.vtkPolyData]) -> str:
        if bool(getattr(self.settings, 'enable_parametric_mode', False)):
            return self._generate_parametric_gcode()

        if polydata is None:
            raise RuntimeError("modelo 3D ausente: carregue STL/OBJ ou ative modo paramétrico")

        analysis = self.analyze_mesh(polydata)
        self.last_overhang_report = []
        self._last_overhang_compensation_points = 0
        if self.apply_recentering:
            self.gcode_gen.extra_offset_x = -analysis.center_x
            self.gcode_gen.extra_offset_y = -analysis.center_y
            self.gcode_gen.extra_offset_z = -analysis.base_z
        else:
            self.gcode_gen.extra_offset_x = 0.0
            self.gcode_gen.extra_offset_y = 0.0
            self.gcode_gen.extra_offset_z = 0.0

        gcode_lines: List[str] = []
        gcode_lines.extend(self.gcode_gen.generate_header())

        first_layer_z = analysis.base_z + self.settings.first_layer_height * 0.5
        gcode_lines.append(
            self.gcode_gen.move_to(
                0.0,
                0.0,
                first_layer_z,
                speed=self.settings.travel_speed,
                extrude=False,
            )
        )

        last_point = self.base_builder.generate_base(gcode_lines, analysis, polydata)

        # Escolher planejador baseado no modo
        if self.settings.enable_nonplanar_mode:
            gcode_lines.append("; NONPLANAR_MODE_ENABLED")
            wall_points = self.nonplanar_planner.plan_nonplanar_walls(analysis, polydata, last_point)
        else:
            wall_points = self.wall_planner.plan_spiral_walls(analysis, polydata, last_point)
        
        if not wall_points:
            raise RuntimeError("failed to generate wall path")

        overhang_segments, flagged_indices = self._analyze_overhangs(wall_points, analysis)
        self.last_overhang_report = overhang_segments
        reinforcement_indices: set[int] = set()
        width_overrides: dict[int, float] = {}
        if flagged_indices:
            reinforcement_indices = self._expand_support_indices(wall_points, flagged_indices)
            if self.settings.enable_overhang_compensation:
                width_overrides = self._apply_overhang_compensation(wall_points, reinforcement_indices, analysis)
                self._last_overhang_compensation_points = len(width_overrides)
        if not self.settings.enable_overhang_compensation:
            self._last_overhang_compensation_points = 0
        
        # Adicionar BLEND 3D suave entre base e parede
        # Para non-planar, a transição já é natural (começa do start_point)
        if wall_points and not self.settings.enable_nonplanar_mode:
            first_wall_point = wall_points[0]
            
            # Calcular distância 3D entre base e primeiro ponto da parede
            dx = first_wall_point.x - last_point.x
            dy = first_wall_point.y - last_point.y
            dz = first_wall_point.z - last_point.z
            gap_distance_xy = math.hypot(dx, dy)
            gap_distance_3d = math.hypot(gap_distance_xy, dz)
            
            # Calcular variação angular (importante para geometrias não-uniformes)
            center = (analysis.center_x, analysis.center_y)
            angle_base = math.atan2(last_point.y - center[1], last_point.x - center[0])
            angle_wall = math.atan2(first_wall_point.y - center[1], first_wall_point.x - center[0])
            angle_diff = abs((angle_wall - angle_base + math.pi) % (2.0 * math.pi) - math.pi)
            
            # Calcular quantas camadas de diferença há entre base e parede
            z_layers_gap = abs(dz) / max(0.01, self.settings.layer_height)
            
            # Threshold: 3% da largura de extrusão OU variação angular > 2 graus OU gap Z > 0.5 camadas
            threshold_dist = self.settings.extrusion_width * 0.03
            threshold_angle = math.radians(2.0)
            threshold_z_layers = 0.5  # Mais de meia camada de diferença em Z
            
            # Gerar blend se:
            # 1. Distância XY > threshold OU
            # 2. Distância 3D > threshold OU  
            # 3. Variação angular significativa (indica geometria não-uniforme) OU
            # 4. Gap Z significativo (precisa rampa vertical)
            should_blend = (gap_distance_xy > threshold_dist or 
                          gap_distance_3d > threshold_dist or
                          angle_diff > threshold_angle or
                          z_layers_gap > threshold_z_layers)
            
            if should_blend:
                # Para gaps Z grandes, precisamos de mais pontos para fazer rampa suave
                blend_points = self.base_builder._generate_transition_blend(
                    last_point,
                    first_wall_point,
                    analysis.center_x,
                    analysis.center_y
                )
                
                # Emitir blend com comentários
                if len(blend_points) > 1:  # Pelo menos 2 pontos (início e fim)
                    wall_h = self.settings.layer_height
                    wall_w = getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
                    wall_speed = getattr(self.settings, 'wall_speed', self.settings.print_speed)
                    blend_flow_factor = clamp(
                        float(getattr(self.settings, 'transition_blend_flow_factor', 1.0)),
                        0.1,
                        2.0,
                    )

                    gcode_lines.append(
                        f"; TRANSITION_BLEND_START "
                        f"(gap_xy={gap_distance_xy:.3f}mm, gap_z={dz:.3f}mm, "
                        f"angle={math.degrees(angle_diff):.2f}°, z_layers={z_layers_gap:.1f})"
                    )
                    for point in blend_points[1:]:  # Pular o primeiro (já está na base)
                        layer_h = wall_h
                        layer_w = wall_w
                        speed = wall_speed

                        gcode_lines.append(
                            self.gcode_gen.move_to(
                                point.x,
                                point.y,
                                point.z,
                                speed=speed,
                                extrude=True,
                                flow_multiplier=self.settings.wall_flow_multiplier * blend_flow_factor,
                                layer_height_override=layer_h,
                                extrusion_width_override=layer_w,
                            )
                        )
                    gcode_lines.append("; TRANSITION_BLEND_END")
                    # Substituir o primeiro ponto da parede pelo último do blend
                    wall_points[0] = blend_points[-1]
        
        # Gerar G-code da espiral COMPLETA (incluindo taper integrado se habilitado)
        gcode_lines.append("; WALLS_START")
        if overhang_segments:
            gcode_lines.append(
                f"; OVERHANG_ALERT count={len(overhang_segments)} threshold={self.settings.max_overhang_angle_deg:.1f}deg"
            )
        if width_overrides:
            extra_factor = clamp(float(getattr(self.settings, 'min_vertical_overlap', 0.0)), 0.0, 1.5)
            support_layers = max(0, int(getattr(self.settings, 'overhang_support_layers', 0)))
            gcode_lines.append(
                "; OVERHANG_COMPENSATION applied="
                f"{len(width_overrides)} width_factor={1.0 + extra_factor:.2f} support_layers={support_layers}"
            )
        
        # ⭐ TAPER INTEGRADO: Detectar se há pontos com height_factor
        has_integrated_taper = False
        taper_start_idx = -1
        
        if self.settings.enable_nonplanar_mode and self.settings.enable_end_taper:
            # Procurar o primeiro ponto com height_factor < 1.0
            for idx, point in enumerate(wall_points):
                if hasattr(point, 'height_factor') and point.height_factor < 0.99:
                    has_integrated_taper = True
                    taper_start_idx = idx
                    break
        
        if has_integrated_taper:
            gcode_lines.append(f"; TAPER_INTEGRADO na última revolução (a partir do ponto {taper_start_idx})")
        
        # ⭐ MODO NON-PLANAR: Calcular altura de extrusão baseada em ΔZ real
        if self.settings.enable_nonplanar_mode:
            gcode_lines.append("; ALTURA_DINAMICA - Ajustada conforme topografia")
        
        # Emitir pontos da parede
        for idx, point in enumerate(wall_points):
            # ⭐ NON-PLANAR: Calcular altura de extrusão dinâmica baseada em ΔZ
            if self.settings.enable_nonplanar_mode and idx > 0:
                prev_point = wall_points[idx - 1]
                
                # Calcular distância 3D entre pontos
                dx = point.x - prev_point.x
                dy = point.y - prev_point.y
                dz = point.z - prev_point.z
                
                # Distância XY (horizontal)
                dist_xy = math.sqrt(dx*dx + dy*dy)
                
                # ⭐ ALTURA DE EXTRUSÃO = |ΔZ| (componente vertical do movimento)
                # Em superfícies íngremes: |ΔZ| grande → altura aumenta
                # Em superfícies planas: |ΔZ| pequeno → usa altura mínima
                delta_z = abs(dz)
                
                # Altura mínima (do preset do usuário)
                min_layer_height = self.settings.layer_height
                
                # ⭐ IMPORTANTE: Usar o MAIOR entre |ΔZ| e altura mínima
                # Isso garante que:
                # - Regiões íngremes (|ΔZ| > min): usa |ΔZ| para preencher totalmente
                # - Regiões planas (|ΔZ| < min): usa min para manter qualidade
                dynamic_layer_height = max(delta_z, min_layer_height)
                
                # Limitar altura máxima para evitar sobre-extrusão
                max_layer_height = min_layer_height * 2.5  # Até 2.5x a altura base
                dynamic_layer_height = min(dynamic_layer_height, max_layer_height)
                
                # Verificar se ponto tem metadata de taper integrado
                height_factor = getattr(point, 'height_factor', 1.0)
                
                # Aplicar fator de taper (se houver)
                layer_height = dynamic_layer_height * height_factor
            else:
                # Primeiro ponto ou modo planar: usar altura do preset
                height_factor = getattr(point, 'height_factor', 1.0)

                # No modo planar, a parede deve começar já na altura normal de parede.
                # A transição de base->parede continua extrudando no bloco TRANSITION_BLEND.
                layer_height = self.settings.layer_height * height_factor
            
            # Se altura muito pequena (< 0.01mm), não extrudar
            if height_factor < 0.01:
                gcode_lines.append(
                    self.gcode_gen.move_to(
                        point.x, point.y, point.z,
                        speed=self.settings.wall_speed,
                        extrude=False,
                    )
                )
            else:
                default_width = self.settings.other_layers_extrusion_width
                width_override = width_overrides.get(idx, default_width)
                gcode_lines.append(
                    self.gcode_gen.move_to(
                        point.x,
                        point.y,
                        point.z,
                        speed=self.settings.wall_speed,
                        extrude=True,
                        flow_multiplier=self.settings.wall_flow_multiplier,
                        layer_height_override=layer_height,  # ⭐ Altura dinâmica!
                        extrusion_width_override=width_override,
                    )
                )
        
        gcode_lines.append("; WALLS_END")
        
        # TAPER SEPARADO: Apenas para modo planar ou se não houver taper integrado
        if self.settings.enable_end_taper and self.settings.end_taper_revolutions > 0:
            if not (self.settings.enable_nonplanar_mode and has_integrated_taper):
                # Modo planar - usar método tradicional
                gcode_lines.append("; TAPER_START - Fechamento suave (volta extra)")
                
                prev_wall_point = wall_points[-2] if len(wall_points) > 1 else None
                taper_points = self._generate_taper_closing(polydata, analysis, wall_points[-1], prev_wall_point)
                
                if taper_points:
                    # PLANAR: Reduzir extrusão (método antigo)
                    total_taper_points = len(taper_points)
                    for idx, point in enumerate(taper_points):
                        progress = idx / max(1, total_taper_points - 1)
                        flow = 1.0 - progress  # 100% → 0%
                        
                        gcode_lines.append(
                            self.gcode_gen.move_to(
                                point.x, point.y, point.z,
                                speed=self.settings.wall_speed,
                                extrude=True,
                                flow_multiplier=flow * self.settings.wall_flow_multiplier,
                                layer_height_override=self.settings.layer_height,
                                extrusion_width_override=self.settings.other_layers_extrusion_width,
                            )
                        )
                
                gcode_lines.append("; TAPER_END")

        gcode_lines.extend(self.gcode_gen.generate_footer())
        self.last_generation_metadata = {
            'overhang_report': list(self.last_overhang_report or []),
            'overhang_threshold_deg': float(getattr(self.settings, 'max_overhang_angle_deg', 0.0)),
            'overhang_compensation_applied': bool(self._last_overhang_compensation_points),
            'overhang_compensation_points': int(self._last_overhang_compensation_points),
            'overhang_support_layers': int(getattr(self.settings, 'overhang_support_layers', 0)),
            'overhang_extra_width_factor': clamp(float(getattr(self.settings, 'min_vertical_overlap', 0.0)), 0.0, 1.5),
        }
        return "\n".join(gcode_lines)

    def save_gcode(self, gcode: str, filename: str) -> None:
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write(gcode)

    def generate_gcode_data(self, polydata: Optional[vtk.vtkPolyData], for_visualization: bool = False) -> List[str]:
        original_recentering = self.apply_recentering
        original_center_x = self.settings.print_center_x
        original_center_y = self.settings.print_center_y
        if for_visualization:
            self.apply_recentering = False
            self.settings.print_center_x = 0.0
            self.settings.print_center_y = 0.0
        try:
            gcode_string = self.generate_gcode(polydata)
        finally:
            self.apply_recentering = original_recentering
            self.settings.print_center_x = original_center_x
            self.settings.print_center_y = original_center_y
        return [line for line in (gcode_string or "").split("\n") if line.strip()]


class DefinitiveClayGCodeGenerator(ClayGCodeGenerator):
    """Compatibilidade com o nome legado usado pela interface."""
    pass


def main() -> None:
    settings = ClayPrintSettings()
    generator = ClayGCodeGenerator(settings)

    obj_file = "copos.obj"
    if not os.path.exists(obj_file):
        print(f"Error: {obj_file} not found")
        return

    reader = vtk.vtkOBJReader()
    reader.SetFileName(obj_file)
    reader.Update()
    polydata = reader.GetOutput()

    gcode = generator.generate_gcode(polydata)
    output_file = "clay_orca_style.gcode"
    generator.save_gcode(gcode, output_file)
    print(f"G-code saved to {output_file}")


if __name__ == "__main__":
    main()





