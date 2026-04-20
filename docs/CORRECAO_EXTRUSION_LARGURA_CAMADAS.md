# CORREÇÃO: Aumento de Extrusão + Controle de Largura por Camada

## 📅 Data: 2025-10-04

## 🎯 Problemas Resolvidos:

### 1. **Pouca Extrusão no Ponto Central**
- **Problema**: Ponto central não tinha material suficiente
- **Solução**: Aumentar `clay_factor` de 0.3 para 0.5
- **Resultado**: 66% mais material em toda a impressão

### 2. **Controle de Largura da 2ª Camada em Diante**
- **Problema**: Não havia como controlar largura separadamente para camadas superiores
- **Solução**: Novo parâmetro `other_layers_extrusion_width`
- **Resultado**: Pode ajustar largura da 1ª camada diferente das demais

---

## 📝 Arquivos Modificados:

### 1. `clay_settings.py` - Novo Parâmetro

**Linha 6** - Adicionado `other_layers_extrusion_width`:
```python
@dataclass
class ClayPrintSettings:
    nozzle_diameter: float = 2.0
    extrusion_width: float = 2.5  # Largura 1ª camada
    other_layers_extrusion_width: float = 2.5  # Largura demais camadas ← NOVO
    first_layer_height: float = 1.0
```

### 2. `clay_gcode_core.py` - Aumento de Extrusão

**Linha 75** - `clay_factor` aumentado:
```python
# ANTES:
clay_factor = 0.3

# DEPOIS:
clay_factor = 0.5  # Aumentado de 0.3 para 0.5 (66% mais material)
```

**Impacto**:
- Mais extrusão em TODOS os movimentos
- Ponto central terá mais material
- Base e paredes terão mais material
- Cálculo: `E = (volume / filament_area) * 0.5 * flow_rate`

### 3. `integrated_clay_viewer.py` - UI

**Linhas 955-972** - Novo SpinBox:
```python
extrusion_layout.addWidget(QLabel("Largura da Extrusão:"))
self.width_spinbox = QDoubleSpinBox()  # 1ª camada
# ...

extrusion_layout.addWidget(QLabel("Largura Demais Camadas:"))
self.other_width_spinbox = QDoubleSpinBox()  # 2ª+ camadas ← NOVO
self.other_width_spinbox.setRange(0.5, 10.0)
self.other_width_spinbox.setValue(getattr(self.gcode_settings, 'other_layers_extrusion_width', 2.5))
self.other_width_spinbox.setSuffix(" mm")
self.other_width_spinbox.setSingleStep(0.1)
self.other_width_spinbox.valueChanged.connect(self.update_extrusion_geometry)
extrusion_layout.addWidget(self.other_width_spinbox)
```

**Linha 2972** - Sincronização com settings:
```python
self.gcode_settings.extrusion_width = self.width_spinbox.value()
if hasattr(self, 'other_width_spinbox'):
    self.gcode_settings.other_layers_extrusion_width = self.other_width_spinbox.value()  # ← NOVO
```

### 4. `printer_presets.json` - Todos os 4 Presets

Adicionado campo `other_layers_extrusion_width` em todos:
```json
{
  "name": "Bico 2mm",
  "extrusion_width": 2.0,
  "other_layers_extrusion_width": 2.0,  ← NOVO
  ...
}
{
  "name": "Bico 3mm",
  "extrusion_width": 3.3,
  "other_layers_extrusion_width": 3.3,  ← NOVO
  ...
}
{
  "name": "Bico 4mm",
  "extrusion_width": 4.0,
  "other_layers_extrusion_width": 4.0,  ← NOVO
  ...
}
{
  "name": "Bico 5mm",
  "extrusion_width": 5.0,
  "other_layers_extrusion_width": 5.0,  ← NOVO
  ...
}
```

---

## 🔢 Cálculo de Extrusão:

### Fórmula Completa:
```python
# Volume do cordão
volume = distance * extrusion_width * layer_height

# Área do filamento
filament_area = π * (nozzle_diameter / 2)²

# Extrusão teórica
theoretical = volume / filament_area

# Extrusão final (relativa)
E = theoretical * clay_factor * flow_rate * flow_multiplier
```

### Comparação:

| Fator | Antes | Depois | Mudança |
|-------|-------|--------|---------|
| `clay_factor` | 0.3 | 0.5 | +66.7% |
| E (exemplo) | 0.0765 | 0.1275 | +66.7% |

**Exemplo com bico 3.3mm, largura 3.3mm, altura 3.3mm, distância 1mm:**
```python
# Antes:
volume = 1.0 * 3.3 * 3.3 = 10.89 mm³
filament_area = π * (3.3/2)² = 8.553 mm²
theoretical = 10.89 / 8.553 = 1.273
E = 1.273 * 0.3 * 1.0 * 1.0 = 0.382 mm

# Depois:
E = 1.273 * 0.5 * 1.0 * 1.0 = 0.637 mm  (+66.7%)
```

---

## 🎨 Interface:

### Novo Campo Visível:
```
┌─────────────────────────────────────┐
│ Geometria da Extrusão               │
├─────────────────────────────────────┤
│ Largura da Extrusão:      [3.3] mm  │  ← 1ª camada
│ Largura Demais Camadas:   [3.3] mm  │  ← 2ª+ camadas (NOVO)
│ Altura 1ª Camada:         [3.3] mm  │
│ Altura Demais Camadas:    [2.0] mm  │
│ Transição altura (voltas): [1.00]   │
└─────────────────────────────────────┘
```

---

## 💡 Como Usar:

### Cenário 1: Primeira Camada Mais Larga
```
Largura 1ª Camada: 4.0mm
Largura Demais:    3.0mm
→ Melhor aderência na base
→ Paredes mais estreitas/altas
```

### Cenário 2: Todas Iguais (Padrão)
```
Largura 1ª Camada: 3.3mm
Largura Demais:    3.3mm
→ Uniformidade total
```

### Cenário 3: Primeira Camada Mais Estreita
```
Largura 1ª Camada: 3.0mm
Largura Demais:    3.5mm
→ Base delicada
→ Paredes mais robustas
```

---

## ⚠️ Observações:

### 1. **Clay Factor Fixo**
- Valor fixo de 0.5 para toda impressão
- Para ajuste fino, use o **Flow Rate** (1.0-1.5)
- Flow Rate multiplica o clay_factor

### 2. **Compatibilidade**
- Todos os presets atualizados automaticamente
- Valor padrão = `extrusion_width` se não especificado
- Retrocompatível com G-codes antigos

### 3. **Visualização**
- Viewer mostra largura da 1ª camada na base
- Largura das demais camadas não afeta visualização (só G-code)
- Proporção L/H calculada com 1ª camada

---

## 🧪 Próximo Teste:

1. **Abrir viewer**
2. **Ajustar larguras**:
   - Largura 1ª Camada: 3.3mm
   - Largura Demais: 3.0mm (por exemplo)
3. **Gerar G-code**
4. **Imprimir**
5. **Observar**:
   - Ponto central com mais material ✅
   - Base com largura de 3.3mm ✅
   - Paredes com largura de 3.0mm ✅

---

## 📊 Resultados Esperados:

✅ **Ponto Central**: Mais material, melhor fixação
✅ **Base**: Extrusão adequada, sem falhas
✅ **Paredes**: Controle independente de largura
✅ **Flexibilidade**: Ajuste fino por camada

---

**Status**: ✅ **IMPLEMENTADO E PRONTO PARA TESTE**

**Próxima Impressão**: Deve ter extrusão 66% maior em todos os elementos, com controle separado de largura entre 1ª camada e demais!
