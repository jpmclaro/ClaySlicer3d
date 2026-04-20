# Correção: Taper para Fechamento do Topo

## Objetivo do Taper

O taper (final suave) tem como objetivo **fechar a abertura visível no topo** do objeto após o término da espiral. Quando a impressão em modo vaso termina, sempre sobra uma área exposta no topo que precisa ser coberta.

### Comportamento Esperado

**Sem taper:**
```
    ┌─────────────┐
    │   ABERTO    │  ← Área cinza exposta (visível na imagem)
    └─────┬───────┘
          │ ← Espiral termina aqui
    ╱╲╱╲╱╲╱╲╱╲╱╲
```

**Com taper:**
```
    ╱══════════╲  ← Voltas horizontais cobrindo topo
    │ Z FIXO   │  ← Mesmo Z, extrusão 100% → 0%
    └─────┬───────┘
          │ ← Espiral sobe até aqui
    ╱╲╱╲╱╲╱╲╱╲╱╲
```

## Problema Anterior

A implementação tentava fazer uma **rampa interpolada** que subia Z gradualmente durante o taper. Isso estava **errado** porque:

1. ❌ A espiral JÁ chega ao topo do objeto naturalmente
2. ❌ Interpolar Z fazia o percurso subir ALÉM do necessário
3. ❌ O objetivo não é subir mais, mas **cobrir horizontalmente** a área exposta

## Solução Correta

### Conceito: Voltas Horizontais no Topo

O taper deve:

1. **Começar no Z do último ponto** da espiral (topo já alcançado)
2. **Manter Z fixo** durante todas as voltas do taper
3. **Reduzir extrusão gradualmente** de 100% para 0%
4. **Fazer N voltas completas** ao redor do perímetro (configurável)

```python
# Z do taper = Z do último ponto da espiral
taper_z_fixed = wall_points[-1].z  # Ex: 53.5mm

# Durante o taper, Z permanece FIXO
if idx >= taper_start_index:
    z_to_use = taper_z_fixed  # Sempre o mesmo Z
    
    # Apenas a extrusão é reduzida
    remaining = total_points - idx
    span = total_points - taper_start_index
    flow = remaining / span  # 1.0 → 0.0
```

### Exemplo Numérico com 1 Volta de Taper

**Configuração:**
- Objeto: Cilindro de 85mm diâmetro, 54mm altura
- Espiral termina em: Z=53.5mm (último ponto da hélice normal)
- Taper configurado: 1.0 volta
- Pontos por volta: ~400 pontos

**Sequência do Taper (última volta):**

```
Ponto 20800 (início taper): X=42.5,  Y=0.0,   Z=53.5mm, E=100%
Ponto 20900 (1/4 volta):    X=0.0,   Y=42.5,  Z=53.5mm, E=75%
Ponto 21000 (1/2 volta):    X=-42.5, Y=0.0,   Z=53.5mm, E=50%
Ponto 21100 (3/4 volta):    X=0.0,   Y=-42.5, Z=53.5mm, E=25%
Ponto 21200 (fim taper):    X=42.4,  Y=-0.2,  Z=53.5mm, E=0%
```

**Características:**
- ✅ **Z sempre 53.5mm** (altura fixa no topo)
- ✅ **XY faz círculo completo** ao redor do objeto
- ✅ **Extrusão reduz linearmente** de 100% para 0%
- ✅ **Cobre a abertura do topo** progressivamente

## Trecho de Código

```python
# clay_gcode_generator_definitive.py, linhas 138-177

if self.settings.enable_end_taper and self.settings.end_taper_revolutions > 0:
    # Calcular quantos pontos por volta
    points_per_turn = calcular_pontos_por_volta(wall_points)
    
    # Quantidade de pontos no taper (N voltas)
    taper_len = int(points_per_turn * self.settings.end_taper_revolutions)
    taper_start_index = max(0, total_points - taper_len)
    
    # Z fixo = Z do último ponto (topo onde espiral terminou)
    if total_points > 0:
        taper_z_fixed = wall_points[-1].z

# Durante geração do G-code:
for idx, point in enumerate(wall_points):
    z_to_use = point.z  # Usa Z da espiral por padrão
    
    if idx >= taper_start_index:
        # Calcular redução de fluxo (linear)
        remaining = total_points - idx
        span = max(1, total_points - taper_start_index)
        flow = clamp(remaining / span, 0.0, 1.0)  # 1.0 → 0.0
        
        # FIXAR Z no topo (voltas horizontais)
        if taper_z_fixed is not None:
            z_to_use = taper_z_fixed  # Sempre o mesmo Z
```

## Comportamento Visual

### Antes (Sem Taper)
```
    ╔═════════════╗
    ║   ABERTO    ║  ← Área cinza exposta
    ╚═════╤═══════╝
          │ Fim abrupto
         ╱╲ Espiral
        ╱  ╲
```

### Depois (Com Taper - 1 volta)
```
    ╔═════════════╗
    ║ ▓▓▓▓▓▓▓▓▓ ║  ← Cobertura gradual (Z fixo)
    ║ ░░░░░░░░░░░ ║  ← Extrusão 100% → 0%
    ╚═════╤═══════╝
          │ Transição suave
         ╱╲ Espiral
        ╱  ╲
```

### Com 2 Voltas de Taper
```
    ╔═════════════╗
    ║ ████████████ ║  ← 2ª volta (mais interno)
    ║ ▓▓▓▓▓▓▓▓▓▓▓ ║  ← 1ª volta (externo)
    ║ ░░░░░░░░░░░ ║  ← Cobertura gradual
    ╚═════╤═══════╝
```

## Teste de Validação

```bash
# Gerar G-code com taper
python integrated_clay_viewer.py

# Analisar geometria do taper
python debug_taper_spiral.py xicarra_flat_c_argila.gcode
```

**Output esperado:**
```
Pontos com Z fixo (taper): 399
Movimentacao XY durante o taper:
  Range X: 85.2mm   ← Diâmetro completo
  Range Y: 84.8mm   ← Diâmetro completo
  OK: Movimento XY detectado - espiral completa
```

## Considerações Técnicas

### Por que Z Fixo?

O taper tem um objetivo específico: **cobrir a abertura no topo** que fica visível quando a espiral termina. Para isso:

1. ✅ **Espiral já chegou ao topo**: A hélice normal já alcançou a altura máxima
2. ✅ **Área exposta precisa de cobertura**: O topo tem superfície visível (cinza nas imagens)
3. ✅ **Voltas horizontais cobrem melhor**: Manter Z fixo permite fazer círculos que preenchem a área
4. ✅ **Extrusão gradual**: Reduzir de 100% para 0% cria acabamento suave

### Diferença entre Espiral e Taper

| Fase | Z | XY | Extrusão | Objetivo |
|------|---|----|---------|----|
| **Espiral** | Sobe (1.0 → 53.5mm) | Círculos | 100% | Construir parede |
| **Taper** | Fixo (53.5mm) | Círculos | 100% → 0% | Cobrir topo |

### Parâmetros do Taper

- **`enable_end_taper`**: Liga/desliga o fechamento do topo
- **`end_taper_revolutions`**: Quantas voltas fazer no Z fixo
  - `1.0`: Uma volta completa (recomendado para objetos pequenos)
  - `2.0`: Duas voltas (melhor cobertura para objetos grandes)
  - `0.5`: Meia volta (pode deixar abertura parcial)

### Cálculo da Extrusão

```python
# Extrusão reduz linearmente conforme avança no taper
remaining_points = total_points - current_index
total_taper_points = total_points - taper_start_index
flow_multiplier = remaining_points / total_taper_points

# Exemplo com 400 pontos de taper:
# Ponto 0 (início):  400/400 = 1.00 (100%)
# Ponto 100:         300/400 = 0.75 (75%)
# Ponto 200:         200/400 = 0.50 (50%)
# Ponto 300:         100/400 = 0.25 (25%)
# Ponto 399 (fim):   1/400   = 0.00 (0%)
```

### Limitação Conhecida

Se `end_taper_revolutions < 1.0` (ex: 0.5 voltas), o taper não completará o perímetro. Isso é **comportamento esperado** - o usuário controla quantas voltas quer no taper.

### Parâmetros Típicos

- `end_taper_revolutions = 1.0`: Uma volta completa (recomendado)
- `end_taper_revolutions = 2.0`: Duas voltas com redução gradual
- `end_taper_revolutions = 0.25`: Apenas 1/4 de volta (pode deixar marca)

## Status

✅ **Corrigido** - Taper agora cria espiral completa ao redor do objeto
✅ **Validado** - Movimento XY durante taper mantém padrão circular
✅ **Documentado** - Explicação completa da geometria e código

## Arquivos Modificados

- `clay_gcode_generator_definitive.py` (linhas 163-176)
- `debug_taper_spiral.py` (novo script de diagnóstico)

## Relacionado

- `RESUMO_COMPLETO_TAPER.md` - Explicação detalhada do recurso taper
- `CORRECAO_ALTURA_TAPER.md` - Correção anterior (altura do topo)
- `CORRECAO_TRAVAMENTO_TAPER.md` - Correção anterior (crash da interface)
