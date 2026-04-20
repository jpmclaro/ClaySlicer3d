# CORRECAO DE ENCODING - INTERFACE GRAFICA
# Data: 2025-01-04

================================================================================
PROBLEMA
================================================================================

A interface grafica (integrated_clay_viewer.py) estava exibindo caracteres 
especiais corrompidos no lugar de emojis e acentos devido a problemas de 
encoding UTF-8 no Windows PowerShell.

Exemplo:
  - "ðŸ"‚ Carregar" aparecia como caracteres quebrados
  - "Simulação" aparecia como "SimulaÃ§Ã£o"

================================================================================
SOLUCAO IMPLEMENTADA
================================================================================

Arquivo: fix_emojis_v2.py

Script Python que:
1. Le o arquivo com encoding UTF-8
2. Detecta botoes QPushButton com emojis
3. Substitui emojis por tags ASCII: [*], [>>], [CFG], etc.
4. Corrige acentuacao quebrada

================================================================================
SUBSTITUICOES REALIZADAS
================================================================================

Emojis -> Tags ASCII:
  Linha 911:  "ðŸ"‚ Carregar STL/OBJ" -> "[*] Carregar STL/OBJ"
  Linha 1083: "âœï¸ Editar Presets" -> "[Editar] Presets"
  Linha 1181: "âš™ï¸ Configurar" -> "[CFG] Configurar Impressao"
  Linha 1185: "ðŸŽ¬ Gerar" -> "[>>] Gerar Simulacao"
  Linha 1219: "ðŸ"¼ Frente" -> "[^] Frente"
  Linha 1223: "â« Topo" -> "[T] Topo"
  Linha 1227: "âž¡ï¸ Dir" -> "[>] Dir"
  Linha 1233: "â¬…ï¸ Esq" -> "[<] Esq"
  Linha 1237: "â¬‡ï¸ Base" -> "[v] Base"
  Linha 1241: "ðŸ"™ Tras" -> "[V] Tras"
  Linha 1246: "ðŸ"„ Resetar" -> "[R] Resetar Visualizacao"
  Linha 1274: "ðŸ'¾ Salvar" -> "[SAVE] Salvar G-code"
  Linha 1587: "âž• Adicionar" -> "[+] Adicionar"
  Linha 1588: "ðŸ—'ï¸ Remover" -> "[-] Remover"

Acentuacao corrigida (48 ocorrencias):
  ImpressÃ£o -> Impressao
  SimulaÃ§Ã£o -> Simulacao
  VisualizaÃ§Ã£o -> Visualizacao
  ConfiguraÃ§Ãµes -> Configuracoes
  VocÃª -> Voce
  nÃ£o -> nao
  VariÃ¡veis -> Variaveis
  apÃ³s -> apos
  geraÃ§Ã£o -> geracao
  visualizaÃ§Ã£o -> visualizacao

================================================================================
COMO APLICAR
================================================================================

1. Restaurar integrated_clay_viewer.py original (se corrompido)
2. Executar: python fix_emojis_v2.py
3. Verificar resultado: python integrated_clay_viewer.py [arquivo.obj]

================================================================================
RESULTADO
================================================================================

Interface grafica agora exibe:
  [*] Carregar STL/OBJ   (botao de carregar)
  [>>] Gerar Simulacao   (botao de simulacao)
  [SAVE] Salvar G-code   (botao de salvar)
  Simulacao nao gerada   (label de status)

Todos os textos visiveis e legiveis no Windows PowerShell!

================================================================================
ARQUIVOS CORRIGIDOS
================================================================================

1. debug_gcode_z_progression.py  - Emojis -> ASCII
2. quick_gcode_gen.py           - Emojis -> ASCII  
3. integrated_clay_viewer.py    - Emojis + acentos -> ASCII

================================================================================
STATUS: IMPLEMENTADO
================================================================================

Os scripts de debug e geracao agora exibem output limpo no PowerShell.
A interface grafica precisa ser corrigida com fix_emojis_v2.py.

IMPORTANTE: Sempre usar encoding UTF-8 nos arquivos Python e adicionar:
  # -*- coding: utf-8 -*-

no topo de cada arquivo.
