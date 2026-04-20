# Modo Non-Planar - Documentação

## 📋 Visão Geral

O **Modo Non-Planar** é uma abordagem experimental de geração de paredes que respeita a forma orgânica tridimensional do objeto, ao invés de usar camadas horizontais uniformes.

## 🎯 Objetivo

Gerar espirais que **seguem o contorno real** do objeto em 3D, mantendo a forma original durante a impressão. Ideal para:

- ✅ Formas orgânicas/complexas
- ✅ Objetos com topo irregular
- ✅ Peças artísticas/escultóricas
- ✅ Vasos com bordas onduladas

## 🔧 Como Funciona

### 1. Detecção da Borda Superior

O algoritmo identifica a borda superior do objeto analisando:
- **Ângulo diédrico** entre faces adjacentes (> 60° por padrão)
- **Posição Z** (apenas metade superior)
- **Normal das faces** (apontando para cima)

Para cada ângulo θ, determina o **z_top(θ)** - altura máxima naquela direção radial.

### 2. Distribuição de Camadas

Ao invés de fatiar em planos horizontais, o algoritmo:
1. Define número de camadas baseado em `layer_height`
2. Para cada camada k e ângulo θ:
   - Calcula altura alvo: `z = base_z + (k/N) * (z_top(θ) - base_z)`
   - Encontra ponto na superfície usando interseção **plano vertical × mesh**
3. Conecta pontos formando espiral que **sobe seguindo a forma**

### 3. Geração da Espiral

```
Para cada ponto da espiral:
  - Ângulo varia continuamente: θ = θ₀ + Δθ
  - Altura varia gradualmente: z = f(θ, camada)
  - Ponto encontrado por interseção geométrica
  - Espiral contínua sem saltos
```

## ⚙️ Parâmetros

### Checkbox Principal
**Localização:** Aba "Avançado" → "Modo Non-Planar (Experimental)"

```python
enable_nonplanar_mode: bool = False
```

### Parâmetros de Configuração

| Parâmetro | Padrão | Faixa | Descrição |
|-----------|--------|-------|-----------|
| `nonplanar_angular_step_deg` | 1.0° | 0.1° - 10.0° | Resolução angular (quanto menor, mais pontos) |
| `nonplanar_angle_threshold_deg` | 60.0° | 10° - 90° | Limiar para detectar borda superior |
| `nonplanar_z_epsilon` | 0.03 mm | 0.0 - 1.0 mm | Recuo em Z no topo (evita ultrapassar) |

### Recomendações

#### Alta Resolução (objetos pequenos/detalhados)
```python
nonplanar_angular_step_deg = 0.5°    # Mais pontos
nonplanar_angle_threshold_deg = 45°  # Detecta bordas mais suaves
```

#### Resolução Normal (uso geral)
```python
nonplanar_angular_step_deg = 1.0°    # Padrão
nonplanar_angle_threshold_deg = 60°  # Padrão
```

#### Baixa Resolução (objetos grandes/rápidos)
```python
nonplanar_angular_step_deg = 2.0°    # Menos pontos
nonplanar_angle_threshold_deg = 70°  # Apenas bordas acentuadas
```

## 📐 Implementação Técnica

### Arquitetura

```
clay_walls_nonplanar.py
├── NonPlanarWallPlanner
│   ├── plan_nonplanar_walls()        # Método principal
│   ├── _detect_top_profile()         # Detecção de z_top(θ)
│   ├── _plane_segments()             # Interseção plano × mesh
│   ├── _point_on_outer_at_z()        # Ponto na superfície em Z
│   └── _generate_spiral_path()       # Gera espiral contínua
```

### Integração

```python
# clay_gcode_generator_definitive.py
def generate_gcode(self, polydata):
    ...
    # Base (sempre igual)
    last_point = self.base_builder.generate_base(...)
    
    # Paredes: escolher planejador
    if self.settings.enable_nonplanar_mode:
        wall_points = self.nonplanar_planner.plan_nonplanar_walls(...)
    else:
        wall_points = self.wall_planner.plan_spiral_walls(...)
    
    # Emitir G-code
    ...
```

## 🎨 Interface do Usuário

### Localização
**Aba: Avançado**

### Elementos
1. **Checkbox:** "Ativar modo Non-Planar"
2. **Info Box:** Explicação e avisos
3. **Grupo de Parâmetros:**
   - Passo angular (resolução)
   - Limiar de borda superior
   - Recuo Z no topo

