@echo off
REM Script de inicialização rápida do Clay 3D Printing G-code Generator
echo ================================
echo  Clay 3D Printing G-code Generator
echo  Sistema Otimizado com Ray Casting
echo ================================
echo.
echo Ativando ambiente virtual...
call .venv\Scripts\activate.bat
echo.
echo Iniciando interface...
python integrated_clay_viewer.py
echo.