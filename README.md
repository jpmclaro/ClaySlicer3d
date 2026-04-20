# Clay 3D Printing G-code Generator

Sistema especializado para geração e visualização de G-code contínuo (modo vaso) voltado à impressão 3D em argila.

## 🌟 Visão Geral

- 🎛️ **Interface Integrada (PyQt5 + VTK):** Carregue modelos STL/OBJ, ajuste parâmetros e visualize a simulação do percurso em 3D.
- 🏺 **Slicer Especializado:** Gera ponto central, micro-espiral na base e paredes helicoidais contínuas (Vase Mode) otimizadas para cerâmica.
- 🌊 **Modo Non-Planar (Experimental):** Gera paredes que seguem a topografia orgânica do objeto, ideal para vasos com bordas irregulares ou onduladas.
- 💧 **Extrusão Contínua:** Sem retrações, com dosagem relativa e limitação volumétrica.
- 💾 **Presets:** Sistema de perfis de impressão salvos em `printer_presets.json`.

## 📂 Estrutura do Projeto

```
C3d - Prusa/
│
├── 📜 Código-Fonte Principal
│   ├── integrated_clay_viewer.py          # Interface gráfica (Ponto de Entrada)
│   ├── clay_gcode_generator_definitive.py # Orquestrador da geração de G-code
│   ├── clay_base_layers.py                # Gerador da base (espiral + micro-espiral)
│   ├── clay_walls.py                      # Gerador de paredes Planar (Vase Mode padrão)
│   ├── clay_walls_nonplanar.py            # Gerador de paredes Non-Planar (Orgânico)
│   ├── clay_gcode_core.py                 # Utilitários de escrita de G-code
│   ├── clay_geometry.py                   # Funções geométricas (Shapely)
│   ├── clay_mesh.py                       # Análise e fatiamento de malhas
│   ├── clay_models.py                     # Estruturas de dados (Point3D, MeshAnalysis)
│   ├── clay_settings.py                   # Configurações de impressão
│   └── clay_spiral_sampling.py            # Algoritmos de amostragem de espiral
│
├── 📂 models/                             # Coloque seus arquivos .obj / .stl aqui
│
├── 📂 gcode_output/                       # G-codes gerados são salvos aqui
│
├── 📂 BCK/                                # Backups, testes antigos e arquivos legados
│
├── ⚙️ Configuração
│   ├── printer_presets.json               # Perfis de impressão salvos
│   ├── requirements.txt                   # Dependências Python
│   └── run_clay_viewer.bat                # Script de execução (Windows)
│
└── 📖 Documentação
    └── docs/                              # Documentação técnica detalhada
```

## 🚀 Como Executar

### Pré-requisitos
- Python 3.10+
- Dependências: `PyQt5`, `vtk`, `numpy`, `shapely`

### Instalação
```bash
python -m venv .venv
.\.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

### Executando
**Via script (Windows):**
```cmd
run_clay_viewer.bat
```

**Manualmente:**
```bash
python integrated_clay_viewer.py
```

1. Clique em **"Carregar STL/OBJ"** (use arquivos da pasta `models/`).
2. Escolha um **Preset** ou ajuste os parâmetros manualmente.
3. Clique em **"Gerar Simulação"** para ver o percurso.
4. Clique em **"Salvar G-code"** para exportar.

## 🌊 Modo Non-Planar

O modo Non-Planar permite imprimir objetos com topos irregulares ou curvos sem o efeito de "degraus" do fatiamento tradicional.

**Como ativar:**
1. No visualizador, vá na aba **"Avançado"**.
2. Marque **"Ativar modo Non-Planar"**.
3. Gere a simulação.

**Ideal para:** Vasos com bordas onduladas, esculturas orgânicas.
**Não recomendado para:** Cilindros retos ou peças mecânicas simples.

## 🛠️ Detalhes Técnicos

| Módulo | Função |
| --- | --- |
| `clay_walls_nonplanar.py` | Implementa "Warping Virtual" para endireitar objetos curvos, fatia, e depois aplica "Unwarping" para gerar o G-code curvo. |
| `clay_base_layers.py` | Gera uma base sólida com micro-espirais no centro para evitar buracos comuns em impressão de argila. |
| `clay_gcode_generator_definitive.py` | Decide qual estratégia usar (Planar vs Non-Planar) e coordena o processo. |

---
*Projeto mantido para pesquisa em impressão 3D cerâmica.*
