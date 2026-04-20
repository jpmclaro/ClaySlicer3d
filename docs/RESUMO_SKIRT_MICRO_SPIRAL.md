# RESUMO: Implementação de SAIA (Skirt) + Controle de Micro Espiral

## 📅 Data: 2025-10-04

## 🎯 Objetivos Cumpridos:

### 1. Remover comandos de inicialização do G-code
- ❌ **Removido**: `G28 ; home all axes`
- ❌ **Removido**: `M190 S{bed_temp}` (temperatura de mesa)
- ✅ **Motivo**: Impressora de argila não precisa destes comandos

### 2. Implementar SAIA (Skirt)
- ✅ **Função**: Meia volta (π radianos) com diâmetro 10mm maior que a base
- ✅ **Objetivo**: Carregar e inicializar o extrusor antes de imprimir a peça
- ✅ **Extrusão**: 100% de fluxo (flow_multiplier=1.0)
- ✅ **Posição**: Primeira operação após header, antes do ponto central

### 3. Adicionar controle de Micro Espiral via Preset
- ✅ **Parâmetro**: `enable_center_micro_spiral` (bool)
- ✅ **Preset JSON**: Todos os 4 presets atualizados
- ✅ **Interface UI**: Checkbox "Micro espiral inicial" adicionado
- ✅ **Sincronização**: Load/Save preset funcionando

---

## 📝 Arquivos Modificados:

### 1. `clay_gcode_core.py`
**Linhas 32-37** - Header do G-code
```python
# ANTES:
"G28 ; home all axes",
f"M190 S{self.settings.bed_temp:.1f}",

# DEPOIS:
# (removidos)
```

### 2. `clay_base_layers.py`
**Linhas 391-423** - Novo método `_generate_skirt()`
```python
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
    skirt_radius = base_radius + 10.0  # 10mm maior
    angle_span = math.pi  # Meia volta
    
    # 3 pontos por mm de arco
    arc_length = skirt_radius * angle_span
    points_per_mm = 3.0
    num_points = max(48, int(arc_length * points_per_mm))
    
    # Gerar pontos de 0 → π radianos
    skirt_points: List[Point3D] = []
    for i in range(num_points + 1):
        t = i / num_points
        angle = angle_span * t
        x = center_x + skirt_radius * math.cos(angle)
        y = center_y + skirt_radius * math.sin(angle)
        skirt_points.append(Point3D(x, y, z))
    
    return skirt_points
```

**Linhas 437-451** - Emissão da saia em `generate_base()`
```python
# SAIA: Meia volta com diâmetro +10mm para carregar extrusor
skirt_points = self._generate_skirt(cx, cy, base_radius, z0)
if skirt_points:
    gcode_lines.append("; SKIRT_START")
    speed = self.settings.first_layer_speed
    self._emit_path(
        gcode_lines, 
        skirt_points, 
        speed, 
        flow_multiplier=1.0,  # 100% de extrusão
        layer_height=self.settings.first_layer_height,
        extrude=True
    )
    gcode_lines.append("; SKIRT_END")
```

### 3. `printer_presets.json`
**Todos os 4 presets** - Adicionado campo `enable_center_micro_spiral`
```json
{
  "name": "Bico 2mm",
  "enable_center_micro_spiral": false,
  ...
}
{
  "name": "Bico 3mm",
  "enable_center_micro_spiral": true,
  ...
}
{
  "name": "Bico 4mm",
  "enable_center_micro_spiral": true,
  ...
}
{
  "name": "Bico 5mm",
  "enable_center_micro_spiral": true,
  ...
}
```

### 4. `integrated_clay_viewer.py`

**Linha 10** - Importação de `math`
```python
import math
```

**Linhas 867-872** - UI: Checkbox micro espiral
```python
# Micro espiral inicial
self.panel_enable_micro_spiral = QCheckBox("Micro espiral inicial")
self.panel_enable_micro_spiral.setChecked(
    getattr(self.gcode_settings, 'enable_center_micro_spiral', True)
)
self.panel_enable_micro_spiral.toggled.connect(self.apply_main_panel_controls)
preset_form.addRow(self.panel_enable_micro_spiral)
```

**Linhas 1182-1183** - Load preset: Micro espiral
```python
enable_micro_spiral = bool(p.get('enable_center_micro_spiral', 
    getattr(self.gcode_settings, 'enable_center_micro_spiral', True)))
```

**Linhas 1210-1214** - UI Update: Micro espiral
```python
if hasattr(self, 'panel_enable_micro_spiral'):
    self.panel_enable_micro_spiral.blockSignals(True)
    self.panel_enable_micro_spiral.setChecked(enable_micro_spiral)
    self.panel_enable_micro_spiral.blockSignals(False)
```

**Linhas 1250-1251** - Settings sync: Micro espiral
```python
self.gcode_settings.enable_center_micro_spiral = enable_micro_spiral
```

**Linhas 1538-1539** - Apply controls: Micro espiral
```python
if hasattr(self, 'panel_enable_micro_spiral'):
    self.gcode_settings.enable_center_micro_spiral = bool(
        self.panel_enable_micro_spiral.isChecked())
```

**Linhas 1723-1724** - Dialog sync: Micro espiral
```python
if hasattr(self, 'panel_enable_micro_spiral'):
    self.panel_enable_micro_spiral.setChecked(
        bool(getattr(self.gcode_settings, 'enable_center_micro_spiral', True)))
```

