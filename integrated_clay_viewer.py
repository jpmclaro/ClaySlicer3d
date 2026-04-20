#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Visualizador 3D Integrado com Simulação de G-code para Argila
Interface única que mostra objeto 3D + simulação do percurso + opção de salvar
"""

import sys
import os
import math
import vtk
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from control_panel_widget import ControlPanelWidget
from preset_service import PresetService
from simulation_service import SimulationService
from vtk_viewport import ClayVTKViewport
from clay_gcode_generator_definitive import ClayPrintSettings, DefinitiveClayGCodeGenerator
from clay_geometry_utils import (
    separate_micro_spiral_points,
    create_path_geometry,
    create_extrusion_actor,
    create_variable_height_tube,
    create_taper_geometry_with_linear_reduction,
    create_continuous_extrusion_cord,
    create_interpolated_segment_tube,
)
from clay_presets_manager import GCodeGenerationDialog, PresetsEditorDialog


class IntegratedClayViewer(QMainWindow):
    """Visualizador integrado: objeto 3D + simulação + controles."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador 3D + Simulação de Impressão em Argila")
        self.setGeometry(100, 100, 1600, 1000)

        self.current_actor = None
        self.current_filename = ""
        self.current_polydata = None
        self.gcode_data = []
        self.simulation_actors = []
        self.gcode_settings = ClayPrintSettings()

        self.preset_service = PresetService()
        self.simulation_service = SimulationService(self)
        self._preset_dirty = False
        self.overhang_report = []

        self._setup_layout()
        self._bind_control_panel_handles()
        self._initialize_presets()
        self._connect_control_panel_signals()
        self._connect_simulation_service_signals()
        self._sync_ui_from_settings()

    def _setup_layout(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.control_panel = ControlPanelWidget(self.gcode_settings, self)

        self.vtk_viewport = ClayVTKViewport(self)
        self.vtk_widget = self.vtk_viewport.widget
        self.renderer = self.vtk_viewport.renderer

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.control_panel)
        self.splitter.addWidget(self.vtk_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([480, 1120])
        self.splitter.setCollapsible(0, False)
        self.splitter.setHandleWidth(10)

        main_layout.addWidget(self.splitter)

    def _bind_control_panel_handles(self) -> None:
        cp = self.control_panel
        handles = [
            'load_button', 'file_info', 'settings_tabs', 'panel_preset_combo',
            'panel_offset_x', 'panel_offset_y', 'panel_nozzle_diameter',
            'panel_flow_rate', 'panel_max_vol_flow', 'panel_micro_flow_rate',
            'panel_enable_center_point', 'panel_enable_micro_spiral',
            'panel_center_point_w', 'panel_center_point_h', 'panel_center_point_dips',
            'panel_base_layers_combo', 'panel_base_pattern_combo', 'panel_base_direction_combo', 'panel_enable_pa', 'panel_pa_value',
            'edit_presets_btn', 'save_preset_btn', 'preset_status_label',
            'speed_first_layer_label', 'speed_other_layers_label',
            'speed_travel_label', 'width_spinbox', 'other_width_spinbox',
            'first_layer_height_spinbox', 'height_spinbox', 'quality_base_layers_combo',
            'height_transition_spin', 'panel_ramp_only_first_transition_cb', 'panel_transition_flow_factor', 'ratio_info', 'panel_enable_taper',
            'panel_taper_turns', 'panel_enable_overhang', 'panel_min_overlap',
            'panel_overhang_support_layers', 'panel_max_overhang_angle',
            'config_button', 'simulate_button',
            'progress_bar', 'sim_info', 'view_overhangs_btn', 'show_object_cb', 'show_path_cb',
            'transparency_slider', 'front_button', 'top_button', 'right_button',
            'left_button', 'bottom_button', 'back_button', 'reset_view_button',
            'save_button', 'acceleration_spinbox', 'enable_nonplanar_cb',
            'algo_group_bg', 'rb_algo1', 'rb_algo2', 'rb_algo3',
            'nonplanar_angular_step', 'nonplanar_angle_threshold', 'nonplanar_z_epsilon',
            'panel_enable_parametric_mode', 'panel_parametric_type_combo',
            'panel_parametric_sharp_corners', 'panel_parametric_transition_len',
            'panel_parametric_base_transition_radius',
            'panel_parametric_arc_layer_height',
            'panel_parametric_wall_layer_height',
            'panel_parametric_curve_mode_combo', 'panel_parametric_curve_strength',
            'panel_parametric_max_overhang', 'panel_parametric_seam_angle',
            'panel_parametric_enable_taper', 'panel_parametric_taper_turns',
            'panel_plate_base_diameter',
            'panel_plate_top_diameter', 'panel_plate_wall_height',
            'panel_cup_base_diameter', 'panel_cup_top_diameter', 'panel_cup_height',
            'panel_jar_base_diameter', 'panel_jar_max_body_diameter', 'panel_jar_body_height',
            'panel_jar_top_diameter', 'panel_jar_neck_height',
            'panel_bottle_base_diameter', 'panel_bottle_body_height',
            'panel_bottle_body_top_diameter', 'panel_bottle_neck_diameter',
            'panel_bottle_neck_height', 'panel_bottle_shoulder_height',
            'panel_mid1_enabled', 'panel_mid1_height', 'panel_mid1_radius',
            'panel_mid2_enabled', 'panel_mid2_height', 'panel_mid2_radius',
        ]
        for name in handles:
            setattr(self, name, getattr(cp, name))

    def _connect_control_panel_signals(self) -> None:
        self.load_button.clicked.connect(self.load_file)
        self.edit_presets_btn.clicked.connect(self.open_presets_editor)
        self.panel_preset_combo.currentIndexChanged.connect(self.on_main_panel_preset_changed)
        self.config_button.clicked.connect(self.configure_printing)
        self.simulate_button.clicked.connect(self.generate_simulation)
        self.save_button.clicked.connect(self.save_gcode)
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        self.view_overhangs_btn.clicked.connect(self.show_overhang_report)

        # Sincronização bidirecional entre os controles de taper da aba Qualidade e da aba Paramétrico
        self.panel_enable_taper.toggled.connect(self.panel_parametric_enable_taper.setChecked)
        self.panel_parametric_enable_taper.toggled.connect(self.panel_enable_taper.setChecked)
        self.panel_taper_turns.valueChanged.connect(self.panel_parametric_taper_turns.setValue)
        self.panel_parametric_taper_turns.valueChanged.connect(self.panel_taper_turns.setValue)

        value_widgets = [
            self.panel_offset_x, self.panel_offset_y, self.panel_flow_rate,
            self.panel_max_vol_flow, self.panel_micro_flow_rate,
            self.panel_center_point_w, self.panel_center_point_h,
            self.panel_center_point_dips, self.panel_pa_value,
            self.panel_taper_turns, self.panel_min_overlap,
            self.panel_overhang_support_layers,
            self.panel_max_overhang_angle, self.height_transition_spin,
            self.panel_transition_flow_factor,
            self.acceleration_spinbox, self.nonplanar_angular_step,
            self.nonplanar_angle_threshold, self.nonplanar_z_epsilon,
            self.panel_parametric_transition_len, self.panel_parametric_base_transition_radius,
            self.panel_parametric_arc_layer_height,
            self.panel_parametric_wall_layer_height,
            self.panel_parametric_curve_strength,
            self.panel_parametric_max_overhang,
            self.panel_parametric_seam_angle,
            self.panel_parametric_taper_turns,
            self.panel_plate_base_diameter, self.panel_plate_top_diameter, self.panel_plate_wall_height,
            self.panel_cup_base_diameter, self.panel_cup_top_diameter, self.panel_cup_height,
            self.panel_jar_base_diameter, self.panel_jar_max_body_diameter, self.panel_jar_body_height,
            self.panel_jar_top_diameter, self.panel_jar_neck_height,
            self.panel_bottle_base_diameter, self.panel_bottle_body_height,
            self.panel_bottle_body_top_diameter, self.panel_bottle_neck_diameter,
            self.panel_bottle_neck_height, self.panel_bottle_shoulder_height,
            self.panel_mid1_height, self.panel_mid1_radius,
            self.panel_mid2_height, self.panel_mid2_radius,
        ]
        for widget in value_widgets:
            widget.valueChanged.connect(self.apply_main_panel_controls)

        toggle_widgets = [
            self.panel_enable_center_point, self.panel_enable_micro_spiral,
            self.panel_enable_pa, self.panel_enable_taper,
            self.panel_enable_overhang, self.enable_nonplanar_cb,
            self.panel_ramp_only_first_transition_cb, self.panel_enable_parametric_mode,
            self.panel_parametric_sharp_corners, self.panel_parametric_enable_taper,
            self.panel_mid1_enabled, self.panel_mid2_enabled,
        ]
        for widget in toggle_widgets:
            widget.toggled.connect(self.apply_main_panel_controls)

        for radio in (self.rb_algo1, self.rb_algo2, self.rb_algo3):
            radio.toggled.connect(self.apply_main_panel_controls)

        self.panel_base_layers_combo.currentIndexChanged.connect(self.apply_main_panel_controls)
        self.panel_base_pattern_combo.currentIndexChanged.connect(self.apply_main_panel_controls)
        self.panel_base_direction_combo.currentIndexChanged.connect(self.apply_main_panel_controls)
        self.panel_parametric_type_combo.currentIndexChanged.connect(self.apply_main_panel_controls)
        self.panel_parametric_curve_mode_combo.currentIndexChanged.connect(self.apply_main_panel_controls)
        self.quality_base_layers_combo.currentIndexChanged.connect(self.sync_base_layers_from_quality)

        geometry_widgets = [
            self.width_spinbox,
            self.other_width_spinbox,
            self.first_layer_height_spinbox,
            self.height_spinbox,
        ]
        for widget in geometry_widgets:
            widget.valueChanged.connect(self.update_extrusion_geometry)

        self.show_object_cb.toggled.connect(self.toggle_object_visibility)
        self.show_path_cb.toggled.connect(self.toggle_path_visibility)
        self.transparency_slider.valueChanged.connect(self.update_transparency)

        self.front_button.clicked.connect(lambda: self.set_quick_view("front"))
        self.back_button.clicked.connect(lambda: self.set_quick_view("back"))
        self.left_button.clicked.connect(lambda: self.set_quick_view("left"))
        self.right_button.clicked.connect(lambda: self.set_quick_view("right"))
        self.top_button.clicked.connect(lambda: self.set_quick_view("top"))
        self.bottom_button.clicked.connect(lambda: self.set_quick_view("bottom"))
        self.reset_view_button.clicked.connect(self.reset_view)

    def _mark_preset_dirty(self, dirty: bool) -> None:
        self._preset_dirty = dirty
        if not hasattr(self, 'preset_status_label'):
            return
        presets = getattr(self, 'panel_presets', [])
        if not presets:
            self.preset_status_label.setText("Preset livre")
            self.preset_status_label.setStyleSheet("color: #34495e; font-size: 10px;")
            return
        if dirty:
            self.preset_status_label.setText("Preset modificado")
            self.preset_status_label.setStyleSheet("color: #c0392b; font-size: 10px;")
        else:
            self.preset_status_label.setText("Preset sincronizado")
            self.preset_status_label.setStyleSheet("color: #27ae60; font-size: 10px;")

    def _connect_simulation_service_signals(self) -> None:
        self.simulation_service.progress.connect(self.progress_bar.setValue)
        self.simulation_service.finished.connect(self.on_simulation_finished)
        self.simulation_service.error.connect(self.on_simulation_error)
        self.simulation_service.running_changed.connect(self._on_simulation_running_changed)

    def _initialize_presets(self, presets: Optional[list] = None) -> None:
        try:
            self.panel_presets = presets if presets is not None else self.preset_service.load_presets()
        except Exception:
            self.panel_presets = []
        self.panel_preset_combo.blockSignals(True)
        self.panel_preset_combo.clear()
        for preset in self.panel_presets:
            self.panel_preset_combo.addItem(preset.get('name', 'Preset'))
        self.panel_preset_combo.blockSignals(False)
        if self.panel_presets:
            self.panel_preset_combo.setCurrentIndex(0)
            self.on_main_panel_preset_changed(0)
        else:
            self.panel_preset_combo.addItem("Atual (painel)")
        self._mark_preset_dirty(False)

    def sync_base_layers_from_quality(self):
        """Sincroniza camadas da base a partir da aba Qualidade"""
        try:
            layers = int(self.quality_base_layers_combo.currentText())
            self.gcode_settings.base_layers_count = layers
            
            # Sincronizar com o combo do painel Global se existir
            if hasattr(self, 'panel_base_layers_combo'):
                idx = {1: 0, 3: 1, 5: 2}.get(layers, 0)
                self.panel_base_layers_combo.blockSignals(True)
                self.panel_base_layers_combo.setCurrentIndex(idx)
                self.panel_base_layers_combo.blockSignals(False)
        except Exception:
            pass

    def _on_simulation_running_changed(self, running: bool) -> None:
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setValue(0)

        has_source = bool(self.current_polydata) or bool(
            getattr(self.gcode_settings, 'enable_parametric_mode', False)
        )
        self.simulate_button.setEnabled(has_source and not running)

    def _sync_ui_from_settings(self) -> None:
        s = self.gcode_settings

        def _set_value(widget, value):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

        def _set_checked(widget, value):
            widget.blockSignals(True)
            widget.setChecked(bool(value))
            widget.blockSignals(False)

        _set_value(self.panel_nozzle_diameter, s.nozzle_diameter)
        _set_value(self.panel_flow_rate, s.flow_rate)
        _set_value(self.panel_micro_flow_rate, s.micro_spiral_flow_rate)
        _set_value(self.panel_max_vol_flow, getattr(s, 'max_volumetric_flow_mm3_s', 30.0))
        _set_checked(self.panel_enable_pa, getattr(s, 'enable_pressure_advance', False))
        _set_value(self.panel_pa_value, s.pressure_advance)
        _set_checked(self.panel_enable_center_point, getattr(s, 'enable_center_point_extrusion', False))
        _set_checked(self.panel_enable_micro_spiral, getattr(s, 'enable_center_micro_spiral', True))
        _set_value(self.panel_center_point_w, getattr(s, 'center_point_width', s.extrusion_width))
        _set_value(self.panel_center_point_h, getattr(s, 'center_point_height', s.first_layer_height))
        _set_value(self.panel_center_point_dips, getattr(s, 'center_point_dips', 2))
        _set_value(self.panel_offset_x, getattr(s, 'print_center_x', 0.0))
        _set_value(self.panel_offset_y, getattr(s, 'print_center_y', 0.0))

        idx = {1: 0, 3: 1, 5: 2}.get(getattr(s, 'base_layers_count', 1), 0)
        self.panel_base_layers_combo.blockSignals(True)
        self.panel_base_layers_combo.setCurrentIndex(idx)
        self.panel_base_layers_combo.blockSignals(False)
        self.quality_base_layers_combo.blockSignals(True)
        self.quality_base_layers_combo.setCurrentIndex(idx)
        self.quality_base_layers_combo.blockSignals(False)
        self.panel_base_pattern_combo.blockSignals(True)
        current_base_pattern = str(getattr(s, 'base_pattern', 'archimedes')).strip().lower()
        self.panel_base_pattern_combo.setCurrentIndex(1 if current_base_pattern == 'concentric' else 0)
        self.panel_base_pattern_combo.blockSignals(False)
        self.panel_base_direction_combo.blockSignals(True)
        current_base_direction = str(getattr(s, 'base_direction', 'center_out')).strip().lower()
        self.panel_base_direction_combo.setCurrentIndex(1 if current_base_direction == 'outside_in' else 0)
        self.panel_base_direction_combo.blockSignals(False)

        _set_value(self.width_spinbox, s.extrusion_width)
        _set_value(self.other_width_spinbox, getattr(s, 'other_layers_extrusion_width', s.extrusion_width))
        _set_value(self.first_layer_height_spinbox, getattr(s, 'first_layer_height', s.layer_height))
        _set_value(self.height_spinbox, s.layer_height)
        _set_value(self.height_transition_spin, getattr(s, 'height_transition_revolutions', 1.0))
        _set_checked(self.panel_ramp_only_first_transition_cb, getattr(s, 'base_ramp_only_first_transition', False))
        _set_value(self.panel_transition_flow_factor, getattr(s, 'transition_blend_flow_factor', 1.0))

        _set_checked(self.panel_enable_taper, getattr(s, 'enable_end_taper', False))
        _set_value(self.panel_taper_turns, getattr(s, 'end_taper_revolutions', 1.0))
        _set_checked(self.panel_parametric_enable_taper, getattr(s, 'enable_end_taper', False))
        _set_value(self.panel_parametric_taper_turns, getattr(s, 'end_taper_revolutions', 1.0))
        _set_checked(self.panel_enable_overhang, getattr(s, 'enable_overhang_compensation', False))
        _set_value(self.panel_min_overlap, getattr(s, 'min_vertical_overlap', 0.6))
        if hasattr(self, 'panel_overhang_support_layers'):
            self.panel_overhang_support_layers.blockSignals(True)
            self.panel_overhang_support_layers.setValue(int(getattr(s, 'overhang_support_layers', 1)))
            self.panel_overhang_support_layers.blockSignals(False)
        _set_value(self.panel_max_overhang_angle, getattr(s, 'max_overhang_angle_deg', 25.0))

        _set_value(self.acceleration_spinbox, getattr(s, 'acceleration', 500.0))
        _set_checked(self.enable_nonplanar_cb, getattr(s, 'enable_nonplanar_mode', False))
        algo_id = getattr(s, 'nonplanar_algorithm', 1)
        button = self.algo_group_bg.button(algo_id)
        if button:
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)
        _set_value(self.nonplanar_angular_step, getattr(s, 'nonplanar_angular_step_deg', 1.0))
        _set_value(self.nonplanar_angle_threshold, getattr(s, 'nonplanar_angle_threshold_deg', 60.0))
        _set_value(self.nonplanar_z_epsilon, getattr(s, 'nonplanar_z_epsilon', 0.03))

        _set_checked(self.panel_enable_parametric_mode, getattr(s, 'enable_parametric_mode', False))
        parametric_type = str(getattr(s, 'parametric_object_type', 'plate')).strip().lower()
        type_idx = {'plate': 0, 'cup': 1, 'jar': 2, 'bottle': 3}.get(parametric_type, 0)
        self.panel_parametric_type_combo.blockSignals(True)
        self.panel_parametric_type_combo.setCurrentIndex(type_idx)
        self.panel_parametric_type_combo.blockSignals(False)
        _set_checked(self.panel_parametric_sharp_corners, getattr(s, 'parametric_enable_sharp_corners', False))
        _set_value(self.panel_parametric_transition_len, getattr(s, 'parametric_transition_length_mm', 3.0))
        _set_value(self.panel_parametric_base_transition_radius, getattr(s, 'parametric_base_transition_radius_mm', 6.0))
        _set_value(self.panel_parametric_arc_layer_height, getattr(s, 'parametric_arc_layer_height', 0.0))
        _set_value(self.panel_parametric_wall_layer_height, getattr(s, 'parametric_wall_layer_height', 0.0))
        curve_mode = str(getattr(s, 'parametric_base_transition_curve_mode', 'fillet')).strip().lower()
        self.panel_parametric_curve_mode_combo.blockSignals(True)
        self.panel_parametric_curve_mode_combo.setCurrentIndex(1 if curve_mode == 's_curve' else 0)
        self.panel_parametric_curve_mode_combo.blockSignals(False)
        _set_value(self.panel_parametric_curve_strength, getattr(s, 'parametric_base_transition_curve_strength', 0.5))
        _set_value(self.panel_parametric_max_overhang, getattr(s, 'parametric_max_overhang_angle_deg', 25.0))
        _set_value(self.panel_parametric_seam_angle, getattr(s, 'parametric_seam_angle_deg', 0.0))
        _set_value(self.panel_plate_base_diameter, getattr(s, 'plate_base_diameter', 60.0))
        _set_value(self.panel_plate_top_diameter, getattr(s, 'plate_top_diameter', 140.0))
        _set_value(self.panel_plate_wall_height, getattr(s, 'plate_wall_height', 30.0))
        _set_value(self.panel_cup_base_diameter, getattr(s, 'cup_base_diameter', 55.0))
        _set_value(self.panel_cup_top_diameter, getattr(s, 'cup_top_diameter', 85.0))
        _set_value(self.panel_cup_height, getattr(s, 'cup_height', 90.0))
        _set_value(self.panel_jar_base_diameter, getattr(s, 'jar_base_diameter', 55.0))
        _set_value(self.panel_jar_max_body_diameter, getattr(s, 'jar_max_body_diameter', 110.0))
        _set_value(self.panel_jar_body_height, getattr(s, 'jar_body_height', 85.0))
        _set_value(self.panel_jar_top_diameter, getattr(s, 'jar_top_diameter', 70.0))
        _set_value(self.panel_jar_neck_height, getattr(s, 'jar_neck_height', 20.0))
        _set_value(self.panel_bottle_base_diameter, getattr(s, 'bottle_base_diameter', 55.0))
        _set_value(self.panel_bottle_body_height, getattr(s, 'bottle_body_height', 100.0))
        _set_value(self.panel_bottle_body_top_diameter, getattr(s, 'bottle_body_top_diameter', 80.0))
        _set_value(self.panel_bottle_neck_diameter, getattr(s, 'bottle_neck_diameter', 36.0))
        _set_value(self.panel_bottle_neck_height, getattr(s, 'bottle_neck_height', 45.0))
        _set_value(self.panel_bottle_shoulder_height, getattr(s, 'bottle_shoulder_height', 20.0))
        _set_checked(self.panel_mid1_enabled, getattr(s, 'parametric_mid1_enabled', False))
        _set_value(self.panel_mid1_height, getattr(s, 'parametric_mid1_height', 30.0))
        _set_value(self.panel_mid1_radius, getattr(s, 'parametric_mid1_radius', 40.0))
        _set_checked(self.panel_mid2_enabled, getattr(s, 'parametric_mid2_enabled', False))
        _set_value(self.panel_mid2_height, getattr(s, 'parametric_mid2_height', 60.0))
        _set_value(self.panel_mid2_radius, getattr(s, 'parametric_mid2_radius', 45.0))

        if hasattr(self, 'panel_parametric_transition_len'):
            self.panel_parametric_transition_len.setEnabled(
                not bool(getattr(s, 'parametric_enable_sharp_corners', False))
            )
        if hasattr(self, 'panel_parametric_base_transition_radius'):
            self.panel_parametric_base_transition_radius.setEnabled(
                not bool(getattr(s, 'parametric_enable_sharp_corners', False))
            )
        if hasattr(self, 'panel_parametric_arc_layer_height'):
            self.panel_parametric_arc_layer_height.setEnabled(
                not bool(getattr(s, 'parametric_enable_sharp_corners', False))
            )
        if hasattr(self, 'panel_parametric_curve_mode_combo'):
            self.panel_parametric_curve_mode_combo.setEnabled(
                not bool(getattr(s, 'parametric_enable_sharp_corners', False))
            )
        if hasattr(self, 'panel_parametric_curve_strength'):
            self.panel_parametric_curve_strength.setEnabled(
                not bool(getattr(s, 'parametric_enable_sharp_corners', False))
            )
        if hasattr(self.control_panel, '_refresh_parametric_preview'):
            self.control_panel._refresh_parametric_preview()

        self.update_extrusion_geometry()
        self._on_simulation_running_changed(self.simulation_service.is_running())
        self._mark_preset_dirty(False)

    # ===== Painel Principal: Presets e Fluxo =====
    def update_speed_tab_from_preset(self, preset: Optional[dict]) -> None:
        """Atualiza aba de velocidades com dados do preset selecionado."""
        if not hasattr(self, 'speed_first_layer_label'):
            return
        first, other, travel = self.preset_service.format_speed_labels(preset, self.gcode_settings)
        self.speed_first_layer_label.setText(first)
        self.speed_other_layers_label.setText(other)
        self.speed_travel_label.setText(travel)

    def on_main_panel_preset_changed(self, index):
        """Aplica preset selecionado no painel principal"""
        if not self.panel_presets or index < 0 or index >= len(self.panel_presets):
            return
        preset = self.panel_presets[index]
        self.preset_service.apply_to_settings(preset, self.gcode_settings)
        self.update_speed_tab_from_preset(preset)
        self._sync_ui_from_settings()
        self._mark_preset_dirty(False)

    def open_presets_editor(self):
        """Abre o editor de presets (agora em módulo separado)."""
        try:
            current_presets = list(getattr(self, 'panel_presets', []))
            dlg = PresetsEditorDialog(self, self.gcode_settings, current_presets)
            if dlg.exec_():
                updated = dlg.get_presets()
                try:
                    self.preset_service.save_presets(updated)
                except Exception as exc:
                    QMessageBox.critical(self, "Erro", f"Falha ao salvar presets:\n{exc}")
                    return

                self._initialize_presets(updated)
                self._mark_preset_dirty(False)
                QMessageBox.information(self, "Presets", "Presets atualizados com sucesso!")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir editor de presets: {str(e)}")
            import traceback
            traceback.print_exc()

    def save_current_preset(self):
        """Persistir alterações do painel no preset selecionado."""
        if not getattr(self, 'panel_presets', []):
            QMessageBox.information(
                self, "Presets", "Nenhum preset carregado. Use 'Gerenciar presets' para criar ou importar."
            )
            return
        idx = self.panel_preset_combo.currentIndex()
        if idx < 0 or idx >= len(self.panel_presets):
            QMessageBox.warning(self, "Presets", "Selecione um preset válido para atualizar.")
            return
        preset = self.panel_presets[idx]
        try:
            self._update_preset_from_settings(preset)
            self.preset_service.save_presets(self.panel_presets)
            self._mark_preset_dirty(False)
            QMessageBox.information(self, "Presets", f"Preset '{preset.get('name', 'Atual')}' atualizado com sucesso!")
        except Exception as exc:
            QMessageBox.critical(self, "Presets", f"Não foi possível salvar o preset:\n{exc}")

    def _update_preset_from_settings(self, preset: dict) -> None:
        s = self.gcode_settings

        def mm_min_to_mm_s(value):
            try:
                return float(value) / 60.0
            except Exception:
                return 0.0

        preset.update(
            {
                'nozzle_diameter': float(getattr(s, 'nozzle_diameter', 2.5)),
                'extrusion_width': float(getattr(s, 'extrusion_width', 2.5)),
                'other_layers_extrusion_width': float(getattr(s, 'other_layers_extrusion_width', getattr(s, 'extrusion_width', 2.5))),
                'first_layer_height': float(getattr(s, 'first_layer_height', 1.0)),
                'other_layers_height': float(getattr(s, 'layer_height', 1.0)),
                'first_layer_speed_mm_s': mm_min_to_mm_s(getattr(s, 'first_layer_speed', getattr(s, 'print_speed', 600.0))),
                'other_layers_speed_mm_s': mm_min_to_mm_s(getattr(s, 'print_speed', getattr(s, 'wall_speed', 600.0))),
                'travel_speed_mm_s': mm_min_to_mm_s(getattr(s, 'travel_speed', 1200.0)),
                'flow_rate': float(getattr(s, 'flow_rate', 1.0)),
                'max_volumetric_flow_mm3_s': float(getattr(s, 'max_volumetric_flow_mm3_s', 30.0)),
                'micro_spiral_flow_rate': float(getattr(s, 'micro_spiral_flow_rate', 1.0)),
                'pressure_advance': float(getattr(s, 'pressure_advance', 0.0)),
                'enable_pressure_advance': bool(getattr(s, 'enable_pressure_advance', False)),
                'enable_center_point_extrusion': bool(getattr(s, 'enable_center_point_extrusion', False)),
                'enable_center_micro_spiral': bool(getattr(s, 'enable_center_micro_spiral', True)),
                'center_point_width': float(getattr(s, 'center_point_width', getattr(s, 'extrusion_width', 2.5))),
                'center_point_height': float(getattr(s, 'center_point_height', getattr(s, 'first_layer_height', 1.0))),
                'center_point_dips': int(getattr(s, 'center_point_dips', 2)),
                'base_layers_count': int(getattr(s, 'base_layers_count', 1)),
                'base_pattern': str(getattr(s, 'base_pattern', 'archimedes')),
                'base_direction': str(getattr(s, 'base_direction', 'center_out')),
                'base_ramp_only_first_transition': bool(getattr(s, 'base_ramp_only_first_transition', False)),
                'print_center_x': float(getattr(s, 'print_center_x', 0.0)),
                'print_center_y': float(getattr(s, 'print_center_y', 0.0)),
                'acceleration': float(getattr(s, 'acceleration', 500.0)),
                'height_transition_revolutions': float(getattr(s, 'height_transition_revolutions', 1.0)),
                'transition_blend_flow_factor': float(getattr(s, 'transition_blend_flow_factor', 1.0)),
                'enable_end_taper': bool(getattr(s, 'enable_end_taper', False)),
                'end_taper_revolutions': float(getattr(s, 'end_taper_revolutions', 1.0)),
                'enable_overhang_compensation': bool(getattr(s, 'enable_overhang_compensation', False)),
                'min_vertical_overlap': float(getattr(s, 'min_vertical_overlap', 0.6)),
                'overhang_support_layers': int(getattr(s, 'overhang_support_layers', 1)),
                'max_overhang_angle_deg': float(getattr(s, 'max_overhang_angle_deg', 25.0)),
                'enable_nonplanar_mode': bool(getattr(s, 'enable_nonplanar_mode', False)),
                'nonplanar_algorithm': int(getattr(s, 'nonplanar_algorithm', 1)),
                'nonplanar_angular_step_deg': float(getattr(s, 'nonplanar_angular_step_deg', 1.0)),
                'nonplanar_angle_threshold_deg': float(getattr(s, 'nonplanar_angle_threshold_deg', 60.0)),
                'nonplanar_z_epsilon': float(getattr(s, 'nonplanar_z_epsilon', 0.03)),
                'enable_parametric_mode': bool(getattr(s, 'enable_parametric_mode', False)),
                'parametric_object_type': str(getattr(s, 'parametric_object_type', 'plate')),
                'parametric_enable_sharp_corners': bool(getattr(s, 'parametric_enable_sharp_corners', False)),
                'parametric_transition_length_mm': float(getattr(s, 'parametric_transition_length_mm', 3.0)),
                'parametric_base_transition_radius_mm': float(getattr(s, 'parametric_base_transition_radius_mm', 6.0)),
                'parametric_arc_layer_height': float(getattr(s, 'parametric_arc_layer_height', 0.0)),
                'parametric_base_transition_curve_mode': str(getattr(s, 'parametric_base_transition_curve_mode', 'fillet')),
                'parametric_base_transition_curve_strength': float(getattr(s, 'parametric_base_transition_curve_strength', 0.5)),
                'parametric_max_overhang_angle_deg': float(getattr(s, 'parametric_max_overhang_angle_deg', 25.0)),
                'parametric_seam_angle_deg': float(getattr(s, 'parametric_seam_angle_deg', 0.0)),
                'plate_base_diameter': float(getattr(s, 'plate_base_diameter', 60.0)),
                'plate_top_diameter': float(getattr(s, 'plate_top_diameter', 140.0)),
                'plate_wall_height': float(getattr(s, 'plate_wall_height', 30.0)),
                'cup_base_diameter': float(getattr(s, 'cup_base_diameter', 55.0)),
                'cup_top_diameter': float(getattr(s, 'cup_top_diameter', 85.0)),
                'cup_height': float(getattr(s, 'cup_height', 90.0)),
                'jar_base_diameter': float(getattr(s, 'jar_base_diameter', 55.0)),
                'jar_max_body_diameter': float(getattr(s, 'jar_max_body_diameter', 110.0)),
                'jar_body_height': float(getattr(s, 'jar_body_height', 85.0)),
                'jar_top_diameter': float(getattr(s, 'jar_top_diameter', 70.0)),
                'jar_neck_height': float(getattr(s, 'jar_neck_height', 20.0)),
                'bottle_base_diameter': float(getattr(s, 'bottle_base_diameter', 55.0)),
                'bottle_body_height': float(getattr(s, 'bottle_body_height', 100.0)),
                'bottle_body_top_diameter': float(getattr(s, 'bottle_body_top_diameter', 80.0)),
                'bottle_neck_diameter': float(getattr(s, 'bottle_neck_diameter', 36.0)),
                'bottle_neck_height': float(getattr(s, 'bottle_neck_height', 45.0)),
                'bottle_shoulder_height': float(getattr(s, 'bottle_shoulder_height', 20.0)),
            }
        )

    def apply_main_panel_controls(self):
        """Aplica valores de fluxo e PA do painel principal às configurações"""
        self.gcode_settings.flow_rate = self.panel_flow_rate.value()
        self.gcode_settings.micro_spiral_flow_rate = self.panel_micro_flow_rate.value()
        self.gcode_settings.enable_pressure_advance = self.panel_enable_pa.isChecked()
        self.gcode_settings.pressure_advance = self.panel_pa_value.value()
        self.gcode_settings.wall_speed = getattr(self.gcode_settings, 'print_speed', self.gcode_settings.wall_speed)
        # Ponto central
        if hasattr(self, 'panel_enable_center_point'):
            self.gcode_settings.enable_center_point_extrusion = bool(self.panel_enable_center_point.isChecked())
        if hasattr(self, 'panel_enable_micro_spiral'):
            self.gcode_settings.enable_center_micro_spiral = bool(self.panel_enable_micro_spiral.isChecked())
        if hasattr(self, 'panel_center_point_w'):
            self.gcode_settings.center_point_width = float(self.panel_center_point_w.value())
        if hasattr(self, 'panel_center_point_h'):
            self.gcode_settings.center_point_height = float(self.panel_center_point_h.value())
        # Limite volumétrico
        if hasattr(self, 'panel_max_vol_flow'):
            self.gcode_settings.max_volumetric_flow_mm3_s = float(self.panel_max_vol_flow.value())
        # Offset do centro (somente para saída do arquivo, visualização continua centrada)
        if hasattr(self, 'panel_offset_x') and hasattr(self, 'panel_offset_y'):
            self.gcode_settings.print_center_x = float(self.panel_offset_x.value())
            self.gcode_settings.print_center_y = float(self.panel_offset_y.value())
        # Taper final (simulação + geração)
        if hasattr(self, 'panel_enable_taper'):
            self.gcode_settings.enable_end_taper = self.panel_enable_taper.isChecked()
        if hasattr(self, 'panel_taper_turns'):
            self.gcode_settings.end_taper_revolutions = float(self.panel_taper_turns.value())
        # Transição de altura
        if hasattr(self, 'height_transition_spin'):
            self.gcode_settings.height_transition_revolutions = float(self.height_transition_spin.value())
        if hasattr(self, 'panel_transition_flow_factor'):
            self.gcode_settings.transition_blend_flow_factor = float(self.panel_transition_flow_factor.value())
        # Compensação de Overhang
        if hasattr(self, 'panel_enable_overhang'):
            self.gcode_settings.enable_overhang_compensation = bool(self.panel_enable_overhang.isChecked())
        if hasattr(self, 'panel_min_overlap'):
            self.gcode_settings.min_vertical_overlap = float(self.panel_min_overlap.value())
        if hasattr(self, 'panel_overhang_support_layers'):
            self.gcode_settings.overhang_support_layers = int(self.panel_overhang_support_layers.value())
        if hasattr(self, 'panel_max_overhang_angle'):
            self.gcode_settings.max_overhang_angle_deg = float(self.panel_max_overhang_angle.value())
        # Camadas da base
        if hasattr(self, 'panel_base_layers_combo'):
            try:
                val = int(self.panel_base_layers_combo.currentText())
                self.gcode_settings.base_layers_count = val
                # Sincronizar com aba Qualidade
                if hasattr(self, 'quality_base_layers_combo'):
                    idx = {1: 0, 3: 1, 5: 2}.get(val, 0)
                    self.quality_base_layers_combo.blockSignals(True)
                    self.quality_base_layers_combo.setCurrentIndex(idx)
                    self.quality_base_layers_combo.blockSignals(False)
            except Exception:
                self.gcode_settings.base_layers_count = 1
        if hasattr(self, 'panel_base_pattern_combo'):
            self.gcode_settings.base_pattern = 'concentric' if self.panel_base_pattern_combo.currentIndex() == 1 else 'archimedes'
        if hasattr(self, 'panel_base_direction_combo'):
            self.gcode_settings.base_direction = 'outside_in' if self.panel_base_direction_combo.currentIndex() == 1 else 'center_out'
        if hasattr(self, 'panel_ramp_only_first_transition_cb'):
            self.gcode_settings.base_ramp_only_first_transition = bool(self.panel_ramp_only_first_transition_cb.isChecked())
        
        # Non-Planar Mode (aba Avançado)
        if hasattr(self, 'enable_nonplanar_cb'):
            self.gcode_settings.enable_nonplanar_mode = bool(self.enable_nonplanar_cb.isChecked())
        if hasattr(self, 'algo_group_bg'):
            self.gcode_settings.nonplanar_algorithm = self.algo_group_bg.checkedId()
        if hasattr(self, 'nonplanar_angular_step'):
            self.gcode_settings.nonplanar_angular_step_deg = float(self.nonplanar_angular_step.value())
        if hasattr(self, 'nonplanar_angle_threshold'):
            self.gcode_settings.nonplanar_angle_threshold_deg = float(self.nonplanar_angle_threshold.value())
        if hasattr(self, 'nonplanar_z_epsilon'):
            self.gcode_settings.nonplanar_z_epsilon = float(self.nonplanar_z_epsilon.value())

        if hasattr(self, 'panel_enable_parametric_mode'):
            self.gcode_settings.enable_parametric_mode = bool(self.panel_enable_parametric_mode.isChecked())
        if hasattr(self, 'panel_parametric_type_combo'):
            obj_map = {0: 'plate', 1: 'cup', 2: 'jar', 3: 'bottle'}
            self.gcode_settings.parametric_object_type = obj_map.get(self.panel_parametric_type_combo.currentIndex(), 'plate')
        if hasattr(self, 'panel_parametric_sharp_corners'):
            self.gcode_settings.parametric_enable_sharp_corners = bool(self.panel_parametric_sharp_corners.isChecked())
        if hasattr(self, 'panel_parametric_transition_len'):
            self.gcode_settings.parametric_transition_length_mm = float(self.panel_parametric_transition_len.value())
        if hasattr(self, 'panel_parametric_base_transition_radius'):
            self.gcode_settings.parametric_base_transition_radius_mm = float(self.panel_parametric_base_transition_radius.value())
        if hasattr(self, 'panel_parametric_arc_layer_height'):
            self.gcode_settings.parametric_arc_layer_height = float(self.panel_parametric_arc_layer_height.value())
        if hasattr(self, 'panel_parametric_wall_layer_height'):
            self.gcode_settings.parametric_wall_layer_height = float(self.panel_parametric_wall_layer_height.value())
        if hasattr(self, 'panel_parametric_curve_mode_combo'):
            self.gcode_settings.parametric_base_transition_curve_mode = 's_curve' if self.panel_parametric_curve_mode_combo.currentIndex() == 1 else 'fillet'
        if hasattr(self, 'panel_parametric_curve_strength'):
            self.gcode_settings.parametric_base_transition_curve_strength = float(self.panel_parametric_curve_strength.value())
        if hasattr(self, 'panel_parametric_max_overhang'):
            self.gcode_settings.parametric_max_overhang_angle_deg = float(self.panel_parametric_max_overhang.value())
        if hasattr(self, 'panel_parametric_seam_angle'):
            self.gcode_settings.parametric_seam_angle_deg = float(self.panel_parametric_seam_angle.value())

        if hasattr(self, 'panel_plate_base_diameter'):
            self.gcode_settings.plate_base_diameter = float(self.panel_plate_base_diameter.value())
        if hasattr(self, 'panel_plate_top_diameter'):
            self.gcode_settings.plate_top_diameter = float(self.panel_plate_top_diameter.value())
        if hasattr(self, 'panel_plate_wall_height'):
            self.gcode_settings.plate_wall_height = float(self.panel_plate_wall_height.value())
        if hasattr(self, 'panel_cup_base_diameter'):
            self.gcode_settings.cup_base_diameter = float(self.panel_cup_base_diameter.value())
        if hasattr(self, 'panel_cup_top_diameter'):
            self.gcode_settings.cup_top_diameter = float(self.panel_cup_top_diameter.value())
        if hasattr(self, 'panel_cup_height'):
            self.gcode_settings.cup_height = float(self.panel_cup_height.value())
        if hasattr(self, 'panel_jar_base_diameter'):
            self.gcode_settings.jar_base_diameter = float(self.panel_jar_base_diameter.value())
        if hasattr(self, 'panel_jar_max_body_diameter'):
            self.gcode_settings.jar_max_body_diameter = float(self.panel_jar_max_body_diameter.value())
        if hasattr(self, 'panel_jar_body_height'):
            self.gcode_settings.jar_body_height = float(self.panel_jar_body_height.value())
        if hasattr(self, 'panel_jar_top_diameter'):
            self.gcode_settings.jar_top_diameter = float(self.panel_jar_top_diameter.value())
        if hasattr(self, 'panel_jar_neck_height'):
            self.gcode_settings.jar_neck_height = float(self.panel_jar_neck_height.value())
        if hasattr(self, 'panel_bottle_base_diameter'):
            self.gcode_settings.bottle_base_diameter = float(self.panel_bottle_base_diameter.value())
        if hasattr(self, 'panel_bottle_body_height'):
            self.gcode_settings.bottle_body_height = float(self.panel_bottle_body_height.value())
        if hasattr(self, 'panel_bottle_body_top_diameter'):
            self.gcode_settings.bottle_body_top_diameter = float(self.panel_bottle_body_top_diameter.value())
        if hasattr(self, 'panel_bottle_neck_diameter'):
            self.gcode_settings.bottle_neck_diameter = float(self.panel_bottle_neck_diameter.value())
        if hasattr(self, 'panel_bottle_neck_height'):
            self.gcode_settings.bottle_neck_height = float(self.panel_bottle_neck_height.value())
        if hasattr(self, 'panel_bottle_shoulder_height'):
            self.gcode_settings.bottle_shoulder_height = float(self.panel_bottle_shoulder_height.value())
        if hasattr(self, 'panel_mid1_enabled'):
            self.gcode_settings.parametric_mid1_enabled = bool(self.panel_mid1_enabled.isChecked())
        if hasattr(self, 'panel_mid1_height'):
            self.gcode_settings.parametric_mid1_height = float(self.panel_mid1_height.value())
        if hasattr(self, 'panel_mid1_radius'):
            self.gcode_settings.parametric_mid1_radius = float(self.panel_mid1_radius.value())
        if hasattr(self, 'panel_mid2_enabled'):
            self.gcode_settings.parametric_mid2_enabled = bool(self.panel_mid2_enabled.isChecked())
        if hasattr(self, 'panel_mid2_height'):
            self.gcode_settings.parametric_mid2_height = float(self.panel_mid2_height.value())
        if hasattr(self, 'panel_mid2_radius'):
            self.gcode_settings.parametric_mid2_radius = float(self.panel_mid2_radius.value())

        self._on_simulation_running_changed(self.simulation_service.is_running())
        
        self._mark_preset_dirty(True)
    def resizeEvent(self, event):
        """Atualiza cubo 3D quando janela redimensiona"""
        super().resizeEvent(event)
        if hasattr(self, 'vtk_viewport'):
            self.vtk_viewport.request_resize_update()
        
    def load_file(self):
        """Carrega arquivo STL/OBJ"""
        file_dialog = QFileDialog()
        filename, _ = file_dialog.getOpenFileName(
            self,
            "Carregar Arquivo 3D",
            "",
            "Arquivos 3D (*.stl *.obj);;STL (*.stl);;OBJ (*.obj);;Todos (*.*)"
        )
        
        if not filename:
            return
            
        try:
            # Guardar tamanhos atuais do splitter para restaurar após carregar
            prev_sizes = self.splitter.sizes() if hasattr(self, 'splitter') else None
            
            # Limpar estado anterior de simulação/visualização
            if hasattr(self, 'simulation_actors'):
                for actor in self.simulation_actors:
                    try:
                        self.renderer.RemoveActor(actor)
                    except Exception:
                        pass
                self.simulation_actors.clear()
            self.gcode_data = []
            if hasattr(self, 'show_path_cb'):
                self.show_path_cb.setChecked(False)
                self.show_path_cb.setEnabled(False)
            if hasattr(self, 'save_button'):
                self.save_button.setEnabled(False)
            if hasattr(self, 'sim_info'):
                self.sim_info.setText("Simulacao nao gerada")
            # Determinar tipo de arquivo e carregar
            if filename.lower().endswith('.stl'):
                reader = vtk.vtkSTLReader()
            elif filename.lower().endswith('.obj'):
                reader = vtk.vtkOBJReader()
            else:
                raise ValueError("Formato não suportado")
                
            reader.SetFileName(filename)
            reader.Update()
            
            self.current_polydata = reader.GetOutput()
            self.current_filename = filename
            
            # Criar visualização do objeto
            self.display_object()
            
            # Atualizar interface
            self.file_info.setText(f"✅ {os.path.basename(filename)}")
            self.config_button.setEnabled(True)
            self.simulate_button.setEnabled(True)
            # Restaurar tamanhos do splitter para garantir que botões fiquem visíveis
            if prev_sizes and len(prev_sizes) == 2:
                self.splitter.setSizes(prev_sizes)
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar arquivo:\n{str(e)}")
            
    def display_object(self):
        """Exibe o objeto 3D com posicionamento sincronizado com o G-code"""
        if self.current_actor:
            self.renderer.RemoveActor(self.current_actor)
            
        # Mapper e actor
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(self.current_polydata)
        
        self.current_actor = vtk.vtkActor()
        self.current_actor.SetMapper(mapper)
        
        # Não aplicar offset na visualização - objeto na posição original
        # O offset será aplicado apenas na saída final do G-code
        
        # Propriedades visuais
        self.current_actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Azul claro
        self.current_actor.GetProperty().SetOpacity(1.0)
        
        self.renderer.AddActor(self.current_actor)
        self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()
        
    def configure_printing(self):
        """Abre diálogo de configuração"""
        dialog = GCodeGenerationDialog(self)
        try:
            dialog.preset_applied.connect(self._on_dialog_preset_applied)
        except Exception:
            pass
        if dialog.exec_() == QDialog.Accepted:
            self.gcode_settings = dialog.get_settings()
            self._sync_ui_from_settings()
            # Atualizar combo de preset se nomes coincidirem
            name = getattr(self.gcode_settings, 'preset_name', '')
            if name and hasattr(self, 'panel_presets'):
                for idx, preset in enumerate(self.panel_presets):
                    if preset.get('name', '') == name:
                        self.panel_preset_combo.blockSignals(True)
                        self.panel_preset_combo.setCurrentIndex(idx)
                        self.panel_preset_combo.blockSignals(False)
                        break
            self.update_object_position()

    def _on_dialog_preset_applied(self, payload: dict):
        """Sincroniza painel principal quando preset muda no diálogo"""
        try:
            self.width_spinbox.setValue(float(payload.get('extrusion_width', self.width_spinbox.value())))
            self.height_spinbox.setValue(float(payload.get('layer_height', self.height_spinbox.value())))
            if hasattr(self, 'panel_nozzle_diameter'):
                self.panel_nozzle_diameter.setValue(float(payload.get('nozzle_diameter', self.panel_nozzle_diameter.value())))
            if hasattr(self, 'panel_flow_rate'):
                self.panel_flow_rate.setValue(float(payload.get('flow_rate', self.panel_flow_rate.value())))
            if hasattr(self, 'panel_micro_flow_rate'):
                self.panel_micro_flow_rate.setValue(float(payload.get('micro_spiral_flow_rate', self.panel_micro_flow_rate.value())))
            if hasattr(self, 'panel_enable_pa') and hasattr(self, 'panel_pa_value'):
                self.panel_enable_pa.setChecked(bool(payload.get('enable_pressure_advance', False)))
                self.panel_pa_value.setEnabled(self.panel_enable_pa.isChecked())
                self.panel_pa_value.setValue(float(payload.get('pressure_advance', self.panel_pa_value.value())))
            self.update_speed_tab_from_preset(payload)
        except Exception:
            pass
            
    def generate_simulation(self):
        """Gera simulação do percurso em memória"""
        if not self.current_polydata and not bool(getattr(self.gcode_settings, 'enable_parametric_mode', False)):
            QMessageBox.information(
                self,
                "Simulação",
                "Carregue um STL/OBJ ou ative o modo paramétrico na aba Objeto Paramétrico.",
            )
            return
        if self.simulation_service.is_running():
            return
        self.overhang_report = []
        self.view_overhangs_btn.setEnabled(False)
        self.sim_info.setText("⏳ Gerando e analisando simulação...")
        self.sim_info.setStyleSheet("color: #7f8c8d; font-style: italic;")
        self.progress_bar.setValue(0)
        self.simulation_service.start(self.current_polydata, self.gcode_settings)
        
    def on_simulation_finished(self, message, gcode_data, metadata=None):
        """Callback quando simulação termina"""
        metadata = metadata or {}
        # Armazenar dados do G-code
        self.gcode_data = gcode_data
        self.overhang_report = metadata.get('overhang_report', [])
        self.view_overhangs_btn.setEnabled(bool(self.overhang_report))
        
        # Reposicionar objeto com as configurações atuais
        if self.current_actor:
            self.display_object()
            # Respeitar o estado do checkbox de visualização
            if hasattr(self, 'show_object_cb'):
                self.current_actor.SetVisibility(self.show_object_cb.isChecked())
        
        # Visualizar percurso
        self.display_gcode_path()
        
        # Atualizar interface
        self._update_overhang_status(len(gcode_data), metadata.get('overhang_threshold_deg'))
        self.show_path_cb.setEnabled(True)
        self.save_button.setEnabled(True)
        
    def on_simulation_error(self, error_message):
        """Callback quando há erro na simulação"""
        QMessageBox.critical(self, "Erro", error_message)

    def show_overhang_report(self):
        if not self.overhang_report:
            QMessageBox.information(
                self,
                "Overhangs",
                "Nenhuma região ultrapassou o ângulo configurado nesta simulação.",
            )
            return
        lines = []
        for idx, segment in enumerate(self.overhang_report, start=1):
            lines.append(
                (
                    f"{idx}. Z {segment.get('start_z', 0.0):.2f}→{segment.get('end_z', 0.0):.2f} mm | "
                    f"Ângulo máx {segment.get('max_angle', 0.0):.1f}° | "
                    f"Extensão {segment.get('length_mm', 0.0):.1f} mm"
                )
            )
            if idx >= 10 and len(self.overhang_report) > 10:
                lines.append(f"... e mais {len(self.overhang_report) - idx} regiões.")
                break
        QMessageBox.information(
            self,
            "Overhangs detectados",
            "\n".join(lines),
        )

    def _update_overhang_status(self, command_count: int, threshold: Optional[float]) -> None:
        threshold = threshold or float(getattr(self.gcode_settings, 'max_overhang_angle_deg', 0.0))
        count = len(self.overhang_report or [])
        if count:
            worst = max((seg.get('max_angle', 0.0) for seg in self.overhang_report), default=0.0)
            self.sim_info.setText(
                f"⚠️ {command_count} comandos | {count} overhangs ≥ {threshold:.0f}° (pico {worst:.1f}°)"
            )
            self.sim_info.setStyleSheet("color: #d35400; font-weight: bold;")
            self.view_overhangs_btn.setEnabled(True)
        else:
            self.sim_info.setText(f"✅ {command_count} comandos gerados")
            self.sim_info.setStyleSheet("color: #2c3e50; font-style: normal;")
            self.view_overhangs_btn.setEnabled(False)
        
    def display_gcode_path(self):
        """Exibe o percurso do G-code com cordão contínuo de extrusão"""
        # Remover simulação anterior
        for actor in self.simulation_actors:
            self.renderer.RemoveActor(actor)
        self.simulation_actors.clear()
        
        if not self.gcode_data:
            return
            
        print("🎬 Gerando cordão contínuo de extrusão...")
        
        # Parâmetros da extrusão (usar configurações atuais)
        extrusion_width = self.gcode_settings.extrusion_width  # mm
        # Altura efetiva para 1ª camada (micro + espiral principal + arco)
        first_h = float(getattr(self.gcode_settings, 'first_layer_height', 1.0))
        other_h = float(self.gcode_settings.layer_height)

        # Para análise textual do perfil nesta visualização, considerar a 1ª camada
        extrusion_height = first_h
        # Determinar tipo de perfil baseado na proporção
        width_height_ratio = extrusion_width / extrusion_height if extrusion_height > 0 else 1.0
        near_circular = abs(width_height_ratio - 1.0) <= 0.05  # 5% de tolerância
        profile_type = "circular" if near_circular else "elíptico REAL"

        print(f"   • Largura: {extrusion_width:.2f}mm")
        print(f"   • Altura: {extrusion_height:.2f}mm") 
        print(f"   • Proporção: {width_height_ratio:.2f}")
        print(f"   • Perfil: {profile_type}")
        
        # Criar cordão contínuo com visualização separada para micro espiral
        try:
            # Separar skirt, ponto central, micro, base+arco e paredes
            skirt_points, center_points, micro_spiral_points, base_arc_points, wall_points, taper_points, base_segments = separate_micro_spiral_points(self.gcode_data)
            
            # SAIA (Skirt) - opcional no preview para não confundir com parede
            if skirt_points and bool(getattr(self.gcode_settings, 'show_skirt_in_preview', False)):
                print(f"🌸 Criando saia (skirt): {len(skirt_points)} pontos")
                skirt_geometry = create_path_geometry(skirt_points, extrusion_width, first_h)
                if skirt_geometry:
                    skirt_actor = create_extrusion_actor(skirt_geometry, color=(0.9, 0.2, 0.6))  # Magenta/Rosa
                    self.simulation_actors.append(skirt_actor)
                    self.renderer.AddActor(skirt_actor)
                    print("✅ Saia magenta criada!")
            elif skirt_points:
                print(f"ℹ️ Skirt ocultado no preview ({len(skirt_points)} pontos)")
            
            # Criar geometrias separadas
            # Ponto central (vermelho)
            if center_points:
                print(f"🔴 Criando ponto central: {len(center_points)} pontos")
                center_h = float(getattr(self.gcode_settings, 'center_point_height', first_h))
                # Aumentar ligeiramente a largura para melhor visibilidade na UI
                center_geometry = create_path_geometry(center_points, extrusion_width * 1.3, center_h)
                if center_geometry:
                    center_actor = create_extrusion_actor(center_geometry, color=(0.9, 0.1, 0.1))  # Vermelho
                    self.simulation_actors.append(center_actor)
                    self.renderer.AddActor(center_actor)
                    # Marcador esférico no topo para garantir visibilidade
                    try:
                        top_pt = center_points[-1]
                        sphere = vtk.vtkSphereSource()
                        sphere.SetRadius(max(0.2, extrusion_width * 0.3))
                        sphere.SetPhiResolution(18)
                        sphere.SetThetaResolution(18)
                        sphere.Update()
                        mapper = vtk.vtkPolyDataMapper()
                        mapper.SetInputConnection(sphere.GetOutputPort())
                        sphere_actor = vtk.vtkActor()
                        sphere_actor.SetMapper(mapper)
                        sphere_actor.GetProperty().SetColor(0.9, 0.1, 0.1)
                        sphere_actor.SetPosition(top_pt[0], top_pt[1], top_pt[2])
                        self.simulation_actors.append(sphere_actor)
                        self.renderer.AddActor(sphere_actor)
                    except Exception:
                        pass
                    print("✅ Ponto central vermelho criado!")

            if micro_spiral_points:
                print(f"🔵 Criando micro espiral: {len(micro_spiral_points)} pontos")
                micro_geometry = create_path_geometry(micro_spiral_points, extrusion_width, first_h)
                if micro_geometry:
                    micro_actor = create_extrusion_actor(micro_geometry, color=(0.1, 0.3, 0.8))  # Azul
                    self.simulation_actors.append(micro_actor)
                    self.renderer.AddActor(micro_actor)
                    print("✅ Micro espiral azul criada!")
            
            # Base + arco (Camadas da base com alturas corretas)
            if base_segments:
                print(f"🟠 Criando base segmentada: {len(base_segments)} segmentos")
                for i, seg in enumerate(base_segments):
                    pts = seg['points']
                    if not pts: continue
                    
                    seg_type = seg.get('type', 'normal')
                    
                    if seg_type == 'ramp':
                        # Segmento de rampa com altura/largura variável
                        h_start = seg.get('h_start', first_h)
                        h_end = seg.get('h_end', first_h)
                        w_start = seg.get('w_start', extrusion_width)
                        w_end = seg.get('w_end', extrusion_width)
                        
                        # Debug info
                        if i < 5 or i == len(base_segments)-1:
                            print(f"   • Base RAMP {i}: {len(pts)} pts, H={h_start:.2f}→{h_end:.2f}mm")
                            
                        # Usar função de interpolação
                        try:
                            from clay_geometry_utils import create_interpolated_segment_tube
                            seg_geometry = create_interpolated_segment_tube(pts, w_start, w_end, h_start, h_end)
                        except ImportError:
                            # Fallback se função não existir (não deveria acontecer)
                            seg_geometry = create_path_geometry(pts, (w_start+w_end)/2, (h_start+h_end)/2)
                    else:
                        # Segmento normal
                        h = seg['height'] if seg['height'] is not None else first_h
                        w = seg['width'] if seg['width'] is not None else extrusion_width
                        
                        # Debug info
                        if i < 5 or i == len(base_segments)-1:
                            print(f"   • Base Seg {i}: {len(pts)} pts, H={h:.2f}mm, W={w:.2f}mm")
                        
                        seg_geometry = create_path_geometry(pts, w, h)

                    if seg_geometry:
                        seg_actor = create_extrusion_actor(seg_geometry, color=(0.8, 0.4, 0.1))  # Laranja
                        self.simulation_actors.append(seg_actor)
                        self.renderer.AddActor(seg_actor)
                print("✅ Base segmentada criada!")
            elif base_arc_points:
                print(f"🟠 Criando base+arco (legacy): {len(base_arc_points)} pontos")
                main_geometry = create_path_geometry(base_arc_points, extrusion_width, first_h)
                if main_geometry:
                    main_actor = create_extrusion_actor(main_geometry, color=(0.8, 0.4, 0.1))  # Laranja
                    self.simulation_actors.append(main_actor)
                    self.renderer.AddActor(main_actor)
                    print("✅ Base+arco laranja criados!")

            # Paredes (demais camadas) com rampa de altura no início
            if wall_points:
                print(f"🟢 Criando paredes: {len(wall_points)} pontos")
                # Calcular Z inicial das paredes (primeiro ponto) e span de transição
                z0_walls = wall_points[0][2]
                trans_turns = float(getattr(self.gcode_settings, 'height_transition_revolutions', 1.0))
                span_z = max(0.0, trans_turns * max(1e-6, other_h))

                # Se temos transição, criar geometria com altura variável nos primeiros pontos
                if span_z > 1e-9:
                    try:
                        # Determinar altura inicial da parede:
                        # Se apenas 1 camada de base, a parede começa com altura da 1ª camada (first_h)
                        # Se mais camadas, a parede começa com altura normal (other_h)
                        base_layers = getattr(self.gcode_settings, 'base_layers_count', 1)
                        wall_start_h = first_h if base_layers == 1 else other_h
                        
                        walls_geometry = create_variable_height_tube(wall_points, extrusion_width, wall_start_h, other_h, z0_walls, span_z)
                    except Exception:
                        walls_geometry = create_path_geometry(wall_points, extrusion_width, other_h)
                else:
                    walls_geometry = create_path_geometry(wall_points, extrusion_width, other_h)

                # NÃO aplicar taper aqui - será renderizado separadamente!
                # (Removido código de taper integrado)

                if walls_geometry:
                    walls_actor = create_extrusion_actor(walls_geometry, color=(0.2, 0.7, 0.2))  # Verde
                    self.simulation_actors.append(walls_actor)
                    self.renderer.AddActor(walls_actor)
                    print("✅ Paredes verdes criadas (com rampa de altura)!")
            
            # TAPER: Percurso independente com cor diferente e ALTURA REDUZINDO
            if taper_points:
                print(f"🟠 Criando taper: {len(taper_points)} pontos")
                
                # CONEXÃO: Se há gap entre walls e taper, adicionar linha de transição
                if wall_points and taper_points:
                    last_wall = wall_points[-1]
                    first_taper = taper_points[0]
                    gap_distance = math.sqrt(
                        (first_taper[0] - last_wall[0])**2 + 
                        (first_taper[1] - last_wall[1])**2 + 
                        (first_taper[2] - last_wall[2])**2
                    )
                    
                    # Se gap > tolerância, criar linha de conexão
                    if gap_distance > 0.1:  # 0.1mm
                        print(f"🔗 Gap detectado ({gap_distance:.3f}mm), criando conexão...")
                        connection_points = [last_wall, first_taper]
                        connection_geometry = create_path_geometry(
                            connection_points, extrusion_width, other_h
                        )
                        if connection_geometry:
                            connection_actor = create_extrusion_actor(
                                connection_geometry, color=(0.9, 0.6, 0.1)  # Mesma cor do taper
                            )
                            self.simulation_actors.append(connection_actor)
                            self.renderer.AddActor(connection_actor)
                            print(f"✅ Conexão criada: {gap_distance:.3f}mm")
                
                # Usar método especial que reduz altura linearmente (100% → 0%)
                taper_geometry = create_taper_geometry_with_linear_reduction(
                    taper_points, extrusion_width, other_h
                )
                if taper_geometry:
                    taper_actor = create_extrusion_actor(taper_geometry, color=(0.9, 0.6, 0.1))  # Laranja
                    self.simulation_actors.append(taper_actor)
                    self.renderer.AddActor(taper_actor)
                    print("✅ Taper laranja criado com altura reduzindo linearmente!")
            
            # Fallback: se não conseguir separar, usar método original
            if not center_points and not micro_spiral_points and not base_arc_points and not wall_points:
                extrusion_geometry = create_continuous_extrusion_cord(self.gcode_data, extrusion_width, first_h)
                if extrusion_geometry and extrusion_geometry.GetNumberOfPoints() > 0:
                    main_actor = create_extrusion_actor(extrusion_geometry, color=(0.8, 0.4, 0.1))
                    self.simulation_actors.append(main_actor)
                    self.renderer.AddActor(main_actor)
                    print("✅ Cordão contínuo de extrusão criado!")

            # Destacar overhangs detectados (independente do modo usado acima)
            self._add_overhang_visuals()

        except Exception as e:
            print(f"❌ Erro na criação do cordão: {e}")
            import traceback
            traceback.print_exc()

        # Ajustar câmera para enquadrar o objeto gerado por inteiro
        self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()

    def _add_overhang_visuals(self) -> None:
        if not getattr(self, 'overhang_report', None):
            return
        base_width = float(getattr(self.gcode_settings, 'other_layers_extrusion_width', self.gcode_settings.extrusion_width))
        layer_height = float(getattr(self.gcode_settings, 'layer_height', 1.0))
        # Fazer o overlay um pouco mais grosso e alto que o percurso principal para evitar ficar oculto
        highlight_width = max(0.7, base_width * 1.3)
        highlight_height = max(0.3, layer_height * 1.1)
        for segment in self.overhang_report:
            pts = segment.get('points')
            if not pts or len(pts) < 2:
                continue
            try:
                geometry = create_path_geometry(pts, highlight_width, highlight_height)
                if not geometry:
                    continue
                actor = create_extrusion_actor(geometry, color=(1.0, 0.85, 0.0))
                prop = actor.GetProperty()
                prop.SetOpacity(0.95)
                prop.SetAmbient(0.5)
                prop.SetDiffuse(0.7)
                self.simulation_actors.append(actor)
                self.renderer.AddActor(actor)
            except Exception:
                continue
        

    

        

        
    def toggle_object_visibility(self, checked):
        """Alterna visibilidade do objeto"""
        if self.current_actor:
            self.current_actor.SetVisibility(checked)
            self.vtk_widget.GetRenderWindow().Render()
            
    def toggle_path_visibility(self, checked):
        """Alterna visibilidade do percurso"""
        for actor in self.simulation_actors:
            actor.SetVisibility(checked)
        self.vtk_widget.GetRenderWindow().Render()
        
    def update_extrusion_geometry(self):
        """Atualiza geometria da extrusão quando parâmetros mudam"""
        # Atualizar configurações
        self.gcode_settings.extrusion_width = self.width_spinbox.value()
        if hasattr(self, 'other_width_spinbox'):
            self.gcode_settings.other_layers_extrusion_width = self.other_width_spinbox.value()
        if hasattr(self, 'first_layer_height_spinbox'):
            self.gcode_settings.first_layer_height = self.first_layer_height_spinbox.value()
        self.gcode_settings.layer_height = self.height_spinbox.value()
        
        # Calcular proporção
        width = self.width_spinbox.value()
        # Considerar altura da 1ª camada para a base
        height = self.first_layer_height_spinbox.value() if hasattr(self, 'first_layer_height_spinbox') else self.height_spinbox.value()
        ratio = width / height
        
        # Determinar tipo de perfil
        profile_type = "Circular" if abs(ratio - 1.0) <= 0.05 else "Elíptico"
            
        # Atualizar info
        self.ratio_info.setText(f"Proporção (L/H): {ratio:.2f} - Perfil: {profile_type}")
        
        # Atualizar posição do objeto para sincronizar
        self.update_object_position()
        
        # Não re-gerar automaticamente a visualização do percurso aqui.
        # A simulação só deve ser atualizada ao clicar em "Gerar Simulacao".
    
    def update_object_position(self):
        """Atualiza posição do objeto 3D para sincronizar com configurações de G-code"""
        if self.current_actor:
            # Não aplicar offset na visualização – manter objeto centrado na origem.
            # O offset é aplicado apenas na exportação do arquivo G-code.
            self.current_actor.SetUserTransform(None)
            self.vtk_widget.GetRenderWindow().Render()
    
    def update_transparency(self, value):
        """Atualiza transparência do objeto"""
        if self.current_actor:
            opacity = (100 - value) / 100.0
            self.current_actor.GetProperty().SetOpacity(opacity)
            self.vtk_widget.GetRenderWindow().Render()
            
    def set_quick_view(self, view_name):
        """Define vista rápida usando o cubo de navegação 3D"""
        if hasattr(self, 'vtk_viewport'):
            self.vtk_viewport.set_quick_view(view_name)
            print(f"📷 Vista alterada para: {view_name}")
    
    def reset_view(self):
        """Reseta a visualização"""
        if hasattr(self, 'vtk_viewport'):
            self.vtk_viewport.reset_view()
        
    def save_gcode(self):
        """Salva o G-code gerado COM offset aplicado (para impressão real)"""
        if not self.current_polydata and not bool(getattr(self.gcode_settings, 'enable_parametric_mode', False)):
            QMessageBox.warning(self, "Aviso", "Nenhum objeto carregado!")
            return
            
        # Diálogo para salvar
        file_dialog = QFileDialog()
        filename, _ = file_dialog.getSaveFileName(
            self,
            "Salvar G-code",
            f"{os.path.splitext(self.current_filename)[0]}_argila.gcode",
            "G-code Files (*.gcode);;All Files (*.*)"
        )
        
        if filename:
            try:
                # Gerar G-code PARA ARQUIVO (com offset aplicado)
                generator = DefinitiveClayGCodeGenerator(self.gcode_settings)
                file_gcode_data = generator.generate_gcode_data(self.current_polydata, for_visualization=False)
                
                # Limpar caracteres especiais do G-code
                clean_gcode_data = []
                for command in file_gcode_data:
                    # Remover caracteres não ASCII se necessário
                    clean_command = command.encode('ascii', 'ignore').decode('ascii')
                    if clean_command.strip():  # Só adicionar se não estiver vazio
                        clean_gcode_data.append(clean_command)
                
                # Salvar com encoding UTF-8
                with open(filename, 'w', encoding='utf-8') as f:
                    for command in clean_gcode_data:
                        f.write(command + '\n')
                        
                QMessageBox.information(
                    self, 
                    "G-code Salvo", 
                    f"Arquivo salvo com sucesso:\n{os.path.basename(filename)}\n\n"
                    f"Total de comandos: {len(clean_gcode_data)}"
                )
                
            except UnicodeError as e:
                QMessageBox.critical(self, "Erro de Codificação", 
                    f"Erro de codificação ao salvar:\n{str(e)}\n\n"
                    f"Tentando salvar com codificação alternativa...")
                
                # Tentar com ASCII puro
                try:
                    with open(filename, 'w', encoding='ascii') as f:
                        for command in self.gcode_data:
                            clean_command = command.encode('ascii', 'ignore').decode('ascii')
                            if clean_command.strip():
                                f.write(clean_command + '\n')
                    
                    QMessageBox.information(self, "Sucesso", "Arquivo salvo com codificação ASCII")
                except Exception as e2:
                    QMessageBox.critical(self, "Erro Crítico", f"Não foi possível salvar:\n{str(e2)}")
                    
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar arquivo:\n{str(e)}")
                
    def closeEvent(self, event):
        """Limpa recursos ao fechar"""
        if hasattr(self, 'simulation_service'):
            self.simulation_service.stop()
        if hasattr(self, 'vtk_viewport'):
            self.vtk_viewport.finalize()
        else:
            self.vtk_widget.Finalize()
        event.accept()


def main():
    """Função principal"""
    # Configura DPI antes de criar QApplication para que primaryScreen().logicalDotsPerInch()
    # retorne o valor correto usado em _apply_compact_style().
    # Sem isso, Qt5 no Windows pode reportar DPIs diferentes dependendo do contexto de
    # inicialização (terminal, atalho, bat), causando layout inconsistente entre execuções.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)   # scaling manual via _apply_compact_style
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)       # ícones/pixmaps nítidos em telas 4K
    app = QApplication(sys.argv)
    app.setApplicationName("Visualizador 3D + Simulação Argila")
    
    viewer = IntegratedClayViewer()
    viewer.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()