# Comparação Visual: Planar vs. Non-Planar

## Modo Planar (Padrão)

```
Vista Lateral do Objeto              Camadas Geradas
   
      ╱╲                                ─────────  ← Z_top (uniforme)
     ╱  ╲                               ─────────
    ╱    ╲                              ─────────
   ╱      ╲                             ─────────
  ╱        ╲                            ─────────
 ╱          ╲                           ─────────
╱____________╲                          ══════════ ← Base
                                        
Características:
✓ Camadas horizontais uniformes
✓ Altura de camada constante
✓ Rápido e simples
✗ Não segue forma real do topo
✗ "Escadas" visíveis em bordas inclinadas
```

## Modo Non-Planar (Experimental)

```
Vista Lateral do Objeto              Camadas Geradas
   
      ╱╲                                ╱────────╲  ← Z_top(θ) variável
     ╱  ╲                              ╱──────────╲
    ╱    ╲                            ╱────────────╲
   ╱      ╲                          ╱──────────────╲
  ╱        ╲                        ╱────────────────╲
 ╱          ╲                      ╱──────────────────╲
╱____________╲                    ══════════════════════ ← Base
                                        
Características:
✓ Camadas seguem forma 3D real
✓ Transições suaves no topo
✓ Fidelidade à geometria original
✗ Mais lento (cálculos complexos)
✗ Requer calibração precisa em Z
```

## Fluxo de Processamento

### Planar (Tradicional)

```
1. Análise do Mesh
   └─> Determina Z_min e Z_max

2. Fatiamento Horizontal
   └─> Z = Z_min + k * layer_height
   └─> Extrai contornos em cada Z
   
3. Espiral Helicoidal
   └─> Conecta contornos subindo uniformemente
   └─> Interpola pontos entre camadas
   
4. G-code
   └─> G1 X Y Z E (Z aumenta linearmente)
```

### Non-Planar (Orgânico)

```
1. Análise do Mesh
   └─> Determina Z_min e Z_max
   └─> DETECTA BORDA SUPERIOR

2. Perfil Superior z_top(θ)
   └─> Para cada ângulo θ (0° - 360°):
       └─> Encontra altura máxima naquela direção
       └─> Cria perfil 3D variável

3. Fatiamento Adaptativo
   └─> Para cada camada k e ângulo θ:
       └─> Z = Z_min + (k/N) * (z_top(θ) - Z_min)
       └─> Plano VERTICAL × Mesh
       └─> Encontra ponto na superfície

4. Espiral Orgânica
   └─> Conecta pontos seguindo forma real
   └─> Z varia conforme perfil detectado

5. G-code
   └─> G1 X Y Z E (Z varia organicamente)
```

## Exemplo Numérico

### Objeto: Vaso com borda ondulada

```
Dimensões:
- Base: R = 40mm, Z = 0mm
- Topo: R = 50mm, Z = 60-80mm (ondulado)
```

### Camadas Planar (layer_height = 2mm)

```
Camada  | Z (mm) | Observação
--------|--------|---------------------------
0       | 1      | Base (uniforme)
1       | 3      | 
2       | 5      |
...     | ...    |
30      | 61     | Topo (corta ondulações)
31      | 63     |
...     | ...    |
40      | 81     | Último slice (perde detalhes)
```

**Problema:** Camadas horizontais "cortam" as ondulações do topo.

### Camadas Non-Planar (layer_height = 2mm, angular_step = 1°)

```
Camada | Ângulo | Z_target (mm) | Observação
-------|--------|---------------|---------------------------
0      | 0°     | 60            | Ponto mais baixo da onda
0      | 90°    | 80            | Pico da onda
0      | 180°   | 60            | Vale
0      | 270°   | 80            | Pico
1      | 0°     | 62            | Subindo na forma
1      | 90°    | 82            | Seguindo pico
...    | ...    | ...           |
30     | 0°     | 60            | Topo seguindo ondulações
30     | 90°    | 80            | 
```

**Vantagem:** Cada ponto segue a altura real do objeto naquela direção.

## Performance

### Planar
```
Tempo de processamento: ~2-5 segundos
Pontos gerados: ~5.000 - 15.000
Memória: ~50MB
```

### Non-Planar
```
Tempo de processamento: ~10-30 segundos
Pontos gerados: ~20.000 - 100.000
Memória: ~200MB

Fatores que influenciam:
- angular_step (menor = mais pontos)
- Complexidade do mesh
- Número de camadas
```

## Qualidade Visual

### Planar - Vista Superior

```
  ╔═══════════╗
  ║ ─── ─── ─ ║  ← Camadas horizontais
  ║─── ─── ───║     visíveis
  ║ ─── ─── ─ ║
  ║─── ─── ───║
  ╚═══════════╝
```

### Non-Planar - Vista Superior

```
  ╔═══════════╗
  ║ ╱╲  ╱╲  ╱╲║  ← Camadas seguem
  ║╱  ╲╱  ╲╱  ║     ondulações
  ║╲  ╱╲  ╱╲  ║
  ║ ╲╱  ╲╱  ╲╱║
  ╚═══════════╝
```

## Casos de Uso Ideais

### Planar é melhor para:
```
1. Cilindros          ████     Z uniforme
                      ████
                      ████
                      
2. Caixas            ╔════╗    Paredes retas
                     ║    ║
                     ╚════╝
                     
3. Impressão rápida   ⚡       Velocidade prioritária
```

### Non-Planar é melhor para:
```
1. Vasos ondulados    ╱╲╱╲     Forma complexa
                     ╱    ╲
                    ╱      ╲
                    
2. Esculturas        🗿        Arte/estética
                              
3. Bordas irregulares ∿∿∿∿    Precisão da forma
```

## Parâmetros Críticos

### angular_step (Resolução)

```
0.5° → 720 pontos/camada   ████████ (Alta resolução)
1.0° → 360 pontos/camada   ████     (Normal - recomendado)
2.0° → 180 pontos/camada   ██       (Rápida)
5.0° → 72 pontos/camada    █        (Baixa)
```

### angle_threshold (Detecção)

```
45° → Bordas suaves         ∼∼∼∼    Detecta mais bordas
60° → Bordas moderadas      ∧∧∧∧    Padrão
75° → Bordas acentuadas     ╱╲╱╲    Apenas arestas fortes
```

## Resumo da Decisão

```
┌─────────────────────────────────────────────┐
│ Use PLANAR quando:                          │
├─────────────────────────────────────────────┤
│ ✓ Objeto tem paredes uniformes/verticais    │
│ ✓ Velocidade é prioridade                   │
│ ✓ Primeira impressão/teste                  │
│ ✓ Calibração Z não é precisa                │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Use NON-PLANAR quando:                      │
├─────────────────────────────────────────────┤
│ ✓ Forma orgânica/complexa                   │
│ ✓ Bordas irregulares/onduladas              │
│ ✓ Qualidade visual é prioridade             │
│ ✓ Calibração Z é precisa                    │
└─────────────────────────────────────────────┘
```

---

**Dica:** Teste primeiro em modo **Planar** para verificar configurações básicas, depois experimente **Non-Planar** para comparar resultados.
