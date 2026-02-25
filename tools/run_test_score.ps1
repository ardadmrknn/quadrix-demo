param(
    [string]$AppId = "",
    [string]$ApiKey = "",
    [string]$SteamId = "76561199351154071",
    [int]$Score = 12345,
    [string]$Mode = "mystery",
    [ValidateSet("KeepBest", "ForceUpdate")]
    [string]$ScoreMethod = "KeepBest"
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

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Quadrix Steam Test Score Runner" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

$AppId = Read-IfEmpty -Current $AppId -Prompt "STEAM_APP_ID"
$ApiKey = Read-IfEmpty -Current $ApiKey -Prompt "STEAM_WEB_API_KEY"
$SteamId = Read-IfEmpty -Current $SteamId -Prompt "SteamID64"

$ApiKey = $ApiKey.Trim().Trim('"').Trim("'").TrimEnd(',',';').Trim()

if ([string]::IsNullOrWhiteSpace($AppId)) {
    Write-Host "[HATA] STEAM_APP_ID boş olamaz." -ForegroundColor Red
    exit 1
}
if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Host "[HATA] STEAM_WEB_API_KEY boş olamaz." -ForegroundColor Red
    exit 1
}
if ([string]::IsNullOrWhiteSpace($SteamId)) {
    Write-Host "[HATA] SteamID64 boş olamaz." -ForegroundColor Red
    exit 1
}

$env:STEAM_APP_ID = $AppId
$env:STEAM_WEB_API_KEY = $ApiKey

$cmd = @(
    ".\\tools\\steam_set_test_score.py",
    "--mode", $Mode,
    "--steamid", $SteamId,
    "--score", "$Score",
    "--scoremethod", $ScoreMethod
)

Write-Host "[INFO] Komut çalıştırılıyor:" -ForegroundColor Yellow
Write-Host "py $($cmd -join ' ')" -ForegroundColor DarkYellow

py @cmd
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host "[OK] Test skor akışı tamamlandı." -ForegroundColor Green
} else {
    Write-Host "[HATA] Komut hata kodu ile çıktı: $code" -ForegroundColor Red
}

Write-Host ""
Read-Host "Kapatmak için Enter'a bas"
exit $code
