# ClaySlicer3d

Gerador e visualizador de G-code contínuo (vase mode) especializado em impressão 3D de argila/cerâmica.

## Visão Geral

O ClaySlicer3d opera em dois modos:

- **Modo Malha** — carrega um arquivo STL/OBJ e fatia o volume para gerar o percurso de extrusão.
- **Modo Paramétrico** — gera o percurso diretamente a partir de parâmetros geométricos, sem necessidade de malha. Suporta quatro tipos de objeto: `prato`, `copo`, `jarra` e `garrafa`.

Em ambos os modos, a interface integrada (PyQt5 + VTK) exibe a simulação 3D do cordão contínuo antes da exportação do G-code.

## Funcionalidades

### Modo Paramétrico
- Objetos: prato, copo, jarra (com pescoço), garrafa (corpo + ombro + gargalo)
- Keyframes de perfil: raio definido por altura com interpolação suave (fillet / s-curve) ou cantos vivos
- Até dois pontos intermediários de raio opcionais por objeto (habilitáveis individualmente)
- Espiral archimediana na base (ponto central + micro-espiral) e na parede helicoidal
- Densidade de espiral controlada por `n_revs = max(n_radial, n_z)` — garante cobertura sem trança nem espaçamento excessivo
- Ângulo da costura (seam) configurável
- Altura de camada independente para base, arco de transição e parede

### Modo Malha (STL/OBJ)
- Fatiamento com Shapely, amostragem peririmétrica adaptativa
- Modo planar (vase mode padrão)
- Modo non-planar experimental: "warping virtual" que endireita o objeto, fatia, e aplica "unwarping" para gerar G-code orgânico

### Extrusão e Controle
- Extrusão contínua sem retração
- Fluxo relativo com limitação volumétrica configurável
- Taper de finalização (redução gradual do fluxo no fechamento)
- Compensação de curvatura lateral nas paredes
- Pressure Advance opcional
- Rampa de altura na transição base→parede

### Interface
- Visualização 3D VTK com tubo elíptico representando o cordão real
- Abas verticais de parâmetros (Básico / Base / Parede / Paramétrico / Avançado)
- Sistema de presets salvo em `printer_presets.json`
- Sincronização bidirecional entre UI e configurações

## Estrutura do Projeto

```
ClaySlicer3d/
│
├── integrated_clay_viewer.py          # Ponto de entrada — interface PyQt5 + VTK
├── control_panel_widget.py            # Painel de controle (abas de parâmetros)
├── vtk_viewport.py                    # Viewport 3D VTK
├── simulation_service.py              # Serviço de geração de simulação
├── preset_service.py                  # Carregamento/salvamento de presets
│
├── clay_gcode_generator_definitive.py # Orquestrador: decide modo e coordena geração
├── clay_parametric_path_planner.py    # Planejador de percurso paramétrico (núcleo)
├── clay_base_layers.py                # Base: espiral archimediana + micro-espiral
├── clay_walls.py                      # Paredes planares (vase mode)
├── clay_walls_nonplanar.py            # Paredes non-planares (warping virtual)
│
├── clay_gcode_core.py                 # Escrita de G-code (movimentos, fluxo, header)
├── clay_geometry.py                   # Geometria 2D (interseções, offsets — Shapely)
├── clay_geometry_utils.py             # Utilitários geométricos gerais
├── clay_mesh.py                       # Análise e fatiamento de malhas 3D
├── clay_models.py                     # Estruturas de dados (Point3D, MeshAnalysis)
├── clay_settings.py                   # Dataclass ClayPrintSettings (todos os parâmetros)
├── clay_spiral_sampling.py            # Algoritmos de amostragem de espiral
├── clay_presets_manager.py            # Gestão interna de presets
├── clay_simulation_thread.py          # Thread de simulação assíncrona
├── clay_view_cube.py                  # Cubo de orientação na viewport
│
├── printer_presets.json               # Perfis de impressão salvos
├── requirements.txt                   # Dependências Python
├── run_clay_viewer.bat                # Script de execução rápida (Windows)
│
├── models/                            # Arquivos STL/OBJ de entrada
├── gcode_output/                      # G-codes exportados
├── docs/                              # Documentação técnica detalhada
└── BCK/                               # Backups e arquivos legados
```

## Instalação e Execução

**Pré-requisitos:** Python 3.10+

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar (Windows)
.\.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

**Executar:**
```cmd
run_clay_viewer.bat
```
ou:
```bash
python integrated_clay_viewer.py
```

## Uso Básico

### Modo Malha
1. Clique em **"Carregar STL/OBJ"** e selecione um arquivo da pasta `models/`.
2. Escolha um preset ou ajuste os parâmetros nas abas.
3. Clique em **"Gerar Simulação"** para visualizar o percurso.
4. Clique em **"Salvar G-code"** para exportar.

### Modo Paramétrico
1. Na aba **"Paramétrico"**, ative **"Modo Paramétrico"**.
2. Escolha o tipo de objeto e configure as dimensões.
3. Opcionalmente, ative pontos intermediários de raio para perfis não-lineares.
4. Clique em **"Gerar Simulação"** e depois **"Salvar G-code"**.

## Detalhes Técnicos

| Módulo | Responsabilidade |
|---|---|
| `clay_parametric_path_planner.py` | Espiral base (Archimediana), arco de transição e parede helicoidal com `n_revs = max(n_radial, n_z)` |
| `clay_base_layers.py` | Base sólida com micro-espiral central para evitar vazio |
| `clay_walls_nonplanar.py` | Warping virtual → fatiamento planar → unwarping para G-code orgânico |
| `clay_gcode_generator_definitive.py` | Seleção de estratégia (malha vs paramétrico, planar vs non-planar) |
| `clay_settings.py` | Dataclass com todos os parâmetros de impressão e configuração |

### Fórmula de densidade da espiral (parede)
Para cada trecho entre keyframes:

$$n_{revs} = \max\!\left(\left\lceil \frac{|\Delta r|}{spacing} \right\rceil,\ \left\lceil \frac{\Delta z}{h_{layer}} \right\rceil\right)$$

Onde `spacing = base_w × (1 − line_overlap)`. Isso garante que a variação radial por volta não exceda o espaçamento entre linhas, eliminando o artefato de "trança" em ombros côncavos e convexos.

## Dependências

| Pacote | Uso |
|---|---|
| `PyQt5` | Interface gráfica |
| `vtk` | Renderização 3D |
| `numpy` | Cálculos numéricos |
| `shapely` | Geometria 2D (contornos, interseções) |
| `trimesh` | Análise de malhas 3D |
| `scipy` | Rotinas auxiliares (trimesh) |
| `matplotlib` | Utilitários de visualização (opcional) |

---
*Desenvolvido para pesquisa em impressão 3D cerâmica — argila e materiais pastosos.*
