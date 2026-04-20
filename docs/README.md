# 📚 Documentação Técnica

Esta pasta contém toda a documentação técnica do projeto.

## 📁 Categorias

### 🏗️ Arquitetura
- **`ARQUITETURA_FINAL_TAPER.md`** - Arquitetura do sistema de taper (afunilamento)

### ⚙️ Controles
- **`CONTROLE_ACELERACAO.md`** - Sistema de controle de aceleração

### 🔧 Correções Implementadas

| Arquivo | Descrição |
|---------|-----------|
| `CORRECAO_ALTURA_TAPER.md` | Correção da altura no taper |
| `CORRECAO_CARREGAMENTO_PRESET.md` | Correção do carregamento de presets na UI |
| `CORRECAO_ENCODING_PYQT5.md` | Correção de encoding PyQt5 |
| `CORRECAO_EXTRUSION_LARGURA_CAMADAS.md` | Correção de largura de extrusão por camada |
| `CORRECAO_LARGURA_EXTRUSION_CAMADAS.md` | Correção adicional de largura |
| `CORRECAO_PONTO_CENTRAL_VELOCIDADE_FLUXO.md` | Correção de velocidade do ponto central |
| `CORRECAO_SALVAMENTO_OTHER_WIDTH.md` | Correção do salvamento de "Largura demais camadas" |
| `CORRECAO_TAPER_ESPIRAL.md` | Correção do taper em espiral |
| `CORRECAO_TRANSICAO_BASE_PAREDE.md` | Correção da transição base→parede |
| `CORRECAO_TRAVAMENTO_TAPER.md` | Correção de travamento no taper |

### 💡 Soluções

| Arquivo | Descrição |
|---------|-----------|
| `SOLUCAO_ENCODING_UI.md` | Solução de encoding na interface |
| `SOLUCAO_FINAL_TAPER_NOVOS_PONTOS.md` | Solução final para taper com novos pontos |
| `SOLUCAO_FINAL_TRANSICAO_ESTRUTURAL.md` | Solução estrutural de transição |
| `SOLUCAO_RAMPA_HELICOIDAL.md` | Solução de rampa helicoidal |
| `SOLUCAO_TAPER_Z_FIXO.md` | Solução de Z fixo no taper |
| `SOLUCAO_VISUALIZACAO_TAPER.md` | Solução de visualização do taper |

### 📖 Explicações

| Arquivo | Descrição |
|---------|-----------|
| `EXPLICACAO_Z_INICIAL_PAREDE.md` | Explicação do Z inicial da parede |

### 📊 Resumos

| Arquivo | Descrição |
|---------|-----------|
| `RESUMO_COMPLETO_TAPER.md` | Resumo completo do sistema de taper |
| `RESUMO_CORRECAO_TAPER.md` | Resumo das correções de taper |
| `RESUMO_SKIRT_MICRO_SPIRAL.md` | Resumo de saia e micro-espiral |

### 📈 Status

| Arquivo | Descrição |
|---------|-----------|
| `STATUS_TAPER_FINAL.md` | Status final da implementação de taper |

## 🔍 Como Usar

### Buscar por Problema

1. **Problema com altura:**
   - `CORRECAO_ALTURA_TAPER.md`
   - `EXPLICACAO_Z_INICIAL_PAREDE.md`

2. **Problema com largura de extrusão:**
   - `CORRECAO_EXTRUSION_LARGURA_CAMADAS.md`
   - `CORRECAO_LARGURA_EXTRUSION_CAMADAS.md`

3. **Problema com taper (afunilamento):**
   - `RESUMO_COMPLETO_TAPER.md` (começar aqui)
   - `ARQUITETURA_FINAL_TAPER.md`
   - `STATUS_TAPER_FINAL.md`

4. **Problema com UI/presets:**
   - `CORRECAO_CARREGAMENTO_PRESET.md`
   - `CORRECAO_SALVAMENTO_OTHER_WIDTH.md`

5. **Problema com transições:**
   - `CORRECAO_TRANSICAO_BASE_PAREDE.md`
   - `SOLUCAO_FINAL_TRANSICAO_ESTRUTURAL.md`

## 📝 Estrutura dos Documentos

Cada documento segue este padrão:

```markdown
# Título da Correção/Solução

## 🐛 Problema Identificado
Descrição do problema...

## 🔍 Causa Raiz
Análise da causa...

## ✅ Solução Implementada
Código e explicação...

## 🧪 Validação
Testes realizados...

## 📁 Arquivos Modificados
Lista de arquivos...
```

## 🎯 Principais Conceitos

### Taper (Afunilamento)
Redução progressiva da largura de extrusão ao longo da altura:
- **Início:** Largura maior (ex: 8.0mm)
- **Fim:** Largura menor (ex: 2.5mm)
- **Uso:** Vasos, formas cônicas

### Ponto Central
Deposição inicial no centro da base:
- Melhora aderência
- Prepara superfície
- Opcional (pode ser desabilitado)

### Micro Espiral
Pequena espiral no ponto central:
- Distribui material uniformemente
- Suaviza transição para paredes
- Controlável via preset

### Cobertura de Altura
Sistema que garante impressão até o topo:
- Detecta altura do objeto
- Extrapola se necessário
- Funciona com geometrias difíceis

## 🔧 Arquivos de Código Relacionados

| Documento | Código Relacionado |
|-----------|-------------------|
| Documentos de taper | `clay_gcode_generator_definitive.py` |
| Documentos de altura | `clay_walls.py` |
| Documentos de base | `clay_base_layers.py` |
| Documentos de UI | `integrated_clay_viewer.py` |
| Documentos de largura | `clay_gcode_core.py` |

## 📚 Ordem de Leitura Recomendada

### Para Novos Desenvolvedores:

1. **Visão Geral:**
   - `../PROJETO_README.md`
   - `../INDEX.md`

2. **Arquitetura:**
   - `ARQUITETURA_FINAL_TAPER.md`
   - `RESUMO_COMPLETO_TAPER.md`

3. **Funcionalidades Principais:**
   - `RESUMO_SKIRT_MICRO_SPIRAL.md`
   - `EXPLICACAO_Z_INICIAL_PAREDE.md`

4. **Correções Recentes:**
   - `CORRECAO_CARREGAMENTO_PRESET.md`
   - `CORRECAO_SALVAMENTO_OTHER_WIDTH.md`

### Para Debugging:

1. **Identifique o módulo** com problema
2. **Busque por `CORRECAO_`** relacionado
3. **Leia `RESUMO_`** para contexto
4. **Consulte `SOLUCAO_`** para detalhes técnicos

## 🕒 Histórico

- **04/10/2025:** Organização da documentação em pasta dedicada
- **04/10/2025:** Correção de carregamento de presets
- **04/10/2025:** Correção de salvamento de largura
- **Versões anteriores:** Consultar git log

## 📞 Contato

Para dúvidas sobre a documentação:
1. Leia o documento relevante
2. Consulte o código-fonte relacionado
3. Verifique testes em `../BCK/test_*.py`

---

**Pasta:** `docs/`
**Total de documentos:** 23
**Última atualização:** 04/10/2025
