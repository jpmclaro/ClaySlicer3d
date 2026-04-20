# Correção: Velocidade e Fluxo do Ponto Central

## 🎯 Problema Relatado
> "a impressao do ponto inicial esta muito rapida, na subida o extruso deve ser mais lento e precisa aumentar o fluxo de extrusao"

Após primeira impressão, identificou-se que o ponto central estava imprimindo muito rápido e com pouco material.

## 🔍 Diagnóstico

### Antes da Correção
- **Velocidade**: Usava `first_layer_speed` (600 mm/min = 10 mm/s)
- **Fluxo**: 
  - 1º dip: 50% (0.5x)
  - 2º dip: 100% (1.0x)
- **Problema**: Movimento vertical muito rápido, material insuficiente

## ✅ Solução Implementada

### Arquivo: `clay_base_layers.py` - Método `_emit_center_point()`

**Linhas 262-303**: Nova lógica de velocidade e fluxo

#### 1. Velocidade Reduzida (30%)
```python
# Velocidade mais lenta para o ponto central (30% da velocidade da primeira camada)
center_point_speed = self.settings.first_layer_speed * 0.3
```

**Antes**: 600 mm/min (10 mm/s)  
**Depois**: 180 mm/min (3 mm/s) ← **70% mais lento** ✅

#### 2. Fluxo Aumentado (150%)
```python
# Aumentar fluxo para 150% para compensar a subida vertical
center_point_flow = 1.5
```

**Antes**: 50% no 1º dip, 100% no 2º dip  
**Depois**: 75% no 1º dip (1.5 × 0.5), 150% no 2º dip ← **+50% material** ✅

#### Código Completo
```python
def _emit_center_point(self, gcode_lines: List[str], cx: float, cy: float, base_z: float, z_target: float) -> None:
    if not self.settings.enable_center_point_extrusion:
        return
    height = max(0.05, self.settings.center_point_height)
    dips = max(1, int(self.settings.center_point_dips))
    gcode_lines.append("; CENTER_POINT_START")
    gcode_lines.append(self.gcode_gen.move_to(cx, cy, base_z, speed=self.settings.travel_speed, extrude=False))
    z_end = base_z + height
    
    # NOVO: Velocidade 30% e fluxo 150%
    center_point_speed = self.settings.first_layer_speed * 0.3
    center_point_flow = 1.5
    
    if dips == 1:
        gcode_lines.append(self.gcode_gen.move_to(
            cx, cy, z_end, 
            speed=center_point_speed,  # ← 70% mais lento
            extrude=True, 
            layer_height_override=height,
            flow_multiplier=center_point_flow  # ← 50% mais material
        ))
    else:
        # Primeira subida com fluxo reduzido (75% do flow_multiplier)
        gcode_lines.append(self.gcode_gen.move_to(
            cx, cy, z_end, 
            speed=center_point_speed,  # ← 70% mais lento
            extrude=True, 
            layer_height_override=height, 
            flow_multiplier=center_point_flow * 0.5  # 1.5 × 0.5 = 0.75
        ))
        gcode_lines.append(self.gcode_gen.move_to(cx, cy, base_z, speed=self.settings.travel_speed, extrude=False))
        # Segunda subida com fluxo completo (150%)
        gcode_lines.append(self.gcode_gen.move_to(
            cx, cy, z_end, 
            speed=center_point_speed,  # ← 70% mais lento
            extrude=True, 
            layer_height_override=height,
            flow_multiplier=center_point_flow  # 1.5x
        ))
    if abs(z_end - z_target) > 1e-6:
        gcode_lines.append(self.gcode_gen.move_to(cx, cy, z_target, speed=self.settings.travel_speed, extrude=False))
    gcode_lines.append("; CENTER_POINT_END")
```

## 🧪 Validação

### Teste com Configuração Real
```
CONFIGURAÇÃO:
- first_layer_speed: 600 mm/min (10 mm/s)
- center_point_height: 1.0 mm
- center_point_dips: 2

RESULTADOS:
```

#### G-code Gerado
```gcode
; CENTER_POINT_START
G1 X167.500 Y230.000 Z0.000 F1200      ; Move para base (sem extrusão)
G1 X167.500 Y230.000 Z1.000 E0.1447 F180   ; 1º dip: 180 mm/min, E=0.1447
G1 X167.500 Y230.000 Z0.000 F1200      ; Desce (sem extrusão)
G1 X167.500 Y230.000 Z1.000 E0.2894 F180   ; 2º dip: 180 mm/min, E=0.2894
G1 X167.500 Y230.000 Z3.300 F1200      ; Move para Z alvo
; CENTER_POINT_END
```

#### Análise
```
Movimento #1:
   Velocidade: 180 mm/min (3.0 mm/s) ✓
   Extrusão: 0.1447 mm (75% do fluxo = 1.5 × 0.5)
   
Movimento #2:
   Velocidade: 180 mm/min (3.0 mm/s) ✓
   Extrusão: 0.2894 mm (150% do fluxo = 1.5 × 1.0)
```

