from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import vtk

from clay_geometry import EPSILON, clamp
from clay_models import MeshAnalysis, Point3D
from clay_gcode_core import GCodeGenerator
from clay_mesh import MeshAnalyzer
from clay_settings import ClayPrintSettings


class BaseLayerBuilder:
    def __init__(self, settings: ClayPrintSettings, gcode_gen, mesh_analyzer: MeshAnalyzer):
        self.settings = settings
        self.gcode_gen = gcode_gen
        self.mesh_analyzer = mesh_analyzer

    def _base_edge_inset_for_layer(self, is_first_layer: bool) -> float:
        if not is_first_layer:
            return 0.0

        first_width = float(self.settings.extrusion_width)
        wall_width = float(getattr(self.settings, 'other_layers_extrusion_width', first_width))
        first_height = float(self.settings.first_layer_height)
        wall_height = float(self.settings.layer_height)

        width_spread = max(0.0, first_width - wall_width) * 0.5
        height_spread = max(0.0, first_height - wall_height) * 0.5

        return width_spread + height_spread

    # ------------------------------------------------------------------
    # Base geometry helpers
    # ------------------------------------------------------------------
    def _compute_base_circle(
        self,
        polydata: vtk.vtkPolyData,
        analysis: MeshAnalysis,
    ) -> Tuple[float, float, float]:
        base_z = analysis.base_z
        tol = max(0.02, self.settings.first_layer_height * 0.35)
        pts = polydata.GetPoints()
        base_points: List[Tuple[float, float]] = []
        if pts is not None:
            for idx in range(pts.GetNumberOfPoints()):
                x, y, z = pts.GetPoint(idx)
                if abs(z - base_z) <= tol:
                    base_points.append((x, y))

        def fit_circle(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float, float]]:
            n = len(points)
            if n < 3:
                return None
            sum_x = sum_y = sum_x2 = sum_y2 = sum_xy = 0.0
            sum_x3 = sum_y3 = sum_x2y = sum_xy2 = 0.0
            for x, y in points:
                x2 = x * x
                y2 = y * y
                sum_x += x
                sum_y += y
                sum_x2 += x2
                sum_y2 += y2
                sum_xy += x * y
                sum_x3 += x2 * x
                sum_y3 += y2 * y
                sum_x2y += x2 * y
                sum_xy2 += x * y2
            c = n * sum_x2 - sum_x * sum_x
            d = n * sum_xy - sum_x * sum_y
            e = n * (sum_x3 + sum_xy2) - (sum_x2 + sum_y2) * sum_x
            g = n * sum_y2 - sum_y * sum_y
            h = n * (sum_x2y + sum_y3) - (sum_x2 + sum_y2) * sum_y
            denom = 2.0 * (c * g - d * d)
            if abs(denom) <= 1e-9:
                return None
            cx = (e * g - d * h) / denom
            cy = (c * h - d * e) / denom
            r = math.sqrt((sum_x2 + sum_y2) / n - cx * cx - cy * cy)
            if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)):
                return None
            return cx, cy, max(r, EPSILON)

        if base_points:
            circle = fit_circle(base_points)
            if circle is not None:
                return circle
            cx = sum(px for px, _ in base_points) / len(base_points)
            cy = sum(py for _, py in base_points) / len(base_points)
            radii = sorted(math.hypot(px - cx, py - cy) for px, py in base_points)
            if radii:
                base_radius = radii[int(len(radii) * 0.8)]
                return cx, cy, base_radius

        sample_z = base_z + self.settings.first_layer_height * 0.5
        polygon = self.mesh_analyzer.outer_polygon_at(polydata, sample_z, analysis)
        if polygon is not None:
            coords = list(polygon.exterior.coords)
            if len(coords) >= 3:
                cx = sum(x for x, _ in coords) / len(coords)
                cy = sum(y for _, y in coords) / len(coords)
                radii = [math.hypot(x - cx, y - cy) for x, y in coords]
                if radii:
                    return cx, cy, max(radii)

        bounds = analysis.bounds
        cx = (bounds[0] + bounds[1]) * 0.5
        cy = (bounds[2] + bounds[3]) * 0.5
        base_radius = max(
            math.hypot(px - cx, py - cy)
            for px in (bounds[0], bounds[1])
            for py in (bounds[2], bounds[3])
        ) if bounds else 20.0
        return cx, cy, base_radius

    def _build_archimedean_spiral(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        z: float,
        extrusion_width: float,
    ) -> List[Point3D]:
        spacing = max(0.05, extrusion_width * (1.0 - self.settings.line_overlap))
        clearance = max(0.05, extrusion_width * 0.15)
        target_radius = max(0.0, radius - clearance)
        points: List[Point3D] = [Point3D(center_x, center_y, z)]
        if target_radius <= EPSILON:
            points.append(Point3D(center_x, center_y, z))
            return points

        b = spacing / (2.0 * math.pi)
        theta = 0.0
        min_step = math.radians(0.5)
        max_step = math.radians(10.0)
        for _ in range(20000):
            r = b * theta
            if r >= target_radius:
                r = target_radius
                x = center_x + r * math.cos(theta)
                y = center_y + r * math.sin(theta)
                if math.hypot(x - points[-1].x, y - points[-1].y) > 1e-6:
                    points.append(Point3D(x, y, z))
                break
            x = center_x + r * math.cos(theta)
            y = center_y + r * math.sin(theta)
            if math.hypot(x - points[-1].x, y - points[-1].y) > 1e-6:
                points.append(Point3D(x, y, z))
            step = spacing / max(r, spacing * 0.5)
            step = max(min_step, min(max_step, step))
            theta += step
        else:
            points.append(Point3D(center_x + target_radius, center_y, z))
        return points

    def _generate_base_spiral(
        self,
        base_center_x: float,
        base_center_y: float,
        seam_radius: float,
        z: float,
        outward: bool,
        extrusion_width: float,
    ) -> Tuple[List[Point3D], Point3D, Point3D, float]:
        seam_point = Point3D(base_center_x + seam_radius, base_center_y, z)
        spiral_points = self._build_archimedean_spiral(base_center_x, base_center_y, seam_radius, z, extrusion_width)
        if not spiral_points:
            return [], seam_point, seam_point, seam_radius
        if outward:
            return spiral_points, spiral_points[-1], seam_point, seam_radius
        
        # Para camada INWARD, queremos manter o sentido de rotação (CCW).
        # A espiral original é CCW Outward (Centro -> Fora).
        # Se apenas invertermos, vira CW Inward (Fora -> Centro).
        # Para ter CCW Inward, precisamos espelhar a espiral invertida (ex: espelhar Y).
        inward_points = []
        for p in reversed(spiral_points):
            # Espelhar Y em relação ao centro para inverter o sentido de rotação de volta para CCW
            new_y = base_center_y - (p.y - base_center_y)
            inward_points.append(Point3D(p.x, new_y, p.z))
            
        return inward_points, inward_points[-1], seam_point, seam_radius

    def _generate_concentric_path(
        self,
        center_x: float,
        center_y: float,
        seam_radius: float,
        z: float,
        extrusion_width: float,
        outward: bool = True,
    ) -> List[Point3D]:
        points: List[Point3D] = [Point3D(center_x, center_y, z)]
        seam_radius = max(EPSILON, seam_radius)

        spacing = max(0.2, extrusion_width * (1.0 - self.settings.line_overlap))
        min_radius = max(spacing * 0.35, extrusion_width * 0.2)

        # Preencher com aneis concentricos de dentro para fora (centro -> borda).
        ring_radius = min_radius

        # Conector inicial do centro ate o primeiro anel.
        first_connector_steps = max(4, int(max(min_radius, 0.1) * 3.0))
        for i in range(1, first_connector_steps + 1):
            t = i / first_connector_steps
            r = ring_radius * t
            x = center_x + r
            points.append(Point3D(x, center_y, z))

        while ring_radius <= seam_radius + EPSILON:
            current_radius = min(ring_radius, seam_radius)

            circle_length = 2.0 * math.pi * current_radius
            circle_count = max(72, int(circle_length * 2.5))
            for i in range(1, circle_count + 1):
                angle = (2.0 * math.pi * i) / circle_count
                x = center_x + current_radius * math.cos(angle)
                y = center_y + current_radius * math.sin(angle)
                points.append(Point3D(x, y, z))

            if current_radius >= seam_radius - EPSILON:
                break

            next_radius = min(seam_radius, current_radius + spacing)

            # Conector radial curto para subir ao proximo anel mantendo continuidade.
            connector_steps = max(4, int(max(next_radius - current_radius, 0.1) * 3.0))
            for j in range(1, connector_steps + 1):
                t = j / connector_steps
                r = current_radius + (next_radius - current_radius) * t
                x = center_x + r
                points.append(Point3D(x, center_y, z))

            ring_radius = next_radius

        if not outward:
            points = list(reversed(points))

        return points

    def _generate_filling_arc(
        self,
        base_center_x: float,
        base_center_y: float,
        start_point: Point3D,
        seam_point: Point3D,
        z: float,
        target_z: Optional[float] = None,
    ) -> Tuple[List[Point3D], Point3D]:
        """
        Gera arco de fechamento da base NO MESMO PLANO Z.
        
        IMPORTANTE: Para impressão em argila, o arco permanece no mesmo Z
        para garantir suporte estrutural. A transição vertical acontecerá
        gradualmente nas primeiras voltas da parede helicoidal.
        """
        seam_radius = math.hypot(seam_point.x - base_center_x, seam_point.y - base_center_y)
        arc_points: List[Point3D] = [start_point]
        if seam_radius <= EPSILON:
            return arc_points, seam_point
        
        start_angle = math.atan2(start_point.y - base_center_y, start_point.x - base_center_x)
        end_angle = math.atan2(seam_point.y - base_center_y, seam_point.x - base_center_x)
        angle_span = (end_angle - start_angle) % (2.0 * math.pi)
        if angle_span <= math.radians(1.0):
            angle_span += 2.0 * math.pi
        
        start_radius = math.hypot(start_point.x - base_center_x, start_point.y - base_center_y)
        
        # Calcular número de pontos baseado no comprimento do arco
        arc_length = seam_radius * angle_span
        points_per_mm = 3.0  # 3 pontos por mm para suavidade
        num_points = max(96, int(arc_length * points_per_mm))
        
        for i in range(1, num_points + 1):
            t = i / num_points
            
            # Interpolação suave do ângulo
            angle = start_angle + angle_span * t
            
            # Interpolação suave do raio (usar smoothstep para G2)
            t_smooth = t * t * (3.0 - 2.0 * t)  # cubic hermite
            radius = start_radius + (seam_radius - start_radius) * t_smooth
            
            # Z permanece constante (sem rampa - apoio estrutural)
            x = base_center_x + radius * math.cos(angle)
            y = base_center_y + radius * math.sin(angle)
            arc_points.append(Point3D(x, y, z))
        
        # Garantir que último ponto esteja exatamente no seam_point no mesmo Z
        final_point = Point3D(seam_point.x, seam_point.y, z)
        arc_points[-1] = final_point
        return arc_points, final_point

    def _emit_path(
        self,
        gcode_lines: List[str],
        points: Sequence[Point3D],
        speed: float,
        flow_multiplier: float = 1.0,
        layer_height: Optional[float] = None,
        extrusion_width: Optional[float] = None,
        extrude: bool = True,
        extrude_first: bool = False,
    ) -> None:
        if not points:
            return
        first = points[0]
        gcode_lines.append(
            self.gcode_gen.move_to(
                first.x,
                first.y,
                first.z,
                speed=(speed if extrude and extrude_first else self.settings.travel_speed),
                extrude=(extrude and extrude_first),
                flow_multiplier=flow_multiplier,
                layer_height_override=layer_height,
                extrusion_width_override=extrusion_width,
            )
        )
        for point in points[1:]:
            gcode_lines.append(
                self.gcode_gen.move_to(
                    point.x,
                    point.y,
                    point.z,
                    speed=speed,
                    extrude=extrude,
                    flow_multiplier=flow_multiplier,
                    layer_height_override=layer_height,
                    extrusion_width_override=extrusion_width,
                )
            )

    def _emit_center_point(self, gcode_lines: List[str], cx: float, cy: float, base_z: float, z_target: float) -> None:
        if not self.settings.enable_center_point_extrusion:
            return
        height = max(0.05, self.settings.center_point_height)
        dips = max(1, int(self.settings.center_point_dips))
        gcode_lines.append("; CENTER_POINT_START")

        # Posiciona primeiro em XY (mantendo Z atual), depois move Z em linha separada.
        final_x = cx + self.gcode_gen.extra_offset_x + self.settings.print_center_x
        final_y = cy + self.gcode_gen.extra_offset_y + self.settings.print_center_y
        gcode_lines.append(f"G1 X{final_x:.3f} Y{final_y:.3f} F{self.settings.travel_speed:.0f}")
        self.gcode_gen.current_position = Point3D(cx, cy, self.gcode_gen.current_position.z)
        gcode_lines.append(self.gcode_gen.move_to(cx, cy, base_z, speed=self.settings.travel_speed, extrude=False))

        z_end = base_z + height
        
        # Velocidade mais lenta para o ponto central (30% da velocidade da primeira camada)
        center_point_speed = self.settings.first_layer_speed * 0.3
        # Aumentar fluxo para 150% para compensar a subida vertical
        center_point_flow = 1.5
        
        if dips == 1:
            gcode_lines.append(self.gcode_gen.move_to(
                cx, cy, z_end, 
                speed=center_point_speed, 
                extrude=True, 
                layer_height_override=height,
                flow_multiplier=center_point_flow
            ))
        else:
            # Primeira subida com fluxo reduzido
            gcode_lines.append(self.gcode_gen.move_to(
                cx, cy, z_end, 
                speed=center_point_speed, 
                extrude=True, 
                layer_height_override=height, 
                flow_multiplier=center_point_flow * 0.5
            ))
            gcode_lines.append(self.gcode_gen.move_to(cx, cy, base_z, speed=self.settings.travel_speed, extrude=False))
            # Segunda subida com fluxo completo
            gcode_lines.append(self.gcode_gen.move_to(
                cx, cy, z_end, 
                speed=center_point_speed, 
                extrude=True, 
                layer_height_override=height,
                flow_multiplier=center_point_flow
            ))
        if abs(z_end - z_target) > 1e-6:
            gcode_lines.append(self.gcode_gen.move_to(cx, cy, z_target, speed=self.settings.travel_speed, extrude=False))
        gcode_lines.append("; CENTER_POINT_END")

    def _generate_micro_spiral(self, cx: float, cy: float, z_start: float, z_end: float) -> List[Point3D]:
        if not self.settings.enable_center_micro_spiral:
            return []
        spacing = max(0.05, self.settings.extrusion_width * 0.5)
        max_turns = 3
        theta_step = math.radians(clamp(self.settings.vase_mode_resolution_deg, 0.5, 5.0))
        radius = spacing * 0.2
        points = [Point3D(cx, cy, z_start)]
        theta = math.pi
        
        total_steps = int((2.0 * math.pi * max_turns) / theta_step)
        
        for i in range(total_steps):
            # Interpolação linear de Z
            t = i / max(1, total_steps - 1)
            current_z = z_start + (z_end - z_start) * t
            
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            points.append(Point3D(x, y, current_z))
            theta += theta_step
            radius += spacing * theta_step / (2.0 * math.pi)
            if radius >= spacing * 3.0:
                break
        return points

    def _emit_base_layer(
        self,
        gcode_lines: List[str],
        cx: float,
        cy: float,
        seam_radius: float,
        z: float,
        layer_index: int,
        outward: bool,
        is_first_layer: bool,
        target_z: Optional[float] = None,
        start_z_from: Optional[float] = None,
        previous_end_point: Optional[Point3D] = None,
    ) -> Point3D:
        """
        Emite uma camada de base.
        
        Args:
            target_z: Se fornecido, o arco de fechamento subirá até este Z (fim da camada).
            start_z_from: Se fornecido, a camada começará neste Z e subirá até 'z' (início da camada).
            previous_end_point: Ponto final da camada anterior para garantir continuidade.
        """
        # Definir parâmetros específicos para esta camada
        if is_first_layer:
            current_speed = self.settings.first_layer_speed
            current_layer_height = self.settings.first_layer_height
            current_extrusion_width = self.settings.extrusion_width
            gcode_lines.append(f"; BASE_LAYER_PARAMS: FIRST_LAYER (H={current_layer_height}, W={current_extrusion_width})")
        else:
            current_speed = getattr(self.settings, 'print_speed', self.settings.wall_speed)
            current_layer_height = self.settings.layer_height
            current_extrusion_width = getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
            gcode_lines.append(f"; BASE_LAYER_PARAMS: OTHER_LAYER (H={current_layer_height}, W={current_extrusion_width})")

        # Determinar Z inicial efetivo
        effective_start_z = start_z_from if start_z_from is not None else z

        # Helper para decidir se deve extrudar no primeiro movimento (evitar travel)
        def should_extrude_first(start_pt: Point3D) -> bool:
            if previous_end_point is None:
                return False
            # Se a distância for pequena (ex: < 10mm), fazemos uma ponte extrudada em vez de travel
            dist = math.hypot(start_pt.x - previous_end_point.x, start_pt.y - previous_end_point.y)
            return dist < 10.0

        # Helper para emitir caminho com altura de camada variável (rampa)
        def emit_ramped_path(points_to_emit, start_h, end_h, start_w, end_w, speed, extrude_first_pt):
            if not points_to_emit:
                return
            
            total_pts = len(points_to_emit)
            gcode_lines.append(f"; RAMP_START: H_start={start_h:.3f} H_end={end_h:.3f} W_start={start_w:.3f} W_end={end_w:.3f}")
            
            for i, pt in enumerate(points_to_emit):
                t = i / max(1, total_pts - 1)
                # Interpolação linear da altura da camada
                h = start_h + (end_h - start_h) * t
                # Interpolação linear da largura
                w = start_w + (end_w - start_w) * t
                
                is_first_pt = (i == 0)
                do_extrude = True
                current_spd = speed
                
                if is_first_pt:
                    do_extrude = extrude_first_pt
                    if not extrude_first_pt:
                        current_spd = self.settings.travel_speed
                
                # Debug para verificar valores
                # gcode_lines.append(f"; RAMP_PT {i}: h={h:.3f} w={w:.3f}")

                gcode_lines.append(
                    self.gcode_gen.move_to(
                        pt.x, pt.y, pt.z,
                        speed=current_spd,
                        extrude=do_extrude,
                        flow_multiplier=self.settings.micro_spiral_flow_rate if outward and is_first_layer else 1.0,
                        layer_height_override=h,
                        extrusion_width_override=w,
                    )
                )
            gcode_lines.append("; RAMP_END")

        base_pattern = str(getattr(self.settings, 'base_pattern', 'archimedes')).strip().lower()
        base_direction = str(getattr(self.settings, 'base_direction', 'center_out')).strip().lower()
        outward_selected = (base_direction != 'outside_in')

        if base_pattern == 'concentric':
            concentric_points = self._generate_concentric_path(
                cx, cy, seam_radius, z, current_extrusion_width, outward=outward_selected
            )

            if abs(effective_start_z - z) > 1e-6:
                ramp_pts = min(len(concentric_points), 120)
                for i in range(ramp_pts):
                    t = i / max(1, ramp_pts - 1)
                    concentric_points[i].z = effective_start_z + (z - effective_start_z) * t

            do_extrude = should_extrude_first(concentric_points[0])
            self._emit_path(
                gcode_lines,
                concentric_points,
                current_speed,
                layer_height=current_layer_height,
                extrusion_width=current_extrusion_width,
                extrude_first=do_extrude,
            )
            return concentric_points[-1]

        if outward:
            # Camada OUTWARD (Centro -> Fora)
            
            if is_first_layer:
                micro_points = self._generate_micro_spiral(cx, cy, z, z)
            else:
                micro_points = self._generate_micro_spiral(cx, cy, effective_start_z, z)

            if micro_points:
                gcode_lines.append("; MICRO_SPIRAL_START")
                
                # Snap start point to previous end point if very close to avoid tiny segments
                if previous_end_point is not None:
                    dist = math.hypot(micro_points[0].x - previous_end_point.x, micro_points[0].y - previous_end_point.y)
                    if dist < 0.1: # Aumentei tolerância
                        micro_points[0].x = previous_end_point.x
                        micro_points[0].y = previous_end_point.y
                        # Ajustar Z também para garantir continuidade perfeita
                        micro_points[0].z = previous_end_point.z
                
                do_extrude = should_extrude_first(micro_points[0])
                
                # Se tiver rampa na micro espiral, usar altura variável
                if abs(effective_start_z - z) > 1e-6 and not is_first_layer:
                    # Rampa de H1/W1 (ou anterior) para H2/W2 (atual)
                    prev_h = self.settings.first_layer_height if layer_index == 1 else self.settings.layer_height
                    prev_w = self.settings.extrusion_width if layer_index == 1 else getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
                    
                    emit_ramped_path(micro_points, prev_h, current_layer_height, prev_w, current_extrusion_width, current_speed, do_extrude)
                else:
                    self._emit_path(
                        gcode_lines, 
                        micro_points, 
                        current_speed, 
                        flow_multiplier=self.settings.micro_spiral_flow_rate, 
                        layer_height=current_layer_height,
                        extrusion_width=current_extrusion_width,
                        extrude_first=do_extrude
                    )
                
                gcode_lines.append("; MICRO_SPIRAL_END")
                spiral_start_z = z
                previous_end_point = micro_points[-1]
            else:
                spiral_start_z = effective_start_z
        
            spiral_points, last_point, seam_point, _ = self._generate_base_spiral(
                cx, cy, seam_radius, z, outward, current_extrusion_width
            )
            if not spiral_points:
                raise RuntimeError("failed to build base spiral")
            
            # Aplicar rampa na espiral principal se necessário
            points_in_ramp = 0
            if abs(spiral_start_z - z) > 1e-6 and spiral_points:
                points_in_ramp = 200
                for i in range(min(len(spiral_points), points_in_ramp)):
                    t = i / points_in_ramp
                    spiral_points[i].z = spiral_start_z + (z - spiral_start_z) * t

            gcode_lines.append(f"; MAIN_SPIRAL_START (Layer {layer_index})")
            
            # Snap start point
            if previous_end_point is not None:
                dist = math.hypot(spiral_points[0].x - previous_end_point.x, spiral_points[0].y - previous_end_point.y)
                if dist < 0.1:
                    spiral_points[0].x = previous_end_point.x
                    spiral_points[0].y = previous_end_point.y
                    spiral_points[0].z = previous_end_point.z

            do_extrude = should_extrude_first(spiral_points[0])
            
            if points_in_ramp > 0:
                # Emitir parte da rampa com altura variável
                ramp_part = spiral_points[:points_in_ramp]
                flat_part = spiral_points[points_in_ramp:]
                
                prev_h = self.settings.first_layer_height if layer_index == 1 else self.settings.layer_height
                prev_w = self.settings.extrusion_width if layer_index == 1 else getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
                
                emit_ramped_path(ramp_part, prev_h, current_layer_height, prev_w, current_extrusion_width, current_speed, do_extrude)
                
                # Emitir o resto plano
                if flat_part:
                    # O primeiro ponto do flat_part deve ser extrudado (continuação)
                    self._emit_path(
                        gcode_lines, 
                        flat_part, 
                        current_speed, 
                        layer_height=current_layer_height,
                        extrusion_width=current_extrusion_width,
                        extrude_first=True 
                    )
            else:
                self._emit_path(
                    gcode_lines, 
                    spiral_points, 
                    current_speed, 
                    layer_height=current_layer_height,
                    extrusion_width=current_extrusion_width,
                    extrude_first=do_extrude
                )
            gcode_lines.append("; MAIN_SPIRAL_END")
            
            arc_points, final_seam = self._generate_filling_arc(
                cx, cy, last_point, seam_point, z, target_z
            )
            if arc_points:
                gcode_lines.append("; BASE_ARC_START")
                self._emit_path(
                    gcode_lines, 
                    arc_points, 
                    current_speed, 
                    layer_height=current_layer_height,
                    extrusion_width=current_extrusion_width
                )
                gcode_lines.append("; BASE_ARC_END")
                return arc_points[-1]
            return spiral_points[-1]
        else:
            # Camada INWARD (Fora -> Centro)
            
            spiral_points, last_point, seam_point, _ = self._generate_base_spiral(
                cx, cy, seam_radius, z, outward, current_extrusion_width
            )
            
            tip_point = spiral_points[0]
            
            perimeter_points = []
            num_circle_points = 120
            has_ramp = abs(effective_start_z - z) > 1e-6
            
            # Determinar raio inicial para interpolação (continuidade com camada anterior)
            start_radius = seam_radius
            if has_ramp and previous_end_point is not None:
                # Se estamos rampando da camada anterior, o raio inicial deve casar com o ponto final anterior
                start_radius = math.hypot(previous_end_point.x - cx, previous_end_point.y - cy)

            for i in range(num_circle_points + 1):
                angle = (i / num_circle_points) * 2.0 * math.pi
                
                # Interpolação do raio se houver rampa (para fechar gap com camada anterior)
                if has_ramp:
                    t = i / num_circle_points
                    current_r = start_radius + (seam_radius - start_radius) * t
                    pz = effective_start_z + (z - effective_start_z) * t
                else:
                    current_r = seam_radius
                    pz = z
                
                px = cx + current_r * math.cos(angle)
                py = cy + current_r * math.sin(angle)
                    
                perimeter_points.append(Point3D(px, py, pz))

            arc_points, _ = self._generate_filling_arc(
                cx, cy, perimeter_points[-1], tip_point, z, target_z=None
            )
            
            full_points = []
            # perimeter_points já está em full_points logicamente, mas vamos separar para emitir rampa
            
            gcode_lines.append(f"; INWARD_BASE_LAYER_START (Layer {layer_index})")
            
            # Snap start point (agora deve ser redundante com a interpolação de raio, mas mantemos por segurança)
            if previous_end_point is not None:
                dist = math.hypot(perimeter_points[0].x - previous_end_point.x, perimeter_points[0].y - previous_end_point.y)
                if dist < 0.1: # Aumentei tolerância para garantir snap se estiver próximo
                    perimeter_points[0].x = previous_end_point.x
                    perimeter_points[0].y = previous_end_point.y
                    # Forçar Z do primeiro ponto para ser idêntico ao anterior
                    perimeter_points[0].z = previous_end_point.z

            do_extrude = should_extrude_first(perimeter_points[0])
            
            if has_ramp:
                # Emitir perímetro com altura variável
                prev_h = self.settings.first_layer_height if layer_index == 1 else self.settings.layer_height
                prev_w = self.settings.extrusion_width if layer_index == 1 else getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
                
                emit_ramped_path(perimeter_points, prev_h, current_layer_height, prev_w, current_extrusion_width, current_speed, do_extrude)
            else:
                self._emit_path(
                    gcode_lines, 
                    perimeter_points, 
                    current_speed, 
                    layer_height=current_layer_height,
                    extrusion_width=current_extrusion_width,
                    extrude_first=do_extrude
                )
            
            # Resto do caminho (Arco + Espiral) é plano na altura da camada atual
            rest_points = []
            if arc_points:
                rest_points.extend(arc_points[1:])
            rest_points.extend(spiral_points[1:])
            
            if rest_points:
                self._emit_path(
                    gcode_lines, 
                    rest_points, 
                    current_speed, 
                    layer_height=current_layer_height,
                    extrusion_width=current_extrusion_width,
                    extrude_first=True # Continuação
                )

            gcode_lines.append("; INWARD_BASE_LAYER_END")
            
            return rest_points[-1] if rest_points else perimeter_points[-1]

    def _generate_transition_blend(
        self,
        start_point: Point3D,
        target_point: Point3D,
        center_x: float,
        center_y: float,
    ) -> List[Point3D]:
        """
        Gera blend 3D suave (spiral blend) entre ponto final da base e início da parede.
        Garante continuidade G1 (tangente) com preferência para G2 (curvatura).
        """
        dx = target_point.x - start_point.x
        dy = target_point.y - start_point.y
        dz = target_point.z - start_point.z
        distance_xy = math.hypot(dx, dy)
        
        # Se pontos já estão muito próximos, não precisa blend
        if distance_xy < EPSILON and abs(dz) < EPSILON:
            return [start_point, target_point]
        
        # Número de pontos baseado na distância (mínimo 8 para suavidade)
        num_points = max(8, int(distance_xy / max(0.1, self.settings.extrusion_width * 0.5)))
        blend_points: List[Point3D] = [start_point]
        
        # Usar interpolação cubic-hermite para suavidade G2
        start_radius = math.hypot(start_point.x - center_x, start_point.y - center_y)
        target_radius = math.hypot(target_point.x - center_x, target_point.y - center_y)
        start_angle = math.atan2(start_point.y - center_y, start_point.x - center_x)
        target_angle = math.atan2(target_point.y - center_y, target_point.x - center_x)
        
        # Normalizar diferença angular
        angle_diff = (target_angle - start_angle) % (2.0 * math.pi)
        if angle_diff > math.pi:
            angle_diff -= 2.0 * math.pi
        
        for i in range(1, num_points + 1):
            t = i / num_points
            # Interpolação suave usando smoothstep (cubic hermite)
            t_smooth = t * t * (3.0 - 2.0 * t)
            
            # Transição suave de raio (exponencial para G2)
            if abs(target_radius - start_radius) > EPSILON:
                radius = start_radius * math.exp(math.log(target_radius / max(start_radius, EPSILON)) * t_smooth)
            else:
                radius = start_radius
            
            # Transição angular suave
            angle = start_angle + angle_diff * t_smooth
            
            # Transição Z linear (já suave por natureza)
            z = start_point.z + dz * t
            
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            blend_points.append(Point3D(x, y, z))
        
        # Garantir que o último ponto seja exatamente o target
        blend_points[-1] = target_point
        return blend_points

    def _generate_skirt(
        self,
        center_x: float,
        center_y: float,
        base_radius: float,
        z: float,
    ) -> List[Point3D]:
        """
        Gera saia (skirt) de meia volta para carregar o extrusor.
        Diâmetro = base_radius + 10mm
        Meia volta (π radianos) começando no ângulo 0.
        """
        skirt_radius = base_radius + 10.0  # 10mm maior que a base
        
        # Meia volta = π radianos
        angle_span = math.pi
        
        # Número de pontos baseado no comprimento do arco
        arc_length = skirt_radius * angle_span
        points_per_mm = 3.0  # 3 pontos por mm para suavidade
        num_points = max(48, int(arc_length * points_per_mm))
        
        skirt_points: List[Point3D] = []
        
        for i in range(num_points + 1):
            t = i / num_points
            angle = angle_span * t  # 0 → π
            
            x = center_x + skirt_radius * math.cos(angle)
            y = center_y + skirt_radius * math.sin(angle)
            skirt_points.append(Point3D(x, y, z))
        
        return skirt_points

    def generate_base(
        self,
        gcode_lines: List[str],
        analysis: MeshAnalysis,
        polydata: vtk.vtkPolyData,
    ) -> Point3D:
        cx, cy, initial_base_radius = self._compute_base_circle(polydata, analysis)
        base_layers = self.settings.base_layers_count if self.settings.base_layers_count in (1, 3, 5) else 1
        
        # A base começa NA altura da primeira camada (não em Z=0)
        # O bico precisa estar na altura correta para depositar material
        z0 = analysis.base_z + self.settings.first_layer_height

        # Calcular raio inicial para a saia (baseado na primeira camada)
        skirt_base_radius = initial_base_radius
        polygon_for_seam = self.mesh_analyzer.outer_polygon_at(polydata, z0, analysis)
        if polygon_for_seam is not None:
            seam_xy = self.mesh_analyzer.point_on_polygon_at_angle(polygon_for_seam, (cx, cy), 0.0)
            if seam_xy is not None:
                skirt_base_radius = math.hypot(seam_xy[0] - cx, seam_xy[1] - cy)

        # SAIA: Meia volta com diâmetro +10mm para carregar extrusor
        skirt_points = self._generate_skirt(cx, cy, skirt_base_radius, z0)
        if skirt_points:
            gcode_lines.append("; SKIRT_START")
            speed = self.settings.first_layer_speed
            self._emit_path(
                gcode_lines, 
                skirt_points, 
                speed, 
                flow_multiplier=1.0,  # 100% de extrusão
                layer_height=self.settings.first_layer_height,
                extrusion_width=self.settings.extrusion_width,  # 1ª camada
                extrude=True
            )
            gcode_lines.append("; SKIRT_END")

        self._emit_center_point(gcode_lines, cx, cy, analysis.base_z, z0)

        # Calcular alturas Z explicitamente
        layer_zs = []
        # Camada 1 (Index 0): Base Z + Altura da 1ª camada
        layer_zs.append(z0)
        
        # Camadas subsequentes: Z anterior + Altura de camada padrão
        current_z = z0
        for _ in range(1, base_layers):
            current_z += self.settings.layer_height
            layer_zs.append(current_z)

        base_direction = str(getattr(self.settings, 'base_direction', 'center_out')).strip().lower()
        outward_selected = (base_direction != 'outside_in')
        patterns = [(i, outward_selected) for i in range(base_layers)]

        # Inicializar como None para garantir que o primeiro movimento da base seja TRAVEL (sem extrusão)
        # vindo do Skirt ou Home, evitando "risco" de extrusão diagonal.
        last_point = None
        
        previous_layer_z = z0

        for idx, (layer_index, outward) in enumerate(patterns):
            z = layer_zs[layer_index]
            is_first = (idx == 0)
            
            # Calcular raio específico para esta altura Z
            current_radius = initial_base_radius
            polygon_at_z = self.mesh_analyzer.outer_polygon_at(polydata, z, analysis)
            
            if polygon_at_z is not None:
                # Usar ângulo 0 para medir raio (consistente com a lógica de costura)
                seam_xy = self.mesh_analyzer.point_on_polygon_at_angle(polygon_at_z, (cx, cy), 0.0)
                if seam_xy is not None:
                    current_radius = math.hypot(seam_xy[0] - cx, seam_xy[1] - cy)
            elif layer_index == 0:
                 # Fallback para primeira camada se falhar (já calculado antes como skirt_base_radius)
                 current_radius = skirt_base_radius

            # Offset de extrusão
            width_for_offset = self.settings.extrusion_width if idx == 0 else getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width)
            offset_radius = width_for_offset * 0.5
            base_edge_inset = self._base_edge_inset_for_layer(is_first)
            offset_radius += base_edge_inset
            effective_radius_at_z = max(EPSILON, current_radius - offset_radius)

            if base_edge_inset > EPSILON:
                gcode_lines.append(
                    f"; BASE_EDGE_COMPENSATION layer={layer_index + 1} inset={base_edge_inset:.3f}mm "
                    f"(first_h={self.settings.first_layer_height:.3f}, wall_h={self.settings.layer_height:.3f}, "
                    f"first_w={self.settings.extrusion_width:.3f}, wall_w={getattr(self.settings, 'other_layers_extrusion_width', self.settings.extrusion_width):.3f})"
                )

            # Determinar Z de início para rampa.
            # Opcional: limitar a rampa apenas à primeira transição (camada 1 -> 2).
            ramp_only_first_transition = bool(getattr(self.settings, 'base_ramp_only_first_transition', False))
            if is_first:
                start_z = z
            elif ramp_only_first_transition:
                start_z = previous_layer_z if idx == 1 else z
            else:
                start_z = previous_layer_z

            # Arco de fechamento permanece no mesmo Z (sem rampa)
            last_point = self._emit_base_layer(
                gcode_lines, cx, cy, effective_radius_at_z, z, layer_index, outward, 
                is_first_layer=is_first,
                target_z=None,
                start_z_from=start_z,
                previous_end_point=last_point
            )
            
            previous_layer_z = z
        if last_point is None:
            return Point3D(cx, cy, z0)
        return last_point


__all__ = ["BaseLayerBuilder"]
