import json
import os
from typing import Dict, List, Optional, Tuple

from clay_gcode_generator_definitive import ClayPrintSettings


class PresetService:
    """Lida com carregamento e aplicação de presets de impressão."""

    def __init__(self, presets_path: Optional[str] = None) -> None:
        self.presets_path = presets_path or os.path.join(
            os.path.dirname(__file__), 'printer_presets.json'
        )
        self.presets: List[Dict] = []

    def load_presets(self) -> List[Dict]:
        if os.path.exists(self.presets_path):
            with open(self.presets_path, 'r', encoding='utf-8') as handler:
                data = json.load(handler)
                self.presets = data.get('presets', [])
        else:
            self.presets = []
        return self.presets

    def save_presets(self, presets: List[Dict]) -> None:
        with open(self.presets_path, 'w', encoding='utf-8') as handler:
            json.dump({'presets': presets}, handler, ensure_ascii=False, indent=2)
        self.presets = presets

    def format_speed_labels(
        self,
        preset: Optional[Dict],
        settings: ClayPrintSettings,
    ) -> Tuple[str, str, str]:
        preset = preset or {}

        def _mm_min_to_mm_s(value: float) -> float:
            try:
                return float(value) / 60.0
            except Exception:
                return 0.0

        def _value_from_preset(key: str, fallback: float) -> float:
            try:
                raw = preset.get(key)
                if raw is None:
                    return fallback
                return float(raw)
            except Exception:
                return fallback

        default_first = _mm_min_to_mm_s(getattr(settings, 'first_layer_speed', 600.0))
        default_other = _mm_min_to_mm_s(getattr(settings, 'print_speed', getattr(settings, 'wall_speed', 600.0)))
        default_travel = _mm_min_to_mm_s(getattr(settings, 'travel_speed', 1200.0))

        first_val = _value_from_preset('first_layer_speed_mm_s', default_first)
        other_val = _value_from_preset('other_layers_speed_mm_s', default_other)
        travel_val = _value_from_preset('travel_speed_mm_s', default_travel)

        def _format(val: float) -> str:
            if val <= 0.0:
                return '--'
            return f"{val:.2f} mm/s ({val * 60.0:.0f} mm/min)"

        return _format(first_val), _format(other_val), _format(travel_val)

    def apply_to_settings(self, preset: Dict, settings: ClayPrintSettings) -> None:
        def mm_s_to_mm_min(value) -> int:
            try:
                return int(float(value) * 60.0)
            except Exception:
                return 600

        nozzle = float(preset.get('nozzle_diameter', settings.nozzle_diameter))
        ext_w = float(preset.get('extrusion_width', nozzle))
        other_ext_w = float(preset.get('other_layers_extrusion_width', ext_w))
        first_h = float(preset.get('first_layer_height', settings.first_layer_height))
        other_h = float(preset.get('other_layers_height', settings.layer_height))
        v1 = mm_s_to_mm_min(preset.get('first_layer_speed_mm_s', 10))
        v_other = mm_s_to_mm_min(preset.get('other_layers_speed_mm_s', 20))
        travel_mm_s = preset.get('travel_speed_mm_s')
        v_travel = mm_s_to_mm_min(travel_mm_s) if travel_mm_s is not None else settings.travel_speed
        flow = float(preset.get('flow_rate', settings.flow_rate))
        max_vol = float(preset.get('max_volumetric_flow_mm3_s', getattr(settings, 'max_volumetric_flow_mm3_s', 30.0)))
        micro_flow = float(preset.get('micro_spiral_flow_rate', settings.micro_spiral_flow_rate))
        pa = float(preset.get('pressure_advance', settings.pressure_advance))
        enable_center_pt = bool(preset.get('enable_center_point_extrusion', getattr(settings, 'enable_center_point_extrusion', False)))
        enable_micro_spiral = bool(preset.get('enable_center_micro_spiral', getattr(settings, 'enable_center_micro_spiral', True)))
        acceleration = float(preset.get('acceleration', getattr(settings, 'acceleration', 500.0)))
        center_pt_w = float(preset.get('center_point_width', getattr(settings, 'center_point_width', settings.extrusion_width)))
        center_pt_h = float(preset.get('center_point_height', getattr(settings, 'center_point_height', settings.first_layer_height)))
        center_pt_dips = int(preset.get('center_point_dips', getattr(settings, 'center_point_dips', 2)))
        base_layers = int(preset.get('base_layers_count', getattr(settings, 'base_layers_count', 1)))
        base_pattern = str(preset.get('base_pattern', getattr(settings, 'base_pattern', 'archimedes'))).strip().lower()
        base_direction = str(preset.get('base_direction', getattr(settings, 'base_direction', 'center_out'))).strip().lower()
        enable_overhang = bool(preset.get('enable_overhang_compensation', getattr(settings, 'enable_overhang_compensation', False)))
        overhang_factor = float(preset.get('min_vertical_overlap', getattr(settings, 'min_vertical_overlap', 0.6)))
        overhang_support_layers = int(preset.get('overhang_support_layers', getattr(settings, 'overhang_support_layers', 1)))
        overhang_angle = float(preset.get('max_overhang_angle_deg', getattr(settings, 'max_overhang_angle_deg', 25.0)))
        base_ramp_only_first_transition = bool(
            preset.get('base_ramp_only_first_transition', getattr(settings, 'base_ramp_only_first_transition', False))
        )
        transition_blend_flow_factor = float(
            preset.get('transition_blend_flow_factor', getattr(settings, 'transition_blend_flow_factor', 1.0))
        )
        enable_parametric_mode = bool(
            preset.get('enable_parametric_mode', getattr(settings, 'enable_parametric_mode', False))
        )
        parametric_object_type = str(
            preset.get('parametric_object_type', getattr(settings, 'parametric_object_type', 'plate'))
        ).strip().lower()
        parametric_enable_sharp_corners = bool(
            preset.get('parametric_enable_sharp_corners', getattr(settings, 'parametric_enable_sharp_corners', False))
        )
        parametric_transition_length_mm = float(
            preset.get('parametric_transition_length_mm', getattr(settings, 'parametric_transition_length_mm', 3.0))
        )
        parametric_base_transition_radius_mm = float(
            preset.get('parametric_base_transition_radius_mm', getattr(settings, 'parametric_base_transition_radius_mm', 6.0))
        )
        parametric_base_transition_curve_mode = str(
            preset.get('parametric_base_transition_curve_mode', getattr(settings, 'parametric_base_transition_curve_mode', 'fillet'))
        ).strip().lower()
        parametric_base_transition_curve_strength = float(
            preset.get('parametric_base_transition_curve_strength', getattr(settings, 'parametric_base_transition_curve_strength', 0.5))
        )
        parametric_max_overhang_angle_deg = float(
            preset.get('parametric_max_overhang_angle_deg', getattr(settings, 'parametric_max_overhang_angle_deg', 25.0))
        )
        parametric_seam_angle_deg = float(
            preset.get('parametric_seam_angle_deg', getattr(settings, 'parametric_seam_angle_deg', 0.0))
        )

        plate_base_diameter = float(preset.get('plate_base_diameter', getattr(settings, 'plate_base_diameter', 60.0)))
        plate_top_diameter = float(preset.get('plate_top_diameter', getattr(settings, 'plate_top_diameter', 140.0)))
        plate_wall_height = float(preset.get('plate_wall_height', getattr(settings, 'plate_wall_height', 30.0)))

        cup_base_diameter = float(preset.get('cup_base_diameter', getattr(settings, 'cup_base_diameter', 55.0)))
        cup_top_diameter = float(preset.get('cup_top_diameter', getattr(settings, 'cup_top_diameter', 85.0)))
        cup_height = float(preset.get('cup_height', getattr(settings, 'cup_height', 90.0)))

        jar_base_diameter = float(preset.get('jar_base_diameter', getattr(settings, 'jar_base_diameter', 55.0)))
        jar_max_body_diameter = float(preset.get('jar_max_body_diameter', getattr(settings, 'jar_max_body_diameter', 110.0)))
        jar_body_height = float(preset.get('jar_body_height', getattr(settings, 'jar_body_height', 85.0)))
        jar_top_diameter = float(preset.get('jar_top_diameter', getattr(settings, 'jar_top_diameter', 70.0)))
        jar_neck_height = float(preset.get('jar_neck_height', getattr(settings, 'jar_neck_height', 20.0)))

        bottle_base_diameter = float(preset.get('bottle_base_diameter', getattr(settings, 'bottle_base_diameter', 55.0)))
        bottle_body_height = float(preset.get('bottle_body_height', getattr(settings, 'bottle_body_height', 100.0)))
        bottle_body_top_diameter = float(preset.get('bottle_body_top_diameter', getattr(settings, 'bottle_body_top_diameter', 80.0)))
        bottle_neck_diameter = float(preset.get('bottle_neck_diameter', getattr(settings, 'bottle_neck_diameter', 36.0)))
        bottle_neck_height = float(preset.get('bottle_neck_height', getattr(settings, 'bottle_neck_height', 45.0)))
        bottle_shoulder_height = float(preset.get('bottle_shoulder_height', getattr(settings, 'bottle_shoulder_height', 20.0)))

        settings.nozzle_diameter = nozzle
        settings.extrusion_width = ext_w
        settings.other_layers_extrusion_width = other_ext_w
        settings.first_layer_height = first_h
        settings.layer_height = other_h
        settings.first_layer_speed = v1
        settings.print_speed = v_other
        settings.wall_speed = v_other
        settings.travel_speed = v_travel
        settings.flow_rate = flow
        settings.max_volumetric_flow_mm3_s = max_vol
        settings.micro_spiral_flow_rate = micro_flow
        settings.pressure_advance = pa
        settings.enable_pressure_advance = pa > 0
        settings.preset_name = preset.get('name', '')
        settings.acceleration = acceleration
        settings.enable_center_point_extrusion = enable_center_pt
        settings.enable_center_micro_spiral = enable_micro_spiral
        settings.center_point_width = center_pt_w
        settings.center_point_height = center_pt_h
        settings.center_point_dips = center_pt_dips
        settings.base_layers_count = base_layers
        settings.base_pattern = base_pattern if base_pattern in ('archimedes', 'concentric') else 'archimedes'
        settings.base_direction = base_direction if base_direction in ('center_out', 'outside_in') else 'center_out'
        settings.base_ramp_only_first_transition = base_ramp_only_first_transition
        settings.enable_overhang_compensation = enable_overhang
        settings.min_vertical_overlap = overhang_factor
        settings.overhang_support_layers = overhang_support_layers
        settings.max_overhang_angle_deg = overhang_angle
        settings.transition_blend_flow_factor = transition_blend_flow_factor
        settings.enable_parametric_mode = enable_parametric_mode
        settings.parametric_object_type = parametric_object_type if parametric_object_type in ('plate', 'cup', 'jar', 'bottle') else 'plate'
        settings.parametric_enable_sharp_corners = parametric_enable_sharp_corners
        settings.parametric_transition_length_mm = parametric_transition_length_mm
        settings.parametric_base_transition_radius_mm = parametric_base_transition_radius_mm
        settings.parametric_base_transition_curve_mode = (
            parametric_base_transition_curve_mode if parametric_base_transition_curve_mode in ('fillet', 's_curve') else 'fillet'
        )
        settings.parametric_base_transition_curve_strength = max(0.0, min(1.0, parametric_base_transition_curve_strength))
        settings.parametric_max_overhang_angle_deg = parametric_max_overhang_angle_deg
        settings.parametric_seam_angle_deg = parametric_seam_angle_deg

        settings.plate_base_diameter = plate_base_diameter
        settings.plate_top_diameter = plate_top_diameter
        settings.plate_wall_height = plate_wall_height

        settings.cup_base_diameter = cup_base_diameter
        settings.cup_top_diameter = cup_top_diameter
        settings.cup_height = cup_height

        settings.jar_base_diameter = jar_base_diameter
        settings.jar_max_body_diameter = jar_max_body_diameter
        settings.jar_body_height = jar_body_height
        settings.jar_top_diameter = jar_top_diameter
        settings.jar_neck_height = jar_neck_height

        settings.bottle_base_diameter = bottle_base_diameter
        settings.bottle_body_height = bottle_body_height
        settings.bottle_body_top_diameter = bottle_body_top_diameter
        settings.bottle_neck_diameter = bottle_neck_diameter
        settings.bottle_neck_height = bottle_neck_height
        settings.bottle_shoulder_height = bottle_shoulder_height

        cx = preset.get('print_center_x', preset.get('center_x', settings.print_center_x))
        cy = preset.get('print_center_y', preset.get('center_y', settings.print_center_y))
        try:
            settings.print_center_x = float(cx)
            settings.print_center_y = float(cy)
        except Exception:
            pass
