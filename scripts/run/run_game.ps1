#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quadrix Windows PowerShell Launcher
.DESCRIPTION
    Bu script oyunu Windows'ta PowerShell ile başlatır.
    Kullanım: Sağ tık -> PowerShell ile Çalıştır
              veya terminalde: .\run_game.ps1
.NOTES
    Python 3.10+ gereklidir.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Script dizinine git
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $scriptDir) { $scriptDir = Get-Location }
Set-Location $scriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    QUADRIX - Full Edition (PowerShell)" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Python bul
$pythonCmd = $null

# 1. Python Launcher (py)
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
    $pythonArgs = @("-3")
}
# 2. python3
elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
    $pythonArgs = @()
}
# 3. python
elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
    $pythonArgs = @()
}
else {
    Write-Host "[HATA] Python bulunamadi!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Python'u python.org adresinden indirip kurun." -ForegroundColor Yellow
    Write-Host "Kurulum sirasinda 'Add Python to PATH' secenegini isaretleyin." -ForegroundColor Yellow
    Read-Host "Devam etmek icin Enter'a basin"
    exit 1
}

Write-Host "[OK] Python: $pythonCmd $pythonArgs" -ForegroundColor Green

# main.py'yi bul (root veya src)
$mainPy = $null
if (Test-Path "main.py") {
    $mainPy = "main.py"
} elseif (Test-Path "src\main.py") {
    $mainPy = "src\main.py"
} else {
    Write-Host "[HATA] main.py bulunamadi!" -ForegroundColor Red
    Read-Host "Devam etmek icin Enter'a basin"
    exit 1
}

# Gerekli paketleri kontrol et
Write-Host "[INFO] Paketler kontrol ediliyor..." -ForegroundColor Yellow
$checkCmd = "$pythonCmd $pythonArgs -c `"import pygame, numpy`""
try {
    Invoke-Expression $checkCmd 2>$null
} catch {
    Write-Host "[INFO] Gerekli paketler yukleniyor..." -ForegroundColor Yellow
    & $pythonCmd @pythonArgs -m pip install -r requirements.txt --quiet
    Write-Host "[OK] Paketler yuklendi." -ForegroundColor Green
}

Write-Host ""
Write-Host "Oyun baslatiliyor..." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Oyunu başlat
try {
    & $pythonCmd @pythonArgs $mainPy @Args
} catch {
    Write-Host ""
    Write-Host "[HATA] Oyun beklenmedik sekilde kapandi: $_" -ForegroundColor Red
    Read-Host "Devam etmek icin Enter'a basin"
    exit 1
}
