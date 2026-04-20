# SOLUCAO DEFINITIVA - ENCODING PYQT5 NO WINDOWS

================================================================================
PROBLEMA IDENTIFICADO
================================================================================

PyQt5 no Windows exibe incorretamente caracteres UTF-8 (acentos) em labels,
botoes e textos da interface quando o sistema usa codepage Windows-1252.

Nas imagens fornecidas:
  - "Compensação" aparece como "CompensaÃ§Ã£o"
  - "Sobreposição" aparece como "SobreposiÃ§Ã£o"
  - "Ângulo máx" aparece como "Ãngulo mÃ¡x"
  - Símbolo "°" aparece como "Â°"

================================================================================
CAUSA RAIZ
================================================================================

O Windows PowerShell e o PyQt5 usam codepages diferentes:
  - Arquivo Python: UTF-8 (correto)
  - PyQt5 renderizacao: Windows-1252 ou similar
  - Resultado: Caracteres multibyte UTF-8 sao interpretados como 2 chars

Exemplo:
  UTF-8: "ção" = bytes C3 A7 C3 A3 6F
  Win-1252 le como: "Ã§Ã£o"

================================================================================
SOLUCOES
================================================================================

### SOLUCAO 1: Remover Acentos dos Textos Visiveis (RECOMENDADA)

Editar manualmente integrated_clay_viewer.py e substituir:

ANTES:
```python
QGroupBox("Compensação de Overhang (modo vaso)")
QCheckBox("Ativar compensação")
QLabel("Sobreposição mínima:")
form.addRow("Ângulo máx. (°):", widget)
```

DEPOIS:
```python
QGroupBox("Compensacao de Overhang (modo vaso)")
QCheckBox("Ativar compensacao")
QLabel("Sobreposicao minima:")
form.addRow("Angulo max. (graus):", widget)
```

### SOLUCAO 2: Usar Script Automatico

Execute:
```powershell
python fix_qt_encoding.py integrated_clay_viewer.py
```

O script fix_qt_encoding.py vai:
  1. Fazer backup do arquivo original
  2. Substituir acentos em strings do PyQt5
  3. Trocar símbolo "°" por "graus"

================================================================================
STRINGS QUE PRECISAM SER CORRIGIDAS
================================================================================

Localizacao na UI (conforme imagens):

1. Aba "Simulacao do Percurso":
   Linha ~2269: QGroupBox("Simulação do Percurso")
   -> QGroupBox("Simulacao do Percurso")

2. Grupo "Compensacao de Overhang":
   Linha ~2305: QGroupBox("Compensação de Overhang (modo vaso)")
   -> QGroupBox("Compensacao de Overhang (modo vaso)")
   
   Linha ~2309: QCheckBox("Ativar compensação")
   -> QCheckBox("Ativar compensacao")
   
   Linha ~2355: addRow("Ângulo máx. (°):", ...)
   -> addRow("Angulo max. (graus):", ...)

3. Labels com "Sobreposição":
   Procurar por: QLabel.*Sobreposi
   Substituir "ção" por "cao"

4. Sufixos com grau:
   Procurar por: .setSuffix(" °")
   Substituir por: .setSuffix(" graus")

================================================================================
COMO APLICAR MANUALMENTE
================================================================================

### Metodo 1: Usando find/replace no VS Code

1. Abrir integrated_clay_viewer.py
2. Ctrl+H (Find and Replace)
3. Ativar "Match Case" e "Match Whole Word"
4. Substituir uma por vez:

   - Find: "Compensação"  Replace: "Compensacao"
   - Find: "compensação"  Replace: "compensacao"
   - Find: "Simulação"    Replace: "Simulacao"
   - Find: "simulação"    Replace: "simulacao"
   - Find: "Visualização" Replace: "Visualizacao"
   - Find: "visualização" Replace: "visualizacao"
   - Find: "Configurações" Replace: "Configuracoes"
   - Find: "configurações" Replace: "configuracoes"
   - Find: "Sobreposição" Replace: "Sobreposicao"
   - Find: "sobreposição" Replace: "sobreposicao"
   - Find: "Ângulo"       Replace: "Angulo"
   - Find: "ângulo"       Replace: "angulo"
   - Find: "máx"          Replace: "max"
   - Find: "mín"          Replace: "min"
   - Find: " °\""         Replace: " graus\""
   - Find: "Você"         Replace: "Voce"
   - Find: "não"          Replace: "nao"