**Proporção de extrusão**: 0.2894 / 0.1447 = **2.0x** (2º dip tem o dobro do material) ✅

## 📊 Comparação Antes vs Depois

| Parâmetro | Antes | Depois | Mudança |
|-----------|-------|--------|---------|
| **Velocidade** | 600 mm/min | 180 mm/min | **-70%** 🐌 |
| **Fluxo (1º dip)** | 0.5x | 0.75x | **+50%** 📈 |
| **Fluxo (2º dip)** | 1.0x | 1.5x | **+50%** 📈 |
| **Tempo de execução** | ~0.1s | ~0.33s | **+230%** ⏱️ |
| **Material depositado** | Baixo | Alto | **+50%** 💪 |

## 🎯 Benefícios

### 1. Melhor Aderência
- Movimento mais lento permite que o material se compacte melhor
- Mais tempo para o material se acomodar na superfície

### 2. Mais Material
- Fluxo 150% garante que o ponto central fique bem preenchido
- Compensa a dificuldade de extrusão em movimentos verticais

### 3. Qualidade Estrutural
- Ponto central mais robusto serve como melhor âncora para a espiral
- Reduz risco de descolamento ou falha na primeira camada

### 4. Controle Progressivo
- 1º dip com 75% serve como "primer" (preparação)
- 2º dip com 150% consolida o ponto central

## 🔧 Ajustes Possíveis (se necessário)

### Se ainda muito rápido
Editar `clay_base_layers.py`, linha ~272:
```python
center_point_speed = self.settings.first_layer_speed * 0.2  # 20% ao invés de 30%
```

### Se ainda pouco material
Editar `clay_base_layers.py`, linha ~274:
```python
center_point_flow = 2.0  # 200% ao invés de 150%
```

### Se muito material
```python
center_point_flow = 1.2  # 120% ao invés de 150%
```

### Se muito lento
```python
center_point_speed = self.settings.first_layer_speed * 0.5  # 50% ao invés de 30%
```

## 📐 Cálculo de Extrusão

### Fórmula Base
```
E = (distância × largura × altura / área_filamento) × clay_factor × flow_rate × flow_multiplier
```

### Para o Ponto Central
```
Altura: 1.0 mm (center_point_height)
Largura: 3.3 mm (extrusion_width)
Clay factor: 0.5
Flow rate: 1.0
Flow multiplier: 1.5 (NOVO!)

Volume = 1.0 × 3.3 × 1.0 = 3.3 mm³
Theoretical = 3.3 / (π × (3.3/2)²) = 3.3 / 8.553 = 0.386
E = 0.386 × 0.5 × 1.0 × 1.5 = 0.289 mm ✓
```

## 🎓 Conceito: Flow Multiplier

O `flow_multiplier` é um **multiplicador local** que afeta apenas movimentos específicos:

- **Global**: `flow_rate` (ajustado na UI, afeta tudo)
- **Local**: `flow_multiplier` (código específico, afeta movimento individual)
- **Final**: `E = ... × flow_rate × flow_multiplier`

### Hierarquia
```
Base calculation
    ↓
× clay_factor (0.5)
    ↓
× flow_rate (UI, ex: 1.0)
    ↓
× flow_multiplier (código, ex: 1.5)
    ↓
E final
```

## 📁 Arquivos Modificados

1. **clay_base_layers.py** (+5 linhas efetivas)
   - Método `_emit_center_point()`: linhas 262-303
   - Adicionadas variáveis `center_point_speed` e `center_point_flow`
   - Aplicado `flow_multiplier=center_point_flow` em todos os move_to

2. **test_center_point_speed.py** (NOVO)
   - Script de validação específico para ponto central
   - Extrai e analisa comandos do CENTER_POINT
   - Valida velocidade e extrusão

## ✅ Status

- [x] Velocidade reduzida para 30%
- [x] Fluxo aumentado para 150%
- [x] Aplicado em ambos os dips
- [x] G-code validado
- [x] Teste confirma valores corretos
- [x] Documentação criada

## 🎉 Resultado

O ponto central agora imprime:
- ✅ **70% mais devagar** (180 mm/min ao invés de 600 mm/min)
- ✅ **50% mais material** (fluxo 1.5x ao invés de 1.0x)
- ✅ **Melhor aderência** (mais tempo para compactação)
- ✅ **Estrutura mais robusta** (ponto central bem preenchido)

### Exemplo Visual
```
ANTES:  ○  (rápido, pouco material, pode falhar)
DEPOIS: ●  (lento, muito material, robusto)
```

---

**Data de correção**: Outubro 2025  
**Motivação**: Feedback da primeira impressão real  
**Status**: ✅ **CORRIGIDO e VALIDADO**