**Linhas 1850-1858** - Visualização da saia (MAGENTA/ROSA)
```python
# Separar skirt, ponto central, micro, base+arco e paredes
skirt_points, center_points, micro_spiral_points, base_arc_points, wall_points, taper_points = self.separate_micro_spiral_points()

# SAIA (Skirt) - Magenta/Rosa para destaque
if skirt_points:
    print(f"🌸 Criando saia (skirt): {len(skirt_points)} pontos")
    skirt_geometry = self.create_path_geometry(skirt_points, extrusion_width, first_h)
    if skirt_geometry:
        skirt_actor = self.create_extrusion_actor(
            skirt_geometry, color=(0.9, 0.2, 0.6))  # Magenta/Rosa
        self.simulation_actors.append(skirt_actor)
        self.renderer.AddActor(skirt_actor)
        print("✅ Saia magenta criada!")
```

**Linhas 1931-1934** - Conexão visual taper
```python
# Se gap > 0.1mm entre walls e taper, criar linha de conexão
if gap_distance > 0.1:
    print(f"🔗 Gap detectado ({gap_distance:.3f}mm), criando conexão...")
    connection_points = [last_wall, first_taper]
    connection_geometry = self.create_path_geometry(...)
```

**Linhas 2191-2213** - Máquina de estados: Fase 'skirt'
```python
def separate_micro_spiral_points(self):
    """Separa pontos do skirt, ponto central, micro espiral, base+arco, paredes e taper"""
    # Retorna: (skirt_points, center_points, micro_points, base_arc_points, wall_points, taper_points)
    
    skirt_points = []
    ...
    
    # Fases: 'none' | 'skirt' | 'center' | 'micro' | 'basearc' | 'walls' | 'taper' | 'done'
    phase = 'none'
    
    for command in self.gcode_data:
        if "; SKIRT_START" in command:
            phase = 'skirt'
            continue
        elif "; SKIRT_END" in command:
            phase = 'none'
            continue
```

**Linhas 2274-2276** - Processamento fase 'skirt'
```python
# Classificação por fase
if phase == 'skirt':
    skirt_points.append(current_pos[:])
elif phase == 'center':
    ...
```

---

## ✅ Testes Realizados:

### 1. **test_skirt_generation.py**
```
✅ Saia gerada com sucesso!
   Pontos: 376
   
✅ Header OK: Sem G28 e M190

📍 Primeiros pontos:
   X=207.499, Y=230.334, Z=1.500, E=0.1277
   
📍 Últimos pontos:
   X=127.500, Y=230.000, Z=1.500, E=0.1277
```

### 2. **Visualização no Viewer**
- 🌸 **Saia**: Cor magenta/rosa (0.9, 0.2, 0.6)
- 🔴 **Ponto central**: Vermelho
- 🔵 **Micro espiral**: Azul (controlável via checkbox)
- 🟠 **Base+arco**: Laranja
- 🟢 **Paredes**: Verde
- 🟠 **Taper**: Laranja com afinamento visual

### 3. **Preset Control**
- ✅ Checkbox "Micro espiral inicial" funcional
- ✅ Load/Save preset mantém configuração
- ✅ Sincronização com `clay_settings.py` OK

---

## 🎨 Cores da Visualização:

| Elemento | Cor | RGB |
|----------|-----|-----|
| **Saia** | 🌸 Magenta/Rosa | (0.9, 0.2, 0.6) |
| **Ponto Central** | 🔴 Vermelho | (0.9, 0.1, 0.1) |
| **Micro Espiral** | 🔵 Azul | (0.1, 0.3, 0.8) |
| **Base+Arco** | 🟠 Laranja | (0.8, 0.4, 0.1) |
| **Paredes** | 🟢 Verde | (0.2, 0.7, 0.2) |
| **Taper** | 🟠 Laranja | (0.9, 0.6, 0.1) |
| **Conexão Taper** | 🟠 Laranja | (0.9, 0.6, 0.1) |

---

## 📊 Sequência de Impressão:

```
1. HEADER (sem G28/M190)
2. ├─ SAIA (Skirt) ─────────── 🌸 Meia volta +10mm, 100% extrusão
3. ├─ PONTO CENTRAL (opcional) ─ 🔴 Mergulhos no centro
4. ├─ MICRO ESPIRAL (opcional) ─ 🔵 3 voltas iniciais
5. ├─ ESPIRAL BASE ──────────── 🟠 Archimedean até raio
6. ├─ ARCO FECHAMENTO ────────── 🟠 Completa volta
7. ├─ PAREDES ───────────────── 🟢 Helicoidal com rampa
8. ├─ TAPER (opcional) ───────── 🟠 Fecha topo, E: 100%→0%
9. └─ FOOTER
```

---

## 🔧 Como Usar:

### 1. Ativar/Desativar Micro Espiral:
- Interface: Marcar/desmarcar checkbox "Micro espiral inicial"
- Preset: Editar `printer_presets.json`:
  ```json
  "enable_center_micro_spiral": true/false
  ```

### 2. Saia é Automática:
- Sempre gerada no início
- Diâmetro = base + 10mm
- Meia volta (180°)
- 100% de extrusão

### 3. Visualização:
- Saia aparece em **MAGENTA/ROSA**
- Facilita identificação do percurso de carregamento
- Separada visualmente dos outros elementos

---

## 🎯 Próximos Passos (Sugestões):

1. ✅ **Parâmetro de distância da saia**: Permitir ajustar o offset de 10mm
2. ✅ **Voltas da saia**: Permitir meia volta, 1 volta completa, ou mais
3. ✅ **Fluxo da saia**: Permitir ajustar flow_multiplier da saia
4. ✅ **Habilitar/desabilitar saia**: Checkbox no preset

---

## 📚 Referências:

- **Saia (Skirt)**: Técnica padrão de FDM/FFF para carregar extrusor
- **Micro Espiral**: Padrão proprietário para impressão em argila
- **Taper**: Fechamento suave do topo com redução gradual de extrusão

---

**Status**: ✅ **IMPLEMENTADO E TESTADO COM SUCESSO**
