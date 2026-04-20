from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ParametricProfilePreviewWidget(QWidget):
    """Preview 2D simples do perfil radial (raio x altura) do objeto paramétrico."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._profile_points: list[tuple[float, float]] = []
        self._enabled = False
        self.setMinimumHeight(170)

    def set_profile(self, points: list[tuple[float, float]], enabled: bool) -> None:
        self._profile_points = points or []
        self._enabled = bool(enabled)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        bg = QColor(248, 250, 252)
        border = QColor(205, 215, 225)
        grid = QColor(225, 232, 239)
        axis = QColor(133, 149, 168)
        profile = QColor(35, 120, 212)
        fill = QColor(35, 120, 212, 45)
        txt = QColor(70, 82, 95)

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(rect, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawRoundedRect(rect, 6, 6)

        content = rect.adjusted(36, 14, -14, -30)
        if content.width() <= 20 or content.height() <= 20:
            return

        # Grade
        painter.setPen(QPen(grid, 1.0))
        for i in range(1, 5):
            x = content.left() + (content.width() * i / 5.0)
            y = content.top() + (content.height() * i / 5.0)
            painter.drawLine(int(x), content.top(), int(x), content.bottom())
            painter.drawLine(content.left(), int(y), content.right(), int(y))

        painter.setPen(QPen(axis, 1.2))
        painter.drawLine(content.left(), content.bottom(), content.left(), content.top())
        painter.drawLine(content.left(), content.bottom(), content.right(), content.bottom())

        if not self._enabled:
            painter.setPen(QPen(txt, 1.0))
            painter.drawText(content, Qt.AlignCenter, "Ative o modo paramétrico para ver o perfil")
            return

        if len(self._profile_points) < 2:
            painter.setPen(QPen(txt, 1.0))
            painter.drawText(content, Qt.AlignCenter, "Defina os parâmetros do objeto")
            return

        max_h = max(1e-6, max(z for z, _ in self._profile_points))
        max_r = max(1e-6, max(r for _, r in self._profile_points))

        def map_pt(z_val: float, r_val: float) -> QPointF:
            x = content.left() + (r_val / max_r) * content.width()
            y = content.bottom() - (z_val / max_h) * content.height()
            return QPointF(x, y)

        poly = QPolygonF([map_pt(zv, rv) for zv, rv in self._profile_points])

        # Preenchimento até o eixo Y
        fill_poly = QPolygonF()
        if poly:
            fill_poly.append(QPointF(content.left(), poly[0].y()))
            for p in poly:
                fill_poly.append(p)
            fill_poly.append(QPointF(content.left(), poly[-1].y()))
            fill_poly.append(QPointF(content.left(), poly[0].y()))
            painter.setBrush(fill)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(fill_poly)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(profile, 2.0))
        painter.drawPolyline(poly)

        painter.setPen(QPen(txt, 1.0))
        painter.drawText(QRectF(content.left(), rect.bottom() - 22, content.width(), 18), Qt.AlignCenter, "Raio")
        painter.save()
        painter.translate(rect.left() + 12, content.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-content.height() * 0.5, -8, content.height(), 16), Qt.AlignCenter, "Altura")
        painter.restore()


class ControlPanelWidget(QFrame):
    """Widget responsável por montar o painel de controles do viewer."""

    def __init__(self, gcode_settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlPanelRoot")
        self.gcode_settings = gcode_settings
        self._build_ui()
        self._apply_compact_style()

    def _apply_compact_style(self) -> None:
        # Usa a tela primária que é determinada na criação do QApplication (estável).
        # self.logicalDpiX() é chamado antes do widget ser exibido → valor inconsistente
        # entre execuções no Windows (depende do contexto de inicialização).
        screen = QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen is not None else 96.0
        scale = max(0.85, min(1.8, dpi / 96.0))
        label_pt = max(10, int(round(11 * scale)))
        button_pt = max(9, int(round(10 * scale)))
        tab_pt = max(9, int(round(10 * scale)))
        tab_h = max(24, int(round(28 * scale)))
        tab_vpad = max(3, int(round(4 * scale)))
        tab_hpad = max(8, int(round(10 * scale)))

        base_font = self.font()
        base_font.setPointSize(max(10, int(round(11 * scale))))
        self.setFont(base_font)
        self.setStyleSheet(
            f"""
            #controlPanelRoot QLabel,
            #controlPanelRoot QCheckBox,
            #controlPanelRoot QRadioButton,
            #controlPanelRoot QComboBox,
            #controlPanelRoot QSpinBox,
            #controlPanelRoot QDoubleSpinBox {{
                font-size: {label_pt}pt;
            }}
            #controlPanelRoot QPushButton {{
                font-size: {button_pt}pt;
            }}
            #controlPanelRoot QGroupBox::title {{
                font-size: {label_pt}pt;
            }}
            #controlPanelRoot QTabBar::tab {{
                min-height: {tab_h}px;
                font-size: {tab_pt}pt;
                padding: {tab_vpad}px {tab_hpad}px;
            }}
            """
        )

    def _build_ui(self) -> None:
        self.setFrameStyle(QFrame.StyledPanel)
        self.setMinimumWidth(420)
        self.setMaximumWidth(700)

        layout = QVBoxLayout(self)

        def apply_font(widget: QWidget, size: int = 12, bold: bool = False) -> None:
            font = widget.font()
            font.setPointSize(size)
            font.setBold(bold)
            widget.setFont(font)

        title = QLabel("🏺 Impressão 3D em Argila")
        apply_font(title, 15, True)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: #2c3e50; padding: 10px; background: #ecf0f1; border-radius: 5px;"
        )
        layout.addWidget(title)

        file_group = QGroupBox("1. Carregar Modelo 3D")
        apply_font(file_group, 12, True)
        file_layout = QVBoxLayout(file_group)
        self.load_button = QPushButton("📂 Carregar STL/OBJ")
        file_layout.addWidget(self.load_button)
        self.file_info = QLabel("Nenhum arquivo carregado")
        self.file_info.setStyleSheet("color: #7f8c8d; font-style: italic;")
        file_layout.addWidget(self.file_info)
        layout.addWidget(file_group)

        preset_group = QGroupBox("2. Preset & Materiais")
        apply_font(preset_group, 12, True)
        preset_layout = QVBoxLayout(preset_group)
        combo_row = QHBoxLayout()
        self.panel_preset_combo = QComboBox()
        combo_row.addWidget(self.panel_preset_combo, 1)
        self.preset_status_label = QLabel("Preset sincronizado")
        apply_font(self.preset_status_label, 10)
        self.preset_status_label.setStyleSheet("color: #27ae60;")
        combo_row.addWidget(self.preset_status_label)
        preset_layout.addLayout(combo_row)

        preset_buttons = QHBoxLayout()
        self.save_preset_btn = QPushButton("💾 Atualizar preset")
        preset_buttons.addWidget(self.save_preset_btn)
        self.edit_presets_btn = QPushButton("Gerenciar presets")
        preset_buttons.addWidget(self.edit_presets_btn)
        preset_layout.addLayout(preset_buttons)
        layout.addWidget(preset_group)

        actions_group = QGroupBox("3. Geração e Exportação Rápida")
        apply_font(actions_group, 12, True)
        actions_layout = QVBoxLayout(actions_group)
        buttons_row = QHBoxLayout()
        self.config_button = QPushButton("⚙️ Configurar Impressão")
        self.config_button.setEnabled(False)
        buttons_row.addWidget(self.config_button)
        self.simulate_button = QPushButton("🎬 Gerar Simulação")
        self.simulate_button.setEnabled(False)
        buttons_row.addWidget(self.simulate_button)
        actions_layout.addLayout(buttons_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        actions_layout.addWidget(self.progress_bar)
        self.sim_info = QLabel("Simulacao nao gerada")
        apply_font(self.sim_info, 11)
        self.sim_info.setStyleSheet("color: #7f8c8d; font-style: italic;")
        actions_layout.addWidget(self.sim_info)
        self.view_overhangs_btn = QPushButton("Ver overhangs detectados")
        self.view_overhangs_btn.setEnabled(False)
        actions_layout.addWidget(self.view_overhangs_btn)
        self.save_button = QPushButton("💾 Salvar G-code")
        self.save_button.setEnabled(False)
        actions_layout.addWidget(self.save_button)
        layout.addWidget(actions_group)

        self.settings_tabs = QTabWidget()
        self.settings_tabs.setDocumentMode(True)
        self.settings_tabs.setTabPosition(QTabWidget.West)
        self.settings_tabs.setStyleSheet(
            "QTabBar::tab { min-height: 80px; max-height: 120px; padding: 6px 4px; }"
            "QTabBar::tab:selected { font-weight: bold; }"
        )

        def wrap_scroll(content_widget: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            container = QWidget()
            v = QVBoxLayout(container)
            v.setContentsMargins(8, 8, 8, 8)
            v.addWidget(content_widget)
            v.addStretch(1)
            scroll.setWidget(container)
            return scroll

        def make_speed_label() -> QLabel:
            label = QLabel("--")
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setAlignment(Qt.AlignLeft)
            apply_font(label, 11, True)
            return label

        material_widget = QWidget()
        material_layout = QVBoxLayout(material_widget)
        material_form = QFormLayout()
        self.panel_offset_x = QDoubleSpinBox()
        self.panel_offset_x.setRange(-1000.0, 1000.0)
        self.panel_offset_x.setSingleStep(1.0)
        self.panel_offset_x.setSuffix(" mm")
        self.panel_offset_x.setValue(self.gcode_settings.print_center_x)
        material_form.addRow("Offset X (centro):", self.panel_offset_x)
        self.panel_offset_y = QDoubleSpinBox()
        self.panel_offset_y.setRange(-1000.0, 1000.0)
        self.panel_offset_y.setSingleStep(1.0)
        self.panel_offset_y.setSuffix(" mm")
        self.panel_offset_y.setValue(self.gcode_settings.print_center_y)
        material_form.addRow("Offset Y (centro):", self.panel_offset_y)
        self.panel_nozzle_diameter = QDoubleSpinBox()
        self.panel_nozzle_diameter.setRange(0.2, 20.0)
        self.panel_nozzle_diameter.setValue(self.gcode_settings.nozzle_diameter)
        self.panel_nozzle_diameter.setSuffix(" mm")
        self.panel_nozzle_diameter.setReadOnly(True)
        self.panel_nozzle_diameter.setButtonSymbols(QDoubleSpinBox.NoButtons)
        material_form.addRow("Diâmetro do bico:", self.panel_nozzle_diameter)
        self.panel_flow_rate = QDoubleSpinBox()
        self.panel_flow_rate.setRange(0.10, 3.0)
        self.panel_flow_rate.setSingleStep(0.05)
        self.panel_flow_rate.setValue(self.gcode_settings.flow_rate)
        material_form.addRow("Fluxo global (×):", self.panel_flow_rate)
        self.panel_max_vol_flow = QDoubleSpinBox()
        self.panel_max_vol_flow.setRange(1.0, 500.0)
        self.panel_max_vol_flow.setSingleStep(1.0)
        self.panel_max_vol_flow.setDecimals(1)
        self.panel_max_vol_flow.setValue(
            getattr(self.gcode_settings, 'max_volumetric_flow_mm3_s', 30.0)
        )
        material_form.addRow("Fluxo volumétrico máx. (mm³/s):", self.panel_max_vol_flow)
        self.panel_micro_flow_rate = QDoubleSpinBox()
        self.panel_micro_flow_rate.setRange(0.10, 3.0)
        self.panel_micro_flow_rate.setSingleStep(0.05)
        self.panel_micro_flow_rate.setValue(self.gcode_settings.micro_spiral_flow_rate)
        material_form.addRow("Fluxo micro-espiral (×):", self.panel_micro_flow_rate)
        self.panel_enable_center_point = QCheckBox("Ponto central na base")
        self.panel_enable_center_point.setChecked(
            getattr(self.gcode_settings, 'enable_center_point_extrusion', False)
        )
        material_form.addRow(self.panel_enable_center_point)
        self.panel_enable_micro_spiral = QCheckBox("Micro espiral inicial")
        self.panel_enable_micro_spiral.setChecked(
            getattr(self.gcode_settings, 'enable_center_micro_spiral', True)
        )
        material_form.addRow(self.panel_enable_micro_spiral)
        center_row = QHBoxLayout()
        self.panel_center_point_w = QDoubleSpinBox()
        self.panel_center_point_w.setRange(0.2, 20.0)
        self.panel_center_point_w.setSingleStep(0.1)
        self.panel_center_point_w.setSuffix(" mm")
        self.panel_center_point_w.setValue(
            float(getattr(self.gcode_settings, 'center_point_width', self.gcode_settings.extrusion_width))
        )
        self.panel_center_point_h = QDoubleSpinBox()
        self.panel_center_point_h.setRange(0.1, 10.0)
        self.panel_center_point_h.setSingleStep(0.1)
        self.panel_center_point_h.setSuffix(" mm")
        self.panel_center_point_h.setValue(
            float(getattr(self.gcode_settings, 'center_point_height', self.gcode_settings.first_layer_height))
        )
        self.panel_center_point_w.setEnabled(self.panel_enable_center_point.isChecked())
        self.panel_center_point_h.setEnabled(self.panel_enable_center_point.isChecked())
        self.panel_enable_center_point.toggled.connect(self.panel_center_point_w.setEnabled)
        self.panel_enable_center_point.toggled.connect(self.panel_center_point_h.setEnabled)
        center_row.addWidget(QLabel("Largura:"))
        center_row.addWidget(self.panel_center_point_w)
        center_row.addWidget(QLabel("Altura:"))
        center_row.addWidget(self.panel_center_point_h)
        material_form.addRow(center_row)
        dips_row = QHBoxLayout()
        dips_row.addWidget(QLabel("Mergulhos:"))
        self.panel_center_point_dips = QDoubleSpinBox()
        self.panel_center_point_dips.setDecimals(0)
        self.panel_center_point_dips.setRange(1, 2)
        self.panel_center_point_dips.setSingleStep(1)
        self.panel_center_point_dips.setValue(
            float(getattr(self.gcode_settings, 'center_point_dips', 2))
        )
        self.panel_center_point_dips.setEnabled(self.panel_enable_center_point.isChecked())
        self.panel_enable_center_point.toggled.connect(self.panel_center_point_dips.setEnabled)
        dips_row.addWidget(self.panel_center_point_dips)
        material_form.addRow(dips_row)
        pa_row_main = QHBoxLayout()
        self.panel_enable_pa = QCheckBox("Pressure Advance (M900)")
        self.panel_enable_pa.setChecked(
            getattr(self.gcode_settings, 'enable_pressure_advance', False)
        )
        self.panel_pa_value = QDoubleSpinBox()
        self.panel_pa_value.setRange(0.0, 2.0)
        self.panel_pa_value.setSingleStep(0.01)
        self.panel_pa_value.setDecimals(3)
        self.panel_pa_value.setValue(self.gcode_settings.pressure_advance)
        self.panel_pa_value.setEnabled(self.panel_enable_pa.isChecked())
        self.panel_enable_pa.toggled.connect(self.panel_pa_value.setEnabled)
        pa_row_main.addWidget(self.panel_enable_pa)
        pa_row_main.addWidget(self.panel_pa_value)
        material_form.addRow("Avanço pressão K:", pa_row_main)
        material_layout.addLayout(material_form)

        speed_group = QGroupBox("Velocidades do Preset")
        apply_font(speed_group, 12, True)
        speed_form = QFormLayout(speed_group)
        self.speed_first_layer_label = make_speed_label()
        self.speed_other_layers_label = make_speed_label()
        self.speed_travel_label = make_speed_label()
        speed_form.addRow("Vel. 1ª camada:", self.speed_first_layer_label)
        speed_form.addRow("Vel. demais camadas:", self.speed_other_layers_label)
        speed_form.addRow("Vel. travel:", self.speed_travel_label)
        material_layout.addWidget(speed_group)

        self.settings_tabs.addTab(wrap_scroll(material_widget), "Material/Fluxo")

        extrusion_group = QGroupBox("Geometria da Extrusão")
        apply_font(extrusion_group, 12, True)
        extrusion_layout = QVBoxLayout(extrusion_group)
        extrusion_layout.addWidget(QLabel("Largura da Extrusão:"))
        self.width_spinbox = QDoubleSpinBox()
        self.width_spinbox.setRange(0.5, 10.0)
        self.width_spinbox.setValue(self.gcode_settings.extrusion_width)
        self.width_spinbox.setSuffix(" mm")
        self.width_spinbox.setSingleStep(0.1)
        extrusion_layout.addWidget(self.width_spinbox)
        extrusion_layout.addWidget(QLabel("Largura Demais Camadas:"))
        self.other_width_spinbox = QDoubleSpinBox()
        self.other_width_spinbox.setRange(0.5, 10.0)
        self.other_width_spinbox.setValue(
            getattr(self.gcode_settings, 'other_layers_extrusion_width', 2.5)
        )
        self.other_width_spinbox.setSuffix(" mm")
        self.other_width_spinbox.setSingleStep(0.1)
        extrusion_layout.addWidget(self.other_width_spinbox)
        extrusion_layout.addWidget(QLabel("Altura 1ª Camada:"))
        self.first_layer_height_spinbox = QDoubleSpinBox()
        self.first_layer_height_spinbox.setRange(0.2, 5.0)
        self.first_layer_height_spinbox.setValue(
            getattr(self.gcode_settings, 'first_layer_height', 1.0)
        )
        self.first_layer_height_spinbox.setSuffix(" mm")
        self.first_layer_height_spinbox.setSingleStep(0.1)
        extrusion_layout.addWidget(self.first_layer_height_spinbox)
        extrusion_layout.addWidget(QLabel("Altura Demais Camadas:"))
        self.height_spinbox = QDoubleSpinBox()
        self.height_spinbox.setRange(0.2, 5.0)
        self.height_spinbox.setValue(self.gcode_settings.layer_height)
        self.height_spinbox.setSuffix(" mm")
        self.height_spinbox.setSingleStep(0.1)
        extrusion_layout.addWidget(self.height_spinbox)
        extrusion_layout.addWidget(QLabel("Camadas da Base:"))
        self.quality_base_layers_combo = QComboBox()
        self.quality_base_layers_combo.addItems(["1", "3", "5"])
        try:
            quality_idx = {1: 0, 3: 1, 5: 2}.get(
                int(getattr(self.gcode_settings, 'base_layers_count', 1)), 0
            )
            self.quality_base_layers_combo.setCurrentIndex(quality_idx)
        except Exception:
            self.quality_base_layers_combo.setCurrentIndex(0)
        extrusion_layout.addWidget(self.quality_base_layers_combo)
        base_layers_panel_row = QHBoxLayout()
        base_layers_panel_row.addWidget(QLabel("Camadas (painel Global):"))
        self.panel_base_layers_combo = QComboBox()
        self.panel_base_layers_combo.addItems(["1", "3", "5"])
        try:
            base_layers = int(getattr(self.gcode_settings, 'base_layers_count', 1))
            base_idx = {1: 0, 3: 1, 5: 2}.get(base_layers, 0)
            self.panel_base_layers_combo.setCurrentIndex(base_idx)
        except Exception:
            self.panel_base_layers_combo.setCurrentIndex(0)
        base_layers_panel_row.addWidget(self.panel_base_layers_combo)
        extrusion_layout.addLayout(base_layers_panel_row)
        base_pattern_row = QHBoxLayout()
        base_pattern_row.addWidget(QLabel("Padrao da base:"))
        self.panel_base_pattern_combo = QComboBox()
        self.panel_base_pattern_combo.addItems(["Cordao Arquimedes", "Concentrica"])
        current_base_pattern = str(getattr(self.gcode_settings, 'base_pattern', 'archimedes')).strip().lower()
        self.panel_base_pattern_combo.setCurrentIndex(1 if current_base_pattern == 'concentric' else 0)
        base_pattern_row.addWidget(self.panel_base_pattern_combo)
        extrusion_layout.addLayout(base_pattern_row)

        base_direction_row = QHBoxLayout()
        base_direction_row.addWidget(QLabel("Sentido da base:"))
        self.panel_base_direction_combo = QComboBox()
        self.panel_base_direction_combo.addItems(["Dentro -> Fora", "Fora -> Dentro"])
        current_base_direction = str(getattr(self.gcode_settings, 'base_direction', 'center_out')).strip().lower()
        self.panel_base_direction_combo.setCurrentIndex(1 if current_base_direction == 'outside_in' else 0)
        base_direction_row.addWidget(self.panel_base_direction_combo)
        extrusion_layout.addLayout(base_direction_row)

        trans_row = QHBoxLayout()
        trans_label = QLabel("Transição altura (voltas):")
        self.height_transition_spin = QDoubleSpinBox()
        self.height_transition_spin.setRange(0.0, 5.0)
        self.height_transition_spin.setSingleStep(0.25)
        self.height_transition_spin.setDecimals(2)
        self.height_transition_spin.setValue(
            float(getattr(self.gcode_settings, 'height_transition_revolutions', 1.0))
        )
        trans_row.addWidget(trans_label)
        trans_row.addWidget(self.height_transition_spin)
        extrusion_layout.addLayout(trans_row)
        self.panel_ramp_only_first_transition_cb = QCheckBox("Rampa base só na 1ª transição")
        self.panel_ramp_only_first_transition_cb.setChecked(
            bool(getattr(self.gcode_settings, 'base_ramp_only_first_transition', False))
        )
        extrusion_layout.addWidget(self.panel_ramp_only_first_transition_cb)
        blend_flow_row = QHBoxLayout()
        blend_flow_label = QLabel("Fluxo fino da transicao (x):")
        self.panel_transition_flow_factor = QDoubleSpinBox()
        self.panel_transition_flow_factor.setRange(0.10, 2.00)
        self.panel_transition_flow_factor.setSingleStep(0.05)
        self.panel_transition_flow_factor.setDecimals(2)
        self.panel_transition_flow_factor.setValue(
            float(getattr(self.gcode_settings, 'transition_blend_flow_factor', 1.0))
        )
        blend_flow_row.addWidget(blend_flow_label)
        blend_flow_row.addWidget(self.panel_transition_flow_factor)
        extrusion_layout.addLayout(blend_flow_row)
        self.ratio_info = QLabel("Proporção (L/H): 1.00 - Perfil: Circular")
        apply_font(self.ratio_info, 12, True)
        self.ratio_info.setStyleSheet("color: #2980b9;")
        extrusion_layout.addWidget(self.ratio_info)

        taper_group = QGroupBox("Acabamento (Taper)")
        apply_font(taper_group, 12, True)
        taper_row = QHBoxLayout(taper_group)
        self.panel_enable_taper = QCheckBox("Final suave (taper)")
        self.panel_enable_taper.setChecked(
            getattr(self.gcode_settings, 'enable_end_taper', False)
        )
        self.panel_taper_turns = QDoubleSpinBox()
        self.panel_taper_turns.setRange(0.25, 5.0)
        self.panel_taper_turns.setSingleStep(0.25)
        self.panel_taper_turns.setValue(
            getattr(self.gcode_settings, 'end_taper_revolutions', 1.0)
        )
        self.panel_taper_turns.setSuffix(" voltas")
        self.panel_taper_turns.setEnabled(self.panel_enable_taper.isChecked())
        self.panel_enable_taper.toggled.connect(self.panel_taper_turns.setEnabled)
        taper_row.addWidget(self.panel_enable_taper)
        taper_row.addWidget(self.panel_taper_turns)
        extrusion_layout.addWidget(taper_group)
        self.settings_tabs.addTab(wrap_scroll(extrusion_group), "Qualidade")

        parametric_widget = QWidget()
        parametric_layout = QVBoxLayout(parametric_widget)

        mode_group = QGroupBox("Modo de Geração")
        apply_font(mode_group, 12, True)
        mode_form = QFormLayout(mode_group)
        self.panel_enable_parametric_mode = QCheckBox("Ativar objeto paramétrico (sem STL)")
        self.panel_enable_parametric_mode.setChecked(
            bool(getattr(self.gcode_settings, 'enable_parametric_mode', False))
        )
        mode_form.addRow(self.panel_enable_parametric_mode)

        self.panel_parametric_type_combo = QComboBox()
        self.panel_parametric_type_combo.addItems(["Prato", "Copo", "Jarra", "Garrafa"])
        type_name = str(getattr(self.gcode_settings, 'parametric_object_type', 'plate')).strip().lower()
        type_index = {'plate': 0, 'cup': 1, 'jar': 2, 'bottle': 3}.get(type_name, 0)
        self.panel_parametric_type_combo.setCurrentIndex(type_index)
        mode_form.addRow("Tipo de objeto:", self.panel_parametric_type_combo)

        self.panel_parametric_sharp_corners = QCheckBox("Permitir cantos vivos")
        self.panel_parametric_sharp_corners.setChecked(
            bool(getattr(self.gcode_settings, 'parametric_enable_sharp_corners', False))
        )
        mode_form.addRow(self.panel_parametric_sharp_corners)

        self.panel_parametric_transition_len = QDoubleSpinBox()
        self.panel_parametric_transition_len.setRange(0.0, 30.0)
        self.panel_parametric_transition_len.setSingleStep(0.5)
        self.panel_parametric_transition_len.setSuffix(" mm")
        self.panel_parametric_transition_len.setValue(
            float(getattr(self.gcode_settings, 'parametric_transition_length_mm', 3.0))
        )
        self.panel_parametric_transition_len.setEnabled(not self.panel_parametric_sharp_corners.isChecked())
        self.panel_parametric_sharp_corners.toggled.connect(
            lambda checked: self.panel_parametric_transition_len.setEnabled(not checked)
        )
        mode_form.addRow("Transição de canto:", self.panel_parametric_transition_len)

        self.panel_parametric_base_transition_radius = QDoubleSpinBox()
        self.panel_parametric_base_transition_radius.setRange(0.0, 80.0)
        self.panel_parametric_base_transition_radius.setSingleStep(0.5)
        self.panel_parametric_base_transition_radius.setSuffix(" mm")
        self.panel_parametric_base_transition_radius.setValue(
            float(getattr(self.gcode_settings, 'parametric_base_transition_radius_mm', 6.0))
        )
        self.panel_parametric_base_transition_radius.setEnabled(not self.panel_parametric_sharp_corners.isChecked())
        self.panel_parametric_sharp_corners.toggled.connect(
            lambda checked: self.panel_parametric_base_transition_radius.setEnabled(not checked)
        )
        mode_form.addRow("Raio base → parede:", self.panel_parametric_base_transition_radius)

        self.panel_parametric_arc_layer_height = QDoubleSpinBox()
        self.panel_parametric_arc_layer_height.setRange(0.0, 5.0)
        self.panel_parametric_arc_layer_height.setSingleStep(0.05)
        self.panel_parametric_arc_layer_height.setDecimals(2)
        self.panel_parametric_arc_layer_height.setSuffix(" mm")
        self.panel_parametric_arc_layer_height.setSpecialValueText("Auto")
        self.panel_parametric_arc_layer_height.setValue(
            float(getattr(self.gcode_settings, 'parametric_arc_layer_height', 0.0))
        )
        self.panel_parametric_arc_layer_height.setToolTip(
            "Altura alvo da camada por volta no filete base→parede.\n"
            "0 (Auto) = usa a mesma altura de camada da parede (preset).\n"
            "Valores explícitos sobrescrevem: maior = menos passagens, menor = mais passagens."
        )
        self.panel_parametric_arc_layer_height.setEnabled(not self.panel_parametric_sharp_corners.isChecked())
        self.panel_parametric_sharp_corners.toggled.connect(
            lambda checked: self.panel_parametric_arc_layer_height.setEnabled(not checked)
        )
        mode_form.addRow("Alt. camada no arco:", self.panel_parametric_arc_layer_height)

        self.panel_parametric_wall_layer_height = QDoubleSpinBox()
        self.panel_parametric_wall_layer_height.setRange(0.0, 5.0)
        self.panel_parametric_wall_layer_height.setSingleStep(0.05)
        self.panel_parametric_wall_layer_height.setDecimals(2)
        self.panel_parametric_wall_layer_height.setSuffix(" mm")
        self.panel_parametric_wall_layer_height.setSpecialValueText("Auto")
        self.panel_parametric_wall_layer_height.setValue(
            float(getattr(self.gcode_settings, 'parametric_wall_layer_height', 0.0))
        )
        self.panel_parametric_wall_layer_height.setToolTip(
            "Altura alvo da camada por volta na parede.\n"
            "0 (Auto) = usa a mesma altura de camada da parede (preset).\n"
            "Valores explícitos sobrescrevem: maior = menos passagens, menor = mais passagens."
        )
        mode_form.addRow("Alt. camada na parede:", self.panel_parametric_wall_layer_height)


        self.panel_parametric_curve_mode_combo = QComboBox()
        self.panel_parametric_curve_mode_combo.addItems(["Fillet suave", "Curva S"])
        curve_mode = str(getattr(self.gcode_settings, 'parametric_base_transition_curve_mode', 'fillet')).strip().lower()
        self.panel_parametric_curve_mode_combo.setCurrentIndex(1 if curve_mode == 's_curve' else 0)
        self.panel_parametric_curve_mode_combo.setEnabled(not self.panel_parametric_sharp_corners.isChecked())
        self.panel_parametric_sharp_corners.toggled.connect(
            lambda checked: self.panel_parametric_curve_mode_combo.setEnabled(not checked)
        )
        mode_form.addRow("Perfil da curva:", self.panel_parametric_curve_mode_combo)

        self.panel_parametric_curve_strength = QDoubleSpinBox()
        self.panel_parametric_curve_strength.setRange(0.0, 1.0)
        self.panel_parametric_curve_strength.setSingleStep(0.05)
        self.panel_parametric_curve_strength.setDecimals(2)
        self.panel_parametric_curve_strength.setValue(
            float(getattr(self.gcode_settings, 'parametric_base_transition_curve_strength', 0.5))
        )
        self.panel_parametric_curve_strength.setEnabled(not self.panel_parametric_sharp_corners.isChecked())
        self.panel_parametric_sharp_corners.toggled.connect(
            lambda checked: self.panel_parametric_curve_strength.setEnabled(not checked)
        )
        mode_form.addRow("Intensidade da curva:", self.panel_parametric_curve_strength)

        self.panel_parametric_max_overhang = QDoubleSpinBox()
        self.panel_parametric_max_overhang.setRange(5.0, 85.0)
        self.panel_parametric_max_overhang.setSingleStep(1.0)
        self.panel_parametric_max_overhang.setSuffix(" graus")
        self.panel_parametric_max_overhang.setValue(
            float(getattr(self.gcode_settings, 'parametric_max_overhang_angle_deg', 25.0))
        )
        mode_form.addRow("Overhang máx. no perfil:", self.panel_parametric_max_overhang)

        self.panel_parametric_seam_angle = QDoubleSpinBox()
        self.panel_parametric_seam_angle.setRange(0.0, 360.0)
        self.panel_parametric_seam_angle.setSingleStep(45.0)
        self.panel_parametric_seam_angle.setDecimals(1)
        self.panel_parametric_seam_angle.setSuffix("°")
        self.panel_parametric_seam_angle.setWrapping(True)
        self.panel_parametric_seam_angle.setValue(
            float(getattr(self.gcode_settings, 'parametric_seam_angle_deg', 0.0))
        )
        self.panel_parametric_seam_angle.setToolTip(
            "Posição da costura (ponto inicial da espiral).\n"
            "0° = direita (Leste) | 90° = frente | 180° = esquerda | 270° = trás.\n"
            "Rotaciona toda a geometria em torno do eixo Z."
        )
        mode_form.addRow("Ponto inicial (costura):", self.panel_parametric_seam_angle)

        parametric_layout.addWidget(mode_group)

        taper_param_group = QGroupBox("Acabamento (Taper)")
        apply_font(taper_param_group, 12, True)
        taper_param_row = QHBoxLayout(taper_param_group)
        self.panel_parametric_enable_taper = QCheckBox("Final suave (taper)")
        self.panel_parametric_enable_taper.setChecked(
            getattr(self.gcode_settings, 'enable_end_taper', False)
        )
        self.panel_parametric_taper_turns = QDoubleSpinBox()
        self.panel_parametric_taper_turns.setRange(0.25, 5.0)
        self.panel_parametric_taper_turns.setSingleStep(0.25)
        self.panel_parametric_taper_turns.setValue(
            getattr(self.gcode_settings, 'end_taper_revolutions', 1.0)
        )
        self.panel_parametric_taper_turns.setSuffix(" voltas")
        self.panel_parametric_taper_turns.setEnabled(self.panel_parametric_enable_taper.isChecked())
        self.panel_parametric_enable_taper.toggled.connect(self.panel_parametric_taper_turns.setEnabled)
        taper_param_row.addWidget(self.panel_parametric_enable_taper)
        taper_param_row.addWidget(self.panel_parametric_taper_turns)
        parametric_layout.addWidget(taper_param_group)

        # ── Pontos Intermediários do Perfil ───────────────────────────
        mid_group = QGroupBox("Pontos Intermediários do Perfil")
        apply_font(mid_group, 12, True)
        mid_grid = QGridLayout(mid_group)
        mid_grid.setColumnStretch(1, 1)
        mid_grid.setColumnStretch(2, 1)

        def make_mid_row(idx: int, h_default: float, r_default: float, enabled: bool):
            cb = QCheckBox(f"Ponto {idx}")
            cb.setChecked(enabled)
            h_spin = QDoubleSpinBox()
            h_spin.setRange(1.0, 500.0)
            h_spin.setSingleStep(1.0)
            h_spin.setDecimals(1)
            h_spin.setSuffix(" mm")
            h_spin.setPrefix("Alt: ")
            h_spin.setValue(h_default)
            h_spin.setEnabled(enabled)
            r_spin = QDoubleSpinBox()
            r_spin.setRange(1.0, 500.0)
            r_spin.setSingleStep(1.0)
            r_spin.setDecimals(1)
            r_spin.setSuffix(" mm")
            r_spin.setPrefix("Raio: ")
            r_spin.setValue(r_default)
            r_spin.setEnabled(enabled)
            cb.toggled.connect(h_spin.setEnabled)
            cb.toggled.connect(r_spin.setEnabled)
            return cb, h_spin, r_spin

        self.panel_mid1_enabled, self.panel_mid1_height, self.panel_mid1_radius = make_mid_row(
            1,
            float(getattr(self.gcode_settings, 'parametric_mid1_height', 30.0)),
            float(getattr(self.gcode_settings, 'parametric_mid1_radius', 40.0)),
            bool(getattr(self.gcode_settings, 'parametric_mid1_enabled', False)),
        )
        self.panel_mid2_enabled, self.panel_mid2_height, self.panel_mid2_radius = make_mid_row(
            2,
            float(getattr(self.gcode_settings, 'parametric_mid2_height', 60.0)),
            float(getattr(self.gcode_settings, 'parametric_mid2_radius', 45.0)),
            bool(getattr(self.gcode_settings, 'parametric_mid2_enabled', False)),
        )
        mid_grid.addWidget(self.panel_mid1_enabled, 0, 0)
        mid_grid.addWidget(self.panel_mid1_height,  0, 1)
        mid_grid.addWidget(self.panel_mid1_radius,  0, 2)
        mid_grid.addWidget(self.panel_mid2_enabled, 1, 0)
        mid_grid.addWidget(self.panel_mid2_height,  1, 1)
        mid_grid.addWidget(self.panel_mid2_radius,  1, 2)
        mid_group.setToolTip(
            "Insere pontos adicionais no perfil lateral do objeto.\n"
            "A altura é relativa à base da parede (início do corpo).\n"
            "Pontos fora do intervalo de altura do objeto são ignorados."
        )
        parametric_layout.addWidget(mid_group)

        object_group = QGroupBox("Parâmetros do Objeto")
        apply_font(object_group, 12, True)
        object_group_layout = QVBoxLayout(object_group)
        self.panel_parametric_stack = QStackedWidget()

        def make_obj_page() -> tuple[QWidget, QFormLayout]:
            page = QWidget()
            form = QFormLayout(page)
            return page, form

        def make_dim_spin(value: float) -> QDoubleSpinBox:
            sb = QDoubleSpinBox()
            sb.setRange(1.0, 500.0)
            sb.setSingleStep(1.0)
            sb.setSuffix(" mm")
            sb.setValue(float(value))
            return sb

        plate_page, plate_form = make_obj_page()
        self.panel_plate_base_diameter = make_dim_spin(getattr(self.gcode_settings, 'plate_base_diameter', 60.0))
        self.panel_plate_top_diameter = make_dim_spin(getattr(self.gcode_settings, 'plate_top_diameter', 140.0))
        self.panel_plate_wall_height = make_dim_spin(getattr(self.gcode_settings, 'plate_wall_height', 30.0))
        plate_form.addRow("Diâmetro da base:", self.panel_plate_base_diameter)
        plate_form.addRow("Diâmetro da borda:", self.panel_plate_top_diameter)
        plate_form.addRow("Altura da parede:", self.panel_plate_wall_height)
        self.panel_parametric_stack.addWidget(plate_page)

        cup_page, cup_form = make_obj_page()
        self.panel_cup_base_diameter = make_dim_spin(getattr(self.gcode_settings, 'cup_base_diameter', 55.0))
        self.panel_cup_top_diameter = make_dim_spin(getattr(self.gcode_settings, 'cup_top_diameter', 85.0))
        self.panel_cup_height = make_dim_spin(getattr(self.gcode_settings, 'cup_height', 90.0))
        cup_form.addRow("Diâmetro da base:", self.panel_cup_base_diameter)
        cup_form.addRow("Diâmetro do topo:", self.panel_cup_top_diameter)
        cup_form.addRow("Altura total:", self.panel_cup_height)
        self.panel_parametric_stack.addWidget(cup_page)

        jar_page, jar_form = make_obj_page()
        self.panel_jar_base_diameter = make_dim_spin(getattr(self.gcode_settings, 'jar_base_diameter', 55.0))
        self.panel_jar_max_body_diameter = make_dim_spin(getattr(self.gcode_settings, 'jar_max_body_diameter', 110.0))
        self.panel_jar_body_height = make_dim_spin(getattr(self.gcode_settings, 'jar_body_height', 85.0))
        self.panel_jar_top_diameter = make_dim_spin(getattr(self.gcode_settings, 'jar_top_diameter', 70.0))
        self.panel_jar_neck_height = make_dim_spin(getattr(self.gcode_settings, 'jar_neck_height', 20.0))
        jar_form.addRow("Diâmetro da base:", self.panel_jar_base_diameter)
        jar_form.addRow("Diâmetro máximo do corpo:", self.panel_jar_max_body_diameter)
        jar_form.addRow("Altura do corpo:", self.panel_jar_body_height)
        jar_form.addRow("Diâmetro da boca:", self.panel_jar_top_diameter)
        jar_form.addRow("Altura da boca:", self.panel_jar_neck_height)
        self.panel_parametric_stack.addWidget(jar_page)

        bottle_page, bottle_form = make_obj_page()
        self.panel_bottle_base_diameter = make_dim_spin(getattr(self.gcode_settings, 'bottle_base_diameter', 55.0))
        self.panel_bottle_body_height = make_dim_spin(getattr(self.gcode_settings, 'bottle_body_height', 100.0))
        self.panel_bottle_body_top_diameter = make_dim_spin(getattr(self.gcode_settings, 'bottle_body_top_diameter', 80.0))
        self.panel_bottle_neck_diameter = make_dim_spin(getattr(self.gcode_settings, 'bottle_neck_diameter', 36.0))
        self.panel_bottle_neck_height = make_dim_spin(getattr(self.gcode_settings, 'bottle_neck_height', 45.0))
        self.panel_bottle_shoulder_height = make_dim_spin(getattr(self.gcode_settings, 'bottle_shoulder_height', 20.0))
        bottle_form.addRow("Diâmetro da base:", self.panel_bottle_base_diameter)
        bottle_form.addRow("Altura do corpo:", self.panel_bottle_body_height)
        bottle_form.addRow("Diâmetro sup. do corpo:", self.panel_bottle_body_top_diameter)
        bottle_form.addRow("Diâmetro do gargalo:", self.panel_bottle_neck_diameter)
        bottle_form.addRow("Altura do gargalo:", self.panel_bottle_neck_height)
        bottle_form.addRow("Altura do ombro:", self.panel_bottle_shoulder_height)
        self.panel_parametric_stack.addWidget(bottle_page)

        self.panel_parametric_stack.setCurrentIndex(type_index)
        self.panel_parametric_type_combo.currentIndexChanged.connect(self.panel_parametric_stack.setCurrentIndex)
        object_group_layout.addWidget(self.panel_parametric_stack)

        preview_group = QGroupBox("Pré-visualização do Perfil")
        apply_font(preview_group, 12, True)
        preview_layout = QVBoxLayout(preview_group)
        self.panel_parametric_preview = ParametricProfilePreviewWidget()
        preview_layout.addWidget(self.panel_parametric_preview)

        preview_hint = QLabel(
            "Visualização simplificada do perfil lateral (raio × altura) usado na espiral."
        )
        apply_font(preview_hint, 10)
        preview_hint.setWordWrap(True)
        preview_hint.setStyleSheet("color: #4f5d6b;")
        preview_layout.addWidget(preview_hint)

        parametric_layout.addWidget(object_group)
        parametric_layout.addWidget(preview_group)
        self.settings_tabs.addTab(wrap_scroll(parametric_widget), "Objeto Paramétrico")

        self._bind_parametric_preview_updates()
        self._refresh_parametric_preview()

        sim_group = QGroupBox("Ajustes de Simulação")
        apply_font(sim_group, 12, True)
        sim_layout = QVBoxLayout(sim_group)
        overhang_group = QGroupBox("Detecção e Compensação de Overhang")
        apply_font(overhang_group, 12, True)
        overhang_form = QFormLayout(overhang_group)
        self.panel_enable_overhang = QCheckBox("Ativar compensacao")
        self.panel_enable_overhang.setChecked(
            getattr(self.gcode_settings, 'enable_overhang_compensation', False)
        )
        overhang_form.addRow(self.panel_enable_overhang)
        self.panel_overhang_support_layers = QSpinBox()
        self.panel_overhang_support_layers.setRange(0, 5)
        self.panel_overhang_support_layers.setValue(
            int(getattr(self.gcode_settings, 'overhang_support_layers', 1))
        )
        self.panel_overhang_support_layers.setEnabled(self.panel_enable_overhang.isChecked())
        self.panel_enable_overhang.toggled.connect(self.panel_overhang_support_layers.setEnabled)
        overhang_form.addRow("Camadas de apoio:", self.panel_overhang_support_layers)
        self.panel_min_overlap = QDoubleSpinBox()
        self.panel_min_overlap.setRange(0.0, 1.0)
        self.panel_min_overlap.setSingleStep(0.05)
        self.panel_min_overlap.setDecimals(2)
        self.panel_min_overlap.setValue(
            float(getattr(self.gcode_settings, 'min_vertical_overlap', 0.6))
        )
        self.panel_min_overlap.setSuffix(" × largura base")
        self.panel_min_overlap.setEnabled(self.panel_enable_overhang.isChecked())
        self.panel_enable_overhang.toggled.connect(self.panel_min_overlap.setEnabled)
        overhang_form.addRow("Fator extra de largura:", self.panel_min_overlap)
        self.panel_max_overhang_angle = QDoubleSpinBox()
        self.panel_max_overhang_angle.setRange(0.0, 85.0)
        self.panel_max_overhang_angle.setSingleStep(1.0)
        self.panel_max_overhang_angle.setDecimals(1)
        self.panel_max_overhang_angle.setValue(
            float(getattr(self.gcode_settings, 'max_overhang_angle_deg', 25.0))
        )
        self.panel_max_overhang_angle.setSuffix(" graus")
        self.panel_max_overhang_angle.setEnabled(self.panel_enable_overhang.isChecked())
        self.panel_enable_overhang.toggled.connect(self.panel_max_overhang_angle.setEnabled)
        overhang_form.addRow("Angulo máx. (°):", self.panel_max_overhang_angle)
        sim_layout.addWidget(overhang_group)
        self.settings_tabs.addTab(wrap_scroll(sim_group), "Simulação")

        view_group = QGroupBox("Controles de Visualização")
        apply_font(view_group, 12, True)
        view_layout = QVBoxLayout(view_group)
        self.show_object_cb = QCheckBox("Mostrar Objeto 3D")
        self.show_object_cb.setChecked(True)
        view_layout.addWidget(self.show_object_cb)
        self.show_path_cb = QCheckBox("Mostrar Percurso G-code")
        self.show_path_cb.setChecked(True)
        self.show_path_cb.setEnabled(False)
        view_layout.addWidget(self.show_path_cb)
        view_layout.addWidget(QLabel("Transparência do Objeto:"))
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(0)
        view_layout.addWidget(self.transparency_slider)
        views_label = QLabel("Vistas Rápidas:")
        apply_font(views_label)
        view_layout.addWidget(views_label)
        views_grid = QHBoxLayout()
        self.front_button = QPushButton("🔼 Frente")
        views_grid.addWidget(self.front_button)
        self.top_button = QPushButton("⏫ Topo")
        views_grid.addWidget(self.top_button)
        self.right_button = QPushButton("➡️ Dir")
        views_grid.addWidget(self.right_button)
        view_layout.addLayout(views_grid)
        views_grid2 = QHBoxLayout()
        self.left_button = QPushButton("⬅️ Esq")
        views_grid2.addWidget(self.left_button)
        self.bottom_button = QPushButton("⬇️ Base")
        views_grid2.addWidget(self.bottom_button)
        self.back_button = QPushButton("🔙 Tras")
        views_grid2.addWidget(self.back_button)
        view_layout.addLayout(views_grid2)
        self.reset_view_button = QPushButton("🔄 Resetar Visualização")
        view_layout.addWidget(self.reset_view_button)
        self.settings_tabs.addTab(wrap_scroll(view_group), "Visualização")

        advanced_group = QGroupBox("Configurações Avançadas")
        apply_font(advanced_group, 12, True)
        advanced_layout = QVBoxLayout(advanced_group)
        accel_row = QHBoxLayout()
        accel_label = QLabel("Aceleração (mm/s²):")
        apply_font(accel_label)
        self.acceleration_spinbox = QDoubleSpinBox()
        self.acceleration_spinbox.setRange(100.0, 5000.0)
        self.acceleration_spinbox.setSingleStep(50.0)
        self.acceleration_spinbox.setDecimals(0)
        self.acceleration_spinbox.setValue(
            getattr(self.gcode_settings, 'acceleration', 500.0)
        )
        accel_row.addWidget(accel_label)
        accel_row.addWidget(self.acceleration_spinbox)
        advanced_layout.addLayout(accel_row)
        accel_info = QLabel(
            "A aceleração controla como a máquina muda de velocidade.<br>"
            "Valores menores (300-500) = movimentos mais suaves, menos trancos<br>"
            "Valores maiores (1000-2000) = movimentos mais rápidos, mais trancos<br>"
            "<b>Recomendado: 500 mm/s² para argila</b>"
        )
        apply_font(accel_info, 11)
        accel_info.setStyleSheet(
            "background: #fff3cd; padding: 8px; border-radius: 4px;"
        )
        accel_info.setWordWrap(True)
        advanced_layout.addWidget(accel_info)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        advanced_layout.addWidget(separator)
        nonplanar_label = QLabel("<b>Modo Non-Planar (Experimental)</b>")
        apply_font(nonplanar_label, 11, True)
        advanced_layout.addWidget(nonplanar_label)
        self.enable_nonplanar_cb = QCheckBox("Ativar modo Non-Planar")
        self.enable_nonplanar_cb.setChecked(
            getattr(self.gcode_settings, 'enable_nonplanar_mode', False)
        )
        algo_group = QGroupBox("Algoritmo")
        apply_font(algo_group, 12, True)
        algo_layout = QVBoxLayout(algo_group)
        self.algo_group_bg = QButtonGroup(self)
        self.rb_algo1 = QRadioButton("Algoritmo 1 (Legacy - Warping)")
        self.rb_algo2 = QRadioButton("Algoritmo 2 (Robust - Clean+FeatureEdges)")
        self.rb_algo3 = QRadioButton("Algoritmo 3 (Linear - Tilted Cylinder)")
        self.algo_group_bg.addButton(self.rb_algo1, 1)
        self.algo_group_bg.addButton(self.rb_algo2, 2)
        self.algo_group_bg.addButton(self.rb_algo3, 3)

        current_algo = getattr(self.gcode_settings, 'nonplanar_algorithm', 1)
        if current_algo == 2:
            self.rb_algo2.setChecked(True)
        elif current_algo == 3:
            self.rb_algo3.setChecked(True)
        else:
            self.rb_algo1.setChecked(True)

        algo_layout.addWidget(self.rb_algo1)
        algo_layout.addWidget(self.rb_algo2)
        algo_layout.addWidget(self.rb_algo3)
        algo_group.setEnabled(self.enable_nonplanar_cb.isChecked())
        self.enable_nonplanar_cb.toggled.connect(algo_group.setEnabled)
        advanced_layout.addWidget(algo_group)
        nonplanar_info = QLabel(
            "O modo Non-Planar gera paredes em espiral que seguem a forma<br>"
            "orgânica do objeto, respeitando o contorno real em 3D.<br>"
            "<b>⚠️ Recomendado apenas para formas orgânicas/complexas</b><br>"
            "• Usa detecção automática de borda superior<br>"
            "• Distribui camadas mantendo formato original<br>"
            "• Requer calibração precisa do Z"
        )
        apply_font(nonplanar_info, 11)
        nonplanar_info.setStyleSheet(
            "background: #e3f2fd; padding: 8px; border-radius: 4px;"
        )
        nonplanar_info.setWordWrap(True)
        advanced_layout.addWidget(nonplanar_info)
        nonplanar_params_group = QGroupBox("Parâmetros Non-Planar")
        apply_font(nonplanar_params_group, 12, True)
        nonplanar_params_layout = QFormLayout(nonplanar_params_group)
        self.nonplanar_angular_step = QDoubleSpinBox()
        self.nonplanar_angular_step.setRange(0.1, 10.0)
        self.nonplanar_angular_step.setSingleStep(0.1)
        self.nonplanar_angular_step.setDecimals(1)
        self.nonplanar_angular_step.setValue(
            getattr(self.gcode_settings, 'nonplanar_angular_step_deg', 1.0)
        )
        self.nonplanar_angular_step.setSuffix(" °")
        self.nonplanar_angular_step.setEnabled(self.enable_nonplanar_cb.isChecked())
        nonplanar_params_layout.addRow(
            "Passo angular (resolução):", self.nonplanar_angular_step
        )
        self.nonplanar_angle_threshold = QDoubleSpinBox()
        self.nonplanar_angle_threshold.setRange(10.0, 90.0)
        self.nonplanar_angle_threshold.setSingleStep(5.0)
        self.nonplanar_angle_threshold.setDecimals(0)
        self.nonplanar_angle_threshold.setValue(
            getattr(self.gcode_settings, 'nonplanar_angle_threshold_deg', 60.0)
        )
        self.nonplanar_angle_threshold.setSuffix(" °")
        self.nonplanar_angle_threshold.setEnabled(self.enable_nonplanar_cb.isChecked())
        nonplanar_params_layout.addRow(
            "Limiar de borda superior:", self.nonplanar_angle_threshold
        )
        self.nonplanar_z_epsilon = QDoubleSpinBox()
        self.nonplanar_z_epsilon.setRange(0.0, 1.0)
        self.nonplanar_z_epsilon.setSingleStep(0.01)
        self.nonplanar_z_epsilon.setDecimals(3)
        self.nonplanar_z_epsilon.setValue(
            getattr(self.gcode_settings, 'nonplanar_z_epsilon', 0.03)
        )
        self.nonplanar_z_epsilon.setSuffix(" mm")
        self.nonplanar_z_epsilon.setEnabled(self.enable_nonplanar_cb.isChecked())
        nonplanar_params_layout.addRow("Recuo Z no topo:", self.nonplanar_z_epsilon)
        self.enable_nonplanar_cb.toggled.connect(self.nonplanar_angular_step.setEnabled)
        self.enable_nonplanar_cb.toggled.connect(self.nonplanar_angle_threshold.setEnabled)
        self.enable_nonplanar_cb.toggled.connect(self.nonplanar_z_epsilon.setEnabled)
        advanced_layout.addWidget(nonplanar_params_group)
        advanced_layout.addStretch()
        advanced_scroll = wrap_scroll(advanced_group)
        self.settings_tabs.addTab(advanced_scroll, "Avançado")
        self._advanced_tab_widget = advanced_scroll

        layout.addWidget(self.settings_tabs, 1)

        nonplanar_card = QGroupBox("Modo Non-Planar (Experimental)")
        apply_font(nonplanar_card, 12, True)
        nonplanar_layout = QVBoxLayout(nonplanar_card)
        self.nonplanar_status_label = QLabel(
            "Use superfícies orgânicas para aproveitar paredes inclinadas"
        )
        apply_font(self.nonplanar_status_label, 12)
        self.nonplanar_status_label.setWordWrap(True)
        nonplanar_layout.addWidget(self.nonplanar_status_label)
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.enable_nonplanar_cb)
        self.open_nonplanar_settings_btn = QPushButton("Ajustar parâmetros...")
        toggle_row.addWidget(self.open_nonplanar_settings_btn)
        nonplanar_layout.addLayout(toggle_row)
        self.open_nonplanar_settings_btn.clicked.connect(self._open_nonplanar_settings)
        layout.addWidget(nonplanar_card)

        self.info_toggle_button = QToolButton()
        self.info_toggle_button.setText("Mostrar dicas rápidas")
        self.info_toggle_button.setCheckable(True)
        self.info_toggle_button.setChecked(False)
        layout.addWidget(self.info_toggle_button)
        self.info_label = QLabel(
            """
