@echo off
REM Quadrix Windows Başlatıcı
REM Bu script oyunu Windows'ta hızlıca başlatır

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo     QUADRIX - Full Edition (Windows)
echo ============================================
echo.

REM Python bul - öncelik sırası: py launcher, python3, python
set "PYTHON_EXE="

REM 1. Python Launcher (py) - en güvenilir
where py >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3"
    goto :found_python
)

REM 2. python3 komutu
where python3 >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python3"
    goto :found_python
)

REM 3. python komutu
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    goto :found_python
)

REM Python bulunamadı
echo [HATA] Python bulunamadi!
echo.
echo Python'u python.org adresinden indirip kurun.
echo Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin.
pause
exit /b 1

:found_python
echo [OK] Python: %PYTHON_EXE%

REM Gerekli paketleri kontrol et
%PYTHON_EXE% -c "import pygame, numpy" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] Gerekli paketler yukleniyor...
    %PYTHON_EXE% -m pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo [HATA] Paket yukleme basarisiz!
        pause
        exit /b 1
    )
    echo [OK] Paketler yuklendi.
)

echo.
echo Oyun baslatiliyor...
echo ============================================
echo.

REM Oyunu başlat
%PYTHON_EXE% main.py %*

REM Hata varsa bekle
if !errorlevel! neq 0 (
    echo.
    echo [HATA] Oyun beklenmedik sekilde kapandi.
    pause
)
