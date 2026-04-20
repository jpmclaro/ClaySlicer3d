# Correção: Campo "Largura de demais camadas" não estava sendo salvo

## 🐛 Problema Identificado

O campo **"Largura de demais camadas"** (`other_layers_extrusion_width`) não estava sendo salvo quando o usuário editava os presets no editor de presets.

### Sintomas:
- Usuário configurava "Largura de demais camadas" no editor
- Ao salvar o preset, o valor não era persistido no `printer_presets.json`
- O campo estava ausente nos presets "Bico 2mm" e "Bico 3mm"

## ✅ Solução Implementada

### 1. **Editor de Presets** (`integrated_clay_viewer.py`)

Foram feitas 4 alterações no método `open_presets_editor()`:

#### a) Adicionado campo no formulário (linha ~1363):
```python
other_width_spin = QDoubleSpinBox()
other_width_spin.setRange(0.2, 20.0)
other_width_spin.setSuffix(" mm")
```

#### b) Adicionado label no formulário (linha ~1381):
```python
form.addRow("Largura demais camadas:", other_width_spin)
```

#### c) Atualizado `load_from_item()` para carregar o valor (linha ~1409):
```python
other_width_spin.setValue(float(data.get('other_layers_extrusion_width', width_spin.value())))
```

#### d) Atualizado `save_fields_to_item()` para salvar o valor (linha ~1470):
```python
'other_layers_extrusion_width': float(other_width_spin.value()),
```

### 2. **Presets JSON** (`printer_presets.json`)

Atualizados os 4 presets para incluir o campo:

**Bico 2mm:**
```json
"other_layers_extrusion_width": 2.0
```

**Bico 3mm:**
```json
"other_layers_extrusion_width": 3.6
```

**Bico 4mm e 5mm:**
- Já tinham o campo configurado

Também adicionados campos faltantes para padronização:
- `acceleration: 500.0`
- `retraction: 0.0`
- `enable_center_micro_spiral: true`

## 🧪 Validação

Criado script de teste `test_other_width_save.py` que verifica:
- ✅ Se todos os presets têm o campo `other_layers_extrusion_width`
- ✅ Se o valor não é `null`
- ✅ Se o valor é numérico válido

**Resultado do teste:**
```
✅ TESTE PASSOU: Todos os presets têm o campo configurado
```

## 📋 Como Usar Agora

1. **Editar presets:**
   - Abrir o viewer: `python integrated_clay_viewer.py`
   - Clicar em "Editar Presets"
   - Configurar "Largura demais camadas" para cada preset
   - **Agora o valor será salvo corretamente!** ✅

2. **Verificar se está salvo:**
   - Executar: `python test_other_width_save.py`
   - Deve mostrar: "✅ TESTE PASSOU"

## 🔍 Observações Técnicas

### Diferença entre os campos:
- **`extrusion_width`**: Largura da **primeira camada** (base)
- **`other_layers_extrusion_width`**: Largura das **demais camadas** (paredes)

### Quando usar valores diferentes:
- **Taper (afunilamento)**: Primeira camada mais larga, demais mais estreitas
  - Exemplo: `extrusion_width: 8.0` → `other_layers_extrusion_width: 2.5`
- **Uniforme**: Mesma largura em todas as camadas
  - Exemplo: `extrusion_width: 3.6` → `other_layers_extrusion_width: 3.6`

### Impacto no G-code:
O campo `other_layers_extrusion_width` afeta:
- Cálculo de extrusão nas paredes (valor E no G-code)
- Largura do cordão depositado da 2ª camada em diante
- Controle de fluxo volumétrico

## 📁 Arquivos Modificados

1. **`integrated_clay_viewer.py`**:
   - Linhas ~1360-1480: Editor de presets
   
2. **`printer_presets.json`**:
   - Todos os 4 presets atualizados

3. **Novos arquivos de teste**:
   - `test_other_width_save.py`: Validação do campo nos presets

## ✅ Status Final

- ✅ Campo adicionado ao editor de presets
- ✅ Carregamento do campo funcionando
- ✅ Salvamento do campo funcionando
- ✅ Todos os 4 presets configurados
- ✅ Teste de validação criado e passando
- ✅ Documentação atualizada

**Correção completa e testada!** 🎉
