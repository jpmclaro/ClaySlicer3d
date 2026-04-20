# Controle de Aceleração - Implementação

## 📋 Resumo
Implementado controle de aceleração para evitar trancos na máquina durante mudanças de velocidade.

## 🎯 Problema Identificado
- **Sintoma**: Trancos na máquina durante mudanças de velocidade
- **Causa**: Ausência de limitação de aceleração no G-code
- **Impacto**: Movimentos bruscos podem afetar a qualidade da impressão e desgastar mecanicamente a impressora

## ✅ Solução Implementada

### 1. Novo Parâmetro em `clay_settings.py`
```python
acceleration: float = 500.0  # mm/s²
```

**Linha adicionada**: Após `first_layer_speed` (linha ~14)

### 2. Comando M204 no Header (`clay_gcode_core.py`)
```python
f"M204 S{self.settings.acceleration:.0f} ; set acceleration"
```

**Posição**: Após M900 (Pressure Advance), antes de G92 E0
**Linha**: ~38

**Header completo gerado**:
```gcode
G90 ; absolute positioning
G21 ; metric units
M83 ; relative extrusion
M204 S500 ; set acceleration
G92 E0
G1 F1200
; Move to print center at 5mm height
G1 X155.000 Y230.000 Z5.000 F1200
```

### 3. Nova Aba "Avançado" na Interface
**Arquivo**: `integrated_clay_viewer.py`
**Localização**: Após aba "Outros", antes do final das tabs

**Componentes adicionados**:
- **Spinbox de Aceleração**:
  - Range: 100 - 5000 mm/s²
  - Passo: 50 mm/s²
  - Valor padrão: 500 mm/s²
  - Conectado a: `apply_main_panel_controls()`

- **Label informativo**:
  - Explica o efeito de valores baixos vs altos
  - Recomendação: 500 mm/s² para argila

**Código adicionado** (linhas ~1140-1165):
```python
# Aba "Avançado": Aceleração e configurações de máquina
advanced_group = QGroupBox("Configurações Avançadas")
advanced_layout = QVBoxLayout(advanced_group)

# Aceleração
accel_row = QHBoxLayout()
accel_label = QLabel("Aceleração (mm/s²):")
self.acceleration_spinbox = QDoubleSpinBox()
self.acceleration_spinbox.setRange(100.0, 5000.0)
self.acceleration_spinbox.setSingleStep(50.0)
self.acceleration_spinbox.setDecimals(0)
self.acceleration_spinbox.setValue(getattr(self.gcode_settings, 'acceleration', 500.0))
self.acceleration_spinbox.valueChanged.connect(self.apply_main_panel_controls)
accel_row.addWidget(accel_label)
accel_row.addWidget(self.acceleration_spinbox)
advanced_layout.addLayout(accel_row)

# Informação sobre aceleração
accel_info = QLabel(
    "A aceleração controla como a máquina muda de velocidade.<br>"
    "Valores menores (300-500) = movimentos mais suaves, menos trancos<br>"
    "Valores maiores (1000-2000) = movimentos mais rápidos, mais trancos<br>"
    "<b>Recomendado: 500 mm/s² para argila</b>"
)
accel_info.setStyleSheet("background: #fff3cd; padding: 8px; border-radius: 4px; font-size: 9px;")
accel_info.setWordWrap(True)
advanced_layout.addWidget(accel_info)

advanced_layout.addStretch()
self.settings_tabs.addTab(wrap_scroll(advanced_group), "Avançado")
```

### 4. Sincronização com Presets
**Método**: `apply_main_panel_controls()`

**Carregamento do preset** (linha ~1232):
```python
acceleration = float(p.get('acceleration', 500.0))  # Aceleração do preset
```

**Atualização da UI** (linha ~1248):
```python
# Aceleração (aba Avançado)
if hasattr(self, 'acceleration_spinbox'):
    self.acceleration_spinbox.setValue(acceleration)
```

**Aplicação nas settings** (linha ~1296):
```python
# Aceleração (da aba Avançado)
if hasattr(self, 'acceleration_spinbox'):
    self.gcode_settings.acceleration = self.acceleration_spinbox.value()
```

### 5. Atualização de Todos os Presets
**Arquivo**: `printer_presets.json`

Adicionado `"acceleration": 500.0` em todos os 4 presets:
- ✅ Bico 2mm: 500 mm/s²
- ✅ Bico 3mm: 500 mm/s²
- ✅ Bico 4mm: 500 mm/s²
- ✅ Bico 5mm: 500 mm/s²

## 🔧 Como Usar

### Ajuste Básico (Interface)
1. Abrir visualizador
2. Ir para aba **"Avançado"**
3. Ajustar "Aceleração (mm/s²)" conforme necessário
4. Gerar G-code

### Valores Recomendados