<b>Valores sugeridos:</b><br>
• Extrusão: 2.5 mm × 1.0 mm<br>
• Velocidade: 600 mm/min<br>
• Micro espiral: 2.0 mm
            """
        )
        apply_font(self.info_label, 12)
        self.info_label.setStyleSheet(
            "background: #f8f9fa; padding: 10px; border-radius: 5px;"
        )
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(False)
        layout.addWidget(self.info_label)
        self.info_toggle_button.toggled.connect(self.info_label.setVisible)

    def set_speed_labels(self, first: str, other: str, travel: str) -> None:
        self.speed_first_layer_label.setText(first)
        self.speed_other_layers_label.setText(other)
        self.speed_travel_label.setText(travel)

    def _open_nonplanar_settings(self) -> None:
        if not hasattr(self, "_advanced_tab_widget"):
            return
        idx = self.settings_tabs.indexOf(self._advanced_tab_widget)
        if idx != -1:
            self.settings_tabs.setCurrentIndex(idx)

    def _build_parametric_keyframes(self) -> list[tuple[float, float]]:
        obj_idx = self.panel_parametric_type_combo.currentIndex()
        if obj_idx == 1:  # Cup
            h = max(1.0, float(self.panel_cup_height.value()))
            r0 = max(0.5, float(self.panel_cup_base_diameter.value()) * 0.5)
            r1 = max(0.5, float(self.panel_cup_top_diameter.value()) * 0.5)
            kfs: list[tuple[float, float]] = [(0.0, r0), (h, r1)]
            wall_h = h

        elif obj_idx == 2:  # Jar
            h_body = max(1.0, float(self.panel_jar_body_height.value()))
            h_neck = max(1.0, float(self.panel_jar_neck_height.value()))
            h_total = h_body + h_neck
            r0 = max(0.5, float(self.panel_jar_base_diameter.value()) * 0.5)
            r_mid = max(0.5, float(self.panel_jar_max_body_diameter.value()) * 0.5)
            r_top = max(0.5, float(self.panel_jar_top_diameter.value()) * 0.5)
            kfs = [(0.0, r0), (h_body, r_mid), (h_total, r_top)]
            wall_h = h_total

        elif obj_idx == 3:  # Bottle
            h_body = max(1.0, float(self.panel_bottle_body_height.value()))
            h_shoulder = max(0.5, float(self.panel_bottle_shoulder_height.value()))
            h_neck = max(1.0, float(self.panel_bottle_neck_height.value()))
            h_total = h_body + h_shoulder + h_neck
            r0 = max(0.5, float(self.panel_bottle_base_diameter.value()) * 0.5)
            r_body_top = max(0.5, float(self.panel_bottle_body_top_diameter.value()) * 0.5)
            r_neck = max(0.5, float(self.panel_bottle_neck_diameter.value()) * 0.5)
            kfs = [(0.0, r0), (h_body, r_body_top), (h_body + h_shoulder, r_neck), (h_total, r_neck)]
            wall_h = h_total

        else:  # Plate
            h = max(1.0, float(self.panel_plate_wall_height.value()))
            r0 = max(0.5, float(self.panel_plate_base_diameter.value()) * 0.5)
            r1 = max(0.5, float(self.panel_plate_top_diameter.value()) * 0.5)
            kfs = [(0.0, r0), (h, r1)]
            wall_h = h

        # Pontos intermediários genéricos
        extra: list[tuple[float, float]] = []
        if hasattr(self, 'panel_mid1_enabled') and self.panel_mid1_enabled.isChecked():
            h1 = float(self.panel_mid1_height.value())
            r1 = max(0.5, float(self.panel_mid1_radius.value()))
            if 1e-6 < h1 < wall_h - 1e-6:
                extra.append((h1, r1))
        if hasattr(self, 'panel_mid2_enabled') and self.panel_mid2_enabled.isChecked():
            h2 = float(self.panel_mid2_height.value())
            r2 = max(0.5, float(self.panel_mid2_radius.value()))
            if 1e-6 < h2 < wall_h - 1e-6:
                extra.append((h2, r2))
        if extra:
            first = kfs[0]
            last  = kfs[-1]
            middle = sorted(kfs[1:-1] + extra, key=lambda kf: kf[0])
            kfs = [first] + middle + [last]

        return kfs

    def _refresh_parametric_preview(self) -> None:
        if not hasattr(self, "panel_parametric_preview"):
            return
        keyframes = self._build_parametric_keyframes()
        enabled = bool(self.panel_enable_parametric_mode.isChecked())
        self.panel_parametric_preview.set_profile(keyframes, enabled)

    def _bind_parametric_preview_updates(self) -> None:
        widgets = [
            self.panel_enable_parametric_mode,
            self.panel_parametric_type_combo,
            self.panel_parametric_sharp_corners,
            self.panel_parametric_transition_len,
            self.panel_parametric_base_transition_radius,
            self.panel_parametric_curve_mode_combo,
            self.panel_parametric_curve_strength,
            self.panel_plate_base_diameter,
            self.panel_plate_top_diameter,
            self.panel_plate_wall_height,
            self.panel_cup_base_diameter,
            self.panel_cup_top_diameter,
            self.panel_cup_height,
            self.panel_jar_base_diameter,
            self.panel_jar_max_body_diameter,
            self.panel_jar_body_height,
            self.panel_jar_top_diameter,
            self.panel_jar_neck_height,
            self.panel_bottle_base_diameter,
            self.panel_bottle_body_height,
            self.panel_bottle_body_top_diameter,
            self.panel_bottle_neck_diameter,
            self.panel_bottle_neck_height,
            self.panel_bottle_shoulder_height,
            self.panel_mid1_enabled,
            self.panel_mid1_height,
            self.panel_mid1_radius,
            self.panel_mid2_enabled,
            self.panel_mid2_height,
            self.panel_mid2_radius,
        ]
        for w in widgets:
            if isinstance(w, QCheckBox):
                w.toggled.connect(self._refresh_parametric_preview)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._refresh_parametric_preview)
            elif isinstance(w, QDoubleSpinBox):
                w.valueChanged.connect(self._refresh_parametric_preview)
