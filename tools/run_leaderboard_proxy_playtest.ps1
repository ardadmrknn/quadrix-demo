param(
    [string]$ApiKey = "",
    [string]$BindHost = "127.0.0.1",
    [int]$BindPort = 8787,
    [string]$ClientToken = "",
    [string]$TokenSecret = ""
)

$ErrorActionPreference = "Stop"

function Read-IfEmpty {
    param(
        [string]$Current,
        [string]$Prompt
    )
    if ([string]::IsNullOrWhiteSpace($Current)) {
        return (Read-Host $Prompt)
    }
    return $Current
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

$ApiKey = Read-IfEmpty -Current $ApiKey -Prompt "STEAM_WEB_API_KEY (Publisher Key)"
$ApiKey = $ApiKey.Trim().Trim('"').Trim("'").TrimEnd(',',';').Trim()
if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Host "[HATA] STEAM_WEB_API_KEY boş olamaz." -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($TokenSecret)) {
    $TokenSecret = [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
}

$env:STEAM_APP_ID = "4428040"
$env:STEAM_WEB_API_KEY = $ApiKey
$env:LEADERBOARD_BIND_HOST = $BindHost
$env:LEADERBOARD_BIND_PORT = "$BindPort"
$env:LEADERBOARD_TOKEN_SECRET = $TokenSecret

if (-not [string]::IsNullOrWhiteSpace($ClientToken)) {
    $env:LEADERBOARD_CLIENT_TOKEN = $ClientToken
}

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Quadrix Playtest Leaderboard Proxy" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "AppID  : $env:STEAM_APP_ID"
Write-Host "Host   : $env:LEADERBOARD_BIND_HOST"
Write-Host "Port   : $env:LEADERBOARD_BIND_PORT"
Write-Host ""
Write-Host "Backend başlatılıyor... (Kapatmak için Ctrl+C)" -ForegroundColor Yellow

py backend/steam_leaderboard_proxy.py
