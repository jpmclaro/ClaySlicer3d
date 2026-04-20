import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QDoubleSpinBox, QCheckBox,
    QComboBox, QDialogButtonBox, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from clay_gcode_generator_definitive import ClayPrintSettings

class GCodeGenerationDialog(QDialog):
    """Diálogo mínimo de configuração (usa configurações atuais)"""
    preset_applied = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Impressao")
        self._settings = getattr(parent, 'gcode_settings', ClayPrintSettings())

        layout = QVBoxLayout(self)
        info = QLabel("Usando as configurações atuais do painel principal. Você pode ajustar no painel e gerar a simulacao.")
        info.setWordWrap(True)
        layout.addWidget(info)
        btns = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancelar")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def get_settings(self) -> ClayPrintSettings:
        return self._settings

class PresetsEditorDialog(QDialog):
    """Editor de presets (CRUD básico)."""
    presets_updated = pyqtSignal(list)

    def __init__(self, parent=None, current_settings=None, presets_list=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Presets")
        self.gcode_settings = current_settings or ClayPrintSettings()
        self.panel_presets = presets_list or []
        self.setup_ui()

    def setup_ui(self):
        v = QVBoxLayout(self)

        # Lista de presets
        self.list_widget = QListWidget()
        for p in self.panel_presets:
            item = QListWidgetItem(p.get('name', 'Preset'))
            item.setData(Qt.UserRole, p)
            self.list_widget.addItem(item)
        v.addWidget(self.list_widget)

        # Formulário de edição
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.nozzle_spin = QDoubleSpinBox(); self.nozzle_spin.setRange(0.2, 20.0); self.nozzle_spin.setSuffix(" mm")
        self.width_spin = QDoubleSpinBox(); self.width_spin.setRange(0.2, 20.0); self.width_spin.setSuffix(" mm")
        self.other_width_spin = QDoubleSpinBox(); self.other_width_spin.setRange(0.2, 20.0); self.other_width_spin.setSuffix(" mm")
        self.first_h_spin = QDoubleSpinBox(); self.first_h_spin.setRange(0.1, 10.0); self.first_h_spin.setSuffix(" mm")
        self.other_h_spin = QDoubleSpinBox(); self.other_h_spin.setRange(0.1, 10.0); self.other_h_spin.setSuffix(" mm")
        self.speed1_spin = QDoubleSpinBox(); self.speed1_spin.setRange(1.0, 300.0); self.speed1_spin.setSuffix(" mm/s")
        self.speedo_spin = QDoubleSpinBox(); self.speedo_spin.setRange(1.0, 300.0); self.speedo_spin.setSuffix(" mm/s")
        self.flow_spin = QDoubleSpinBox(); self.flow_spin.setRange(0.1, 5.0); self.flow_spin.setSingleStep(0.05)
        self.vmax_spin = QDoubleSpinBox(); self.vmax_spin.setRange(1.0, 1000.0); self.vmax_spin.setSuffix(" mm³/s")
        self.micro_flow_spin = QDoubleSpinBox(); self.micro_flow_spin.setRange(0.1, 5.0); self.micro_flow_spin.setSingleStep(0.05)
        self.pa_spin = QDoubleSpinBox(); self.pa_spin.setRange(0.0, 2.0); self.pa_spin.setSingleStep(0.01)
        self.cx_spin = QDoubleSpinBox(); self.cx_spin.setRange(-1000.0, 1000.0); self.cx_spin.setSuffix(" mm")
        self.cy_spin = QDoubleSpinBox(); self.cy_spin.setRange(-1000.0, 1000.0); self.cy_spin.setSuffix(" mm")
        # Ponto central
        self.center_enable_cb = QCheckBox("Ativar ponto central")
        self.base_ramp_only_first_transition_cb = QCheckBox("Rampa base só na 1ª transição")
        self.center_w_spin = QDoubleSpinBox(); self.center_w_spin.setRange(0.2, 20.0); self.center_w_spin.setSuffix(" mm")
        self.center_h_spin = QDoubleSpinBox(); self.center_h_spin.setRange(0.1, 10.0); self.center_h_spin.setSuffix(" mm")
        self.center_dips_spin = QDoubleSpinBox(); self.center_dips_spin.setDecimals(0); self.center_dips_spin.setRange(1, 2); self.center_dips_spin.setSingleStep(1)
        self.base_layers_combo = QComboBox(); self.base_layers_combo.addItems(["1", "3", "5"]) 
        self.base_pattern_combo = QComboBox(); self.base_pattern_combo.addItems(["Cordao Arquimedes", "Concentrica"])
        self.base_direction_combo = QComboBox(); self.base_direction_combo.addItems(["Dentro -> Fora", "Fora -> Dentro"])
        self.transition_blend_flow_spin = QDoubleSpinBox(); self.transition_blend_flow_spin.setRange(0.1, 2.0); self.transition_blend_flow_spin.setSingleStep(0.05); self.transition_blend_flow_spin.setDecimals(2)

        form.addRow("Nome:", self.name_edit)
        form.addRow("Bico:", self.nozzle_spin)
        form.addRow("Largura 1ª camada:", self.width_spin)
        form.addRow("Largura demais camadas:", self.other_width_spin)
        form.addRow("Altura 1ª:", self.first_h_spin)
        form.addRow("Altura demais:", self.other_h_spin)
        form.addRow("Vel. 1ª (mm/s):", self.speed1_spin)
        form.addRow("Vel. demais (mm/s):", self.speedo_spin)
        form.addRow("Fluxo (×):", self.flow_spin)
        form.addRow("Vol máx (mm³/s):", self.vmax_spin)
        form.addRow("Fluxo micro (×):", self.micro_flow_spin)
        form.addRow("PA K:", self.pa_spin)
        form.addRow("Centro X:", self.cx_spin)
        form.addRow("Centro Y:", self.cy_spin)
        form.addRow(self.center_enable_cb)
        form.addRow(self.base_ramp_only_first_transition_cb)
        form.addRow("Ponto Largura:", self.center_w_spin)
        form.addRow("Ponto Altura:", self.center_h_spin)
        form.addRow("Mergulhos:", self.center_dips_spin)
        form.addRow("Camadas da base:", self.base_layers_combo)
        form.addRow("Padrao da base:", self.base_pattern_combo)
        form.addRow("Sentido da base:", self.base_direction_combo)
        form.addRow("Fluxo fino transição (×):", self.transition_blend_flow_spin)

        form_container = QWidget(); form_container.setLayout(form)
        v.addWidget(form_container)

        # Botões
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        v.addWidget(btn_box)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.load_from_item(self.list_widget.currentItem())
        else:
            self.add_new_item()

        # Botões de adicionar/remover
        btns_row = QHBoxLayout()
        add_btn = QPushButton("➕ Adicionar")
        rem_btn = QPushButton("🗑️ Remover")
        btns_row.addWidget(add_btn)
        btns_row.addWidget(rem_btn)
        v.addLayout(btns_row)

        add_btn.clicked.connect(self.add_new_item)
        rem_btn.clicked.connect(self.remove_current_item)

        # Ao trocar seleção, salvar no item anterior e carregar o novo
        self.list_widget.currentItemChanged.connect(lambda curr, prev: (self.save_fields_to_item(prev), self.load_from_item(curr)))
        # Ao salvar, persistir alterações do item atual e gravar no JSON
        btn_box.accepted.connect(self.on_accept)
        btn_box.rejected.connect(self.reject)

    def load_from_item(self, item: QListWidgetItem):
        if not item:
            return
        data = item.data(Qt.UserRole) or {}
        self.name_edit.setText(str(data.get('name', '')))
        self.nozzle_spin.setValue(float(data.get('nozzle_diameter', self.gcode_settings.nozzle_diameter)))
        self.width_spin.setValue(float(data.get('extrusion_width', self.nozzle_spin.value())))
        self.other_width_spin.setValue(float(data.get('other_layers_extrusion_width', self.width_spin.value())))
        self.first_h_spin.setValue(float(data.get('first_layer_height', getattr(self.gcode_settings, 'first_layer_height', 1.0))))
        self.other_h_spin.setValue(float(data.get('other_layers_height', self.gcode_settings.layer_height)))
        self.speed1_spin.setValue(float(data.get('first_layer_speed_mm_s', 10.0)))
        self.speedo_spin.setValue(float(data.get('other_layers_speed_mm_s', 20.0)))
        self.flow_spin.setValue(float(data.get('flow_rate', 1.0)))
        self.vmax_spin.setValue(float(data.get('max_volumetric_flow_mm3_s', getattr(self.gcode_settings, 'max_volumetric_flow_mm3_s', 30.0))))
        self.micro_flow_spin.setValue(float(data.get('micro_spiral_flow_rate', 1.0)))
        self.pa_spin.setValue(float(data.get('pressure_advance', 0.0)))
        self.cx_spin.setValue(float(data.get('print_center_x', self.gcode_settings.print_center_x)))
        self.cy_spin.setValue(float(data.get('print_center_y', self.gcode_settings.print_center_y)))
        self.center_enable_cb.setChecked(bool(data.get('enable_center_point_extrusion', getattr(self.gcode_settings, 'enable_center_point_extrusion', False))))
        self.base_ramp_only_first_transition_cb.setChecked(bool(data.get('base_ramp_only_first_transition', getattr(self.gcode_settings, 'base_ramp_only_first_transition', False))))
        self.center_w_spin.setValue(float(data.get('center_point_width', getattr(self.gcode_settings, 'center_point_width', self.gcode_settings.extrusion_width))))
        self.center_h_spin.setValue(float(data.get('center_point_height', getattr(self.gcode_settings, 'center_point_height', self.gcode_settings.first_layer_height))))
        self.center_dips_spin.setValue(float(data.get('center_point_dips', getattr(self.gcode_settings, 'center_point_dips', 2))))
        try:
            bl = int(data.get('base_layers_count', getattr(self.gcode_settings, 'base_layers_count', 1)))
            self.base_layers_combo.setCurrentIndex({1: 0, 3: 1, 5: 2}.get(bl, 0))
        except Exception:
            self.base_layers_combo.setCurrentIndex(0)
        base_pattern = str(data.get('base_pattern', getattr(self.gcode_settings, 'base_pattern', 'archimedes'))).strip().lower()
        self.base_pattern_combo.setCurrentIndex(1 if base_pattern == 'concentric' else 0)
        base_direction = str(data.get('base_direction', getattr(self.gcode_settings, 'base_direction', 'center_out'))).strip().lower()
        self.base_direction_combo.setCurrentIndex(1 if base_direction == 'outside_in' else 0)
        self.transition_blend_flow_spin.setValue(float(data.get('transition_blend_flow_factor', 1.0)))

    def save_fields_to_item(self, item: QListWidgetItem):
        if item is None:
            return
        data = dict(item.data(Qt.UserRole) or {})
        data.update({
            'name': self.name_edit.text().strip() or 'Preset',
            'nozzle_diameter': float(self.nozzle_spin.value()),
            'extrusion_width': float(self.width_spin.value()),
            'other_layers_extrusion_width': float(self.other_width_spin.value()),
            'first_layer_height': float(self.first_h_spin.value()),
            'other_layers_height': float(self.other_h_spin.value()),
            'first_layer_speed_mm_s': float(self.speed1_spin.value()),
            'other_layers_speed_mm_s': float(self.speedo_spin.value()),
            'flow_rate': float(self.flow_spin.value()),
            'max_volumetric_flow_mm3_s': float(self.vmax_spin.value()),
            'micro_spiral_flow_rate': float(self.micro_flow_spin.value()),
            'pressure_advance': float(self.pa_spin.value()),
            'print_center_x': float(self.cx_spin.value()),
            'print_center_y': float(self.cy_spin.value()),
            'enable_center_point_extrusion': bool(self.center_enable_cb.isChecked()),
            'base_ramp_only_first_transition': bool(self.base_ramp_only_first_transition_cb.isChecked()),
            'center_point_width': float(self.center_w_spin.value()),
            'center_point_height': float(self.center_h_spin.value()),
            'center_point_dips': int(self.center_dips_spin.value()),
            'base_layers_count': int(self.base_layers_combo.currentText()),
            'base_pattern': 'concentric' if self.base_pattern_combo.currentIndex() == 1 else 'archimedes',
            'base_direction': 'outside_in' if self.base_direction_combo.currentIndex() == 1 else 'center_out',
            'transition_blend_flow_factor': float(self.transition_blend_flow_spin.value()),
        })
        item.setText(data['name'])
        item.setData(Qt.UserRole, data)

    def add_new_item(self):
        # Salvar alterações no item atual antes de criar um novo
        self.save_fields_to_item(self.list_widget.currentItem())
        item = QListWidgetItem("Novo Preset")
        default_data = {
            'name': 'Novo Preset',
            'nozzle_diameter': self.gcode_settings.nozzle_diameter,
            'extrusion_width': self.gcode_settings.extrusion_width,
            'first_layer_height': getattr(self.gcode_settings, 'first_layer_height', 1.0),
            'other_layers_height': self.gcode_settings.layer_height,
            'first_layer_speed_mm_s': 10.0,
            'other_layers_speed_mm_s': 20.0,
            'flow_rate': 1.0,
            'max_volumetric_flow_mm3_s': getattr(self.gcode_settings, 'max_volumetric_flow_mm3_s', 30.0),
            'micro_spiral_flow_rate': getattr(self.gcode_settings, 'micro_spiral_flow_rate', 1.0),
            'pressure_advance': getattr(self.gcode_settings, 'pressure_advance', 0.0),
            'print_center_x': self.gcode_settings.print_center_x,
            'print_center_y': self.gcode_settings.print_center_y,
            'enable_center_point_extrusion': getattr(self.gcode_settings, 'enable_center_point_extrusion', False),
            'base_ramp_only_first_transition': getattr(self.gcode_settings, 'base_ramp_only_first_transition', False),
            'center_point_width': getattr(self.gcode_settings, 'center_point_width', self.gcode_settings.extrusion_width),
            'center_point_height': getattr(self.gcode_settings, 'center_point_height', self.gcode_settings.first_layer_height),
            'center_point_dips': getattr(self.gcode_settings, 'center_point_dips', 1),
            'base_layers_count': getattr(self.gcode_settings, 'base_layers_count', 1),
            'base_pattern': getattr(self.gcode_settings, 'base_pattern', 'archimedes'),
            'base_direction': getattr(self.gcode_settings, 'base_direction', 'center_out'),
            'transition_blend_flow_factor': getattr(self.gcode_settings, 'transition_blend_flow_factor', 1.0),
        }
        item.setData(Qt.UserRole, default_data)
        self.list_widget.addItem(item)
        self.list_widget.setCurrentItem(item)
        self.load_from_item(item)

    def remove_current_item(self):
        # Salvar alterações antes de remover
        self.save_fields_to_item(self.list_widget.currentItem())
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))
                self.load_from_item(self.list_widget.currentItem())
            else:
                # limpar formulário
                self.name_edit.clear()
                self.nozzle_spin.setValue(self.gcode_settings.nozzle_diameter)
                self.width_spin.setValue(self.gcode_settings.extrusion_width)
                self.first_h_spin.setValue(getattr(self.gcode_settings, 'first_layer_height', 1.0))
                self.other_h_spin.setValue(self.gcode_settings.layer_height)
                self.speed1_spin.setValue(10.0)
                self.speedo_spin.setValue(20.0)
                self.flow_spin.setValue(1.0)
                self.vmax_spin.setValue(getattr(self.gcode_settings, 'max_volumetric_flow_mm3_s', 30.0))
                self.micro_flow_spin.setValue(getattr(self.gcode_settings, 'micro_spiral_flow_rate', 1.0))
                self.pa_spin.setValue(getattr(self.gcode_settings, 'pressure_advance', 0.0))
                self.cx_spin.setValue(self.gcode_settings.print_center_x)
                self.cy_spin.setValue(self.gcode_settings.print_center_y)
                self.center_enable_cb.setChecked(getattr(self.gcode_settings, 'enable_center_point_extrusion', False))
                self.base_ramp_only_first_transition_cb.setChecked(getattr(self.gcode_settings, 'base_ramp_only_first_transition', False))
                self.base_pattern_combo.setCurrentIndex(1 if str(getattr(self.gcode_settings, 'base_pattern', 'archimedes')).strip().lower() == 'concentric' else 0)
                self.base_direction_combo.setCurrentIndex(1 if str(getattr(self.gcode_settings, 'base_direction', 'center_out')).strip().lower() == 'outside_in' else 0)
                self.center_w_spin.setValue(getattr(self.gcode_settings, 'center_point_width', self.gcode_settings.extrusion_width))
                self.center_h_spin.setValue(getattr(self.gcode_settings, 'center_point_height', self.gcode_settings.first_layer_height))
                self.transition_blend_flow_spin.setValue(getattr(self.gcode_settings, 'transition_blend_flow_factor', 1.0))

    def on_accept(self):
        self.save_fields_to_item(self.list_widget.currentItem())
        self._save_presets_from_list_and_close()

    def get_presets(self):
        """Retorna presets atualmente editados no diálogo (sem depender do arquivo)."""
        self.save_fields_to_item(self.list_widget.currentItem())
        return self._collect_presets_from_list()

    def _collect_presets_from_list(self):
        presets = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.UserRole)
            if data:
                presets.append(data)
        return presets

    def _save_presets_from_list_and_close(self):
        # Coletar todos os itens
        presets = self._collect_presets_from_list()
        # Salvar JSON
        try:
            path = os.path.join(os.path.dirname(__file__), 'printer_presets.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'presets': presets}, f, ensure_ascii=False, indent=2)
            
            self.presets_updated.emit(presets)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar presets:\n{e}")
