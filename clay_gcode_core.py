from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional

from clay_geometry import EPSILON
from clay_models import Point3D
from clay_settings import ClayPrintSettings


class GCodeGenerator:
    def __init__(self, settings: ClayPrintSettings):
        self.settings = settings
        self.current_position = Point3D(0.0, 0.0, 0.0)
        self.extruder_position = 0.0
        self.extra_offset_x = 0.0
        self.extra_offset_y = 0.0
        self.extra_offset_z = 0.0

    def generate_header(self) -> List[str]:
        header = [
            "; Clay G-code generated with Orca-inspired planner",
            f"; Timestamp: {self._get_timestamp()}",
            f"; Nozzle: {self.settings.nozzle_diameter:.2f} mm",
            f"; Extrusion width: {self.settings.extrusion_width:.2f} mm",
            f"; First layer height: {self.settings.first_layer_height:.3f} mm",
            f"; Layer height: {self.settings.layer_height:.3f} mm",
            f"; Flow rate: {self.settings.flow_rate:.3f}",
            f"; Preset: {self.settings.preset_name}",
            "",
            "G90 ; absolute positioning",
            "G21 ; metric units",
            "M83 ; relative extrusion",
        ]
        if self.settings.enable_pressure_advance and self.settings.pressure_advance > 0.0:
            header.append(f"M900 K{self.settings.pressure_advance:.4f}")
        header.extend([
            f"M204 S{self.settings.acceleration:.0f} ; set acceleration",
            "G92 E0",
            f"G1 F{self.settings.travel_speed:.0f}",
            "",
            "; Move to print center at 5mm height",
            f"G1 X{self.settings.print_center_x:.3f} Y{self.settings.print_center_y:.3f} Z5.000 F{self.settings.travel_speed:.0f}",
            "",
        ])
        return header

    def generate_footer(self) -> List[str]:
        return [
            "",
            "; end of print",
            f"G1 E-{self.settings.retract_length:.3f} F{self.settings.retract_speed:.0f}",
            "G92 E0",
            "G28 Z",
            "M84",
            "M106 S0",
            "; end of file",
        ]

    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        speed: Optional[float] = None,
        extrude: bool = False,
        flow_multiplier: float = 1.0,
        layer_height_override: Optional[float] = None,
        extrusion_width_override: Optional[float] = None,
    ) -> str:
        new_pos = Point3D(x, y, z)
        distance = self.current_position.distance_to(new_pos)
        relative_extrusion = 0.0

        if extrude and distance > 0.0:
            layer_height = self.settings.layer_height if layer_height_override is None else max(EPSILON, layer_height_override)
            extrusion_width = self.settings.extrusion_width if extrusion_width_override is None else max(EPSILON, extrusion_width_override)
            extrusion_area = extrusion_width * layer_height
            volume = distance * extrusion_area
            theoretical = volume / (math.pi * (self.settings.nozzle_diameter / 2.0) ** 2)
            clay_factor = 0.5  # Aumentado de 0.3 para 0.5 (66% mais material)
            relative_extrusion = theoretical * clay_factor
            relative_extrusion *= max(0.0, self.settings.flow_rate) * max(0.0, flow_multiplier)
            self.extruder_position += relative_extrusion

        if speed is None:
            speed = self.settings.print_speed if extrude else self.settings.travel_speed

        if extrude and speed > 0.0:
            layer_height = self.settings.layer_height if layer_height_override is None else max(EPSILON, layer_height_override)
            extrusion_width = self.settings.extrusion_width if extrusion_width_override is None else max(EPSILON, extrusion_width_override)
            area = max(EPSILON, extrusion_width * layer_height)
            volumetric_limit = max(EPSILON, self.settings.max_volumetric_flow_mm3_s)
            flow_factor = max(EPSILON, max(0.0, self.settings.flow_rate) * max(0.0, flow_multiplier))
            max_speed = (volumetric_limit / (area * flow_factor)) * 60.0
            speed = min(speed, max_speed)

        final_x = x + self.extra_offset_x + self.settings.print_center_x
        final_y = y + self.extra_offset_y + self.settings.print_center_y
        final_z = z + self.extra_offset_z

        parts = ["G1", f"X{final_x:.3f}", f"Y{final_y:.3f}", f"Z{final_z:.3f}"]
        if extrude and relative_extrusion > 0.0:
            parts.append(f"E{relative_extrusion:.4f}")
        parts.append(f"F{speed:.0f}")

        self.current_position = new_pos
        return " ".join(parts)

    @staticmethod
    def _get_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["GCodeGenerator"]