### Comportamento
- Parâmetros ficam **desabilitados** quando checkbox está desmarcado
- Valores salvos nas configurações globais
- Sincronizado com `apply_main_panel_controls()`

## 🧪 Testes

### Script de Teste
```bash
python test_nonplanar.py
```

Executa dois testes:
1. **Modo Planar** (controle) → `test_planar_output.gcode`
2. **Modo Non-Planar** → `test_nonplanar_output.gcode`

### Validação Manual
```python
# Verificar marcador no G-code
grep "NONPLANAR_MODE_ENABLED" test_nonplanar_output.gcode

# Contar comandos de extrusão
grep "G1.*E" test_nonplanar_output.gcode | wc -l
```

## ⚠️ Limitações e Considerações

### Limitações Conhecidas

1. **Geometrias com Furos/Ilhas**
   - Assume objeto sólido sem furos internos
   - Detecta apenas contorno externo

2. **Objetos com Topo Plano**
   - Se não detectar borda superior, usa topo uniforme (fallback)
   - Pode não trazer benefícios vs. modo planar

3. **Performance**
   - Mais lento que modo planar (muitas interseções geométricas)
   - Recomendado `angular_step >= 1.0°`

4. **Calibração Z**
   - Requer calibração precisa do eixo Z
   - Pequenos erros podem causar colisões

### Quando NÃO Usar

❌ Objetos cilíndricos uniformes (use modo planar)  
❌ Formas com paredes verticais retas  
❌ Impressão rápida (prioridade de velocidade)  
❌ Primeiras impressões (testar com planar primeiro)  

### Quando Usar

✅ Vasos com bordas onduladas  
✅ Formas orgânicas/escultóricas  
✅ Objetos com topo irregular  
✅ Peças artísticas onde forma importa  

## 🔬 Algoritmo Detalhado

### Pseudo-código

```python
def plan_nonplanar_walls(polydata, start_point):
    # 1. Extrair mesh
    V, F = extract_triangulated_mesh(polydata)
    
    # 2. Detectar perfil superior
    top_edges = find_top_edges(V, F, angle_threshold)
    z_top[θ] = interpolate_z_from_edges(top_edges, θ)
    
    # 3. Pré-calcular interseções
    for θ in range(0°, 360°, Δθ):
        planes[θ] = intersect_vertical_plane(mesh, θ)
    
    # 4. Gerar espiral
    points = []
    for layer in range(N_layers):
        for θ in range(0°, 360°, Δθ):
            z_target = base_z + (layer/N) * (z_top[θ] - base_z)
            point = find_point_at_z(planes[θ], z_target)
            points.append(point)
    
    return points
```

### Complexidade

- **Tempo:** O(N × M × T)
  - N = número de faces do mesh
  - M = número de ângulos (360° / Δθ)
  - T = número de camadas

- **Espaço:** O(M × T)
  - Cache de interseções plano × mesh

## 📊 Comparação: Planar vs. Non-Planar

| Aspecto | Planar | Non-Planar |
|---------|--------|------------|
| **Velocidade** | Rápido | Lento |
| **Complexidade** | Simples | Complexa |
| **Fidelidade à forma** | Aproximada | Alta |
| **Calibração requerida** | Normal | Precisa |
| **Casos de uso** | Geral | Formas orgânicas |
| **Suavidade** | Camadas visíveis | Transições suaves |

## 🚀 Próximos Passos

### Melhorias Futuras
- [ ] Suavização adaptativa do perfil z_top(θ)
- [ ] Detecção automática de quando usar non-planar
- [ ] Otimização de performance (cache mais agressivo)
- [ ] Suporte a múltiplos contornos (ilhas/furos)
- [ ] Preview visual do perfil detectado na UI
- [ ] Exportação do perfil para análise externa

### Testes Necessários
- [ ] Validar com impressão real em argila
- [ ] Testar com objetos de referência (esfera, cone, ondulado)
- [ ] Medir precisão dimensional
- [ ] Avaliar qualidade superficial

## 📚 Referências

- **Fatiador Adaptativo:** `fatiador.py` - Algoritmo original de detecção de borda
- **Trimesh Library:** Interseções plano × mesh
- **Shapely:** Manipulação geométrica 2D
- **VTK:** Processamento de malhas 3D

---

**Versão:** 1.0  
**Data:** 13/10/2025  
**Status:** ✅ Experimental - Pronto para testes

**Autor:** Sistema de Impressão 3D em Argila