### Metodo 2: Usando PowerShell

```powershell
$file = "integrated_clay_viewer.py"
$content = Get-Content $file -Raw -Encoding UTF8

# Backup
Copy-Item $file "$file.backup"

# Substituicoes
$content = $content -replace 'Compensação', 'Compensacao'
$content = $content -replace 'compensação', 'compensacao'
$content = $content -replace 'Simulação', 'Simulacao'
$content = $content -replace 'simulação', 'simulacao'
$content = $content -replace 'Visualização', 'Visualizacao'
$content = $content -replace 'visualização', 'visualizacao'
$content = $content -replace 'Sobreposição', 'Sobreposicao'
$content = $content -replace 'sobreposição', 'sobreposicao'
$content = $content -replace 'Ângulo', 'Angulo'
$content = $content -replace 'ângulo', 'angulo'
$content = $content -replace ' °"', ' graus"'
$content = $content -replace 'Você', 'Voce'
$content = $content -replace 'não', 'nao'

# Salvar
$content | Set-Content $file -Encoding UTF8
```

================================================================================
VERIFICACAO
================================================================================

Apos corrigir, execute:
```powershell
python integrated_clay_viewer.py copoOnda.obj
```

A interface deve exibir:
  - "Simulacao do Percurso" (sem Ã§Ã£)
  - "Compensacao de Overhang" (sem Ã§)
  - "Angulo max. (graus)" (sem Ã, sem Â°)
  - "Sobreposicao minima" (sem Ã§Ã£)

================================================================================
OBSERVACOES IMPORTANTES
================================================================================

1. NAO substituir acentos em:
   - Comentarios (linhas que começam com #)
   - Docstrings ("""...""")
   - Nomes de variaveis ou funcoes
   
2. APENAS substituir em:
   - Strings de QLabel, QPushButton, QGroupBox, QCheckBox
   - Strings de addRow(), setText(), setWindowTitle()
   - Mensagens de QMessageBox

3. Manter # -*- coding: utf-8 -*- no topo do arquivo

4. Testar a interface apos cada substituicao

================================================================================
ARQUIVO CORROMPIDO?
================================================================================

Se integrated_clay_viewer.py estiver incompleto ou duplicado:

1. Verificar numero de linhas:
   ```powershell
   (Get-Content "integrated_clay_viewer.py").Count
   ```
   Deve ter ~3126 linhas

2. Se estiver duplicado (>5000 linhas):
   ```powershell
   $lines = Get-Content "integrated_clay_viewer.py"
   $half = [int]($lines.Count / 2)
   $lines[0..($half-1)] | Set-Content "integrated_clay_viewer_fixed.py"
   Move-Item "integrated_clay_viewer_fixed.py" "integrated_clay_viewer.py" -Force
   ```

3. Verificar final do arquivo termina com:
   - Ultima funcao completa
   - Possivelmente: if __name__ == "__main__": main()

================================================================================
STATUS
================================================================================

- [OK] Problema identificado: PyQt5 + Windows codepage
- [OK] Causa raiz: UTF-8 interpretado como Windows-1252
- [OK] Solucao: Remover acentos de strings visiveis na UI
- [OK] Script automatico criado: fix_qt_encoding.py
- [ ] PENDENTE: Aplicar correcoes no integrated_clay_viewer.py

================================================================================