| Situação | Aceleração | Efeito |
|----------|------------|--------|
| **Argila padrão** | 500 mm/s² | ✅ Movimentos suaves, sem trancos |
| **Alta velocidade** | 1000-1500 mm/s² | ⚡ Mais rápido, pode ter trancos leves |
| **Ultra suave** | 300-400 mm/s² | 🐌 Muito suave, mas mais lento |
| **Teste estrutural** | 200 mm/s² | 🔬 Teste de qualidade máxima |

### Quando Ajustar

**Diminuir aceleração (300-400) se**:
- ❌ Trancos visíveis durante impressão
- ❌ Vibrações excessivas
- ❌ Perda de passos em motores
- ❌ Defeitos nas mudanças de direção

**Aumentar aceleração (700-1000) se**:
- ✅ Impressões muito lentas
- ✅ Máquina robusta com motores potentes
- ✅ Nenhum problema de qualidade observado

## 📊 Impacto no G-code

### Antes (sem controle)
```gcode
G90 ; absolute positioning
G21 ; metric units
M83 ; relative extrusion
G92 E0
G1 F1200
```
**Problema**: Máquina usa aceleração padrão do firmware (pode ser muito alta)

### Depois (com M204)
```gcode
G90 ; absolute positioning
G21 ; metric units
M83 ; relative extrusion
M204 S500 ; set acceleration ← NOVO!
G92 E0
G1 F1200
```
**Vantagem**: Controle explícito da aceleração, comportamento previsível

## 🧪 Testes Realizados

### Teste 1: Inicialização
✅ Visualizador iniciou sem erros
✅ Aba "Avançado" visível
✅ Spinbox funcionando (range 100-5000)

### Teste 2: Carregamento de Preset
✅ Valor 500 carregado do JSON
✅ UI atualizada corretamente
✅ Settings sincronizadas

### Teste 3: Geração de G-code
**Comando esperado no header**:
```gcode
M204 S500 ; set acceleration
```

## 📁 Arquivos Modificados

1. **clay_settings.py** (+1 linha)
   - Novo parâmetro `acceleration`

2. **clay_gcode_core.py** (+1 linha)
   - Comando M204 no header

3. **integrated_clay_viewer.py** (+35 linhas)
   - Nova aba "Avançado"
   - Spinbox de aceleração
   - Sincronização com presets
   - Aplicação nas settings

4. **printer_presets.json** (+4 linhas)
   - Campo `acceleration` em todos os presets

## 🎓 Conceito: M204 - Set Acceleration

### Sintaxe
```gcode
M204 S<accel>    ; Define aceleração padrão
M204 P<print> T<travel>  ; Separar impressão/deslocamento
```

### Comportamento
- Define quantos mm/s² a máquina pode acelerar
- Afeta TODAS as mudanças de velocidade subsequentes
- Permanece ativo até próximo M204 ou reset

### Exemplo Prático
```gcode
M204 S500        ; Acelera suavemente
G1 X100 F600     ; Acelera de 0 → 600mm/min em 2 segundos
G1 X200 F1200    ; Acelera de 600 → 1200mm/min em 2 segundos
```

Com S1000:
```gcode
M204 S1000       ; Acelera 2x mais rápido
G1 X100 F600     ; Acelera de 0 → 600mm/min em 1 segundo
G1 X200 F1200    ; Acelera de 600 → 1200mm/min em 1 segundo
```

## 🔮 Expansões Futuras

### Possíveis Melhorias
1. **Aceleração separada** (impressão vs deslocamento):
   ```gcode
   M204 P500 T1000  ; P=print, T=travel
   ```

2. **Aceleração por tipo de movimento**:
   - Base: 300 mm/s² (mais suave)
   - Paredes: 500 mm/s² (padrão)
   - Deslocamentos: 1000 mm/s² (mais rápido)

3. **Perfis de aceleração**:
   - "Suave" (300)
   - "Balanceado" (500) ✅ atual
   - "Rápido" (800)
   - "Máximo" (1500)

4. **Jerk control** (M205):
   ```gcode
   M205 X10 Y10 Z5  ; Limitar mudanças instantâneas
   ```

## ✅ Checklist de Implementação

- [x] Parâmetro adicionado em `ClayPrintSettings`
- [x] Comando M204 no header do G-code
- [x] Nova aba "Avançado" na UI
- [x] Spinbox de aceleração funcionando
- [x] Sincronização com presets (carregar)
- [x] Sincronização com presets (aplicar)
- [x] Todos os 4 presets atualizados no JSON
- [x] Visualizador testado sem erros
- [x] Documentação criada

## 📝 Notas de Uso

1. **Valor padrão (500 mm/s²)** é conservador e seguro para a maioria das impressoras
2. **Não aumentar** sem testar incrementalmente (teste +100 por vez)
3. **Sintomas de aceleração muito alta**: ruído excessivo, perda de passos, camadas desalinhadas
4. **Sintomas de aceleração muito baixa**: impressão extremamente lenta

---

**Data de implementação**: Outubro 2025  
**Motivação**: Eliminar trancos durante mudanças de velocidade  
**Status**: ✅ Implementado e testado
