param(
    [Parameter(Mandatory = $true)]
    [string]$SteamCmdPath,

    [Parameter(Mandatory = $true)]
    [string]$SteamUser,

    [string]$SteamPassword = "",

    [string]$AppBuildScript = ".\\steamworks\\scripts\\app_build_playtest.vdf"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SteamCmdPath)) {
    throw "steamcmd bulunamadı: $SteamCmdPath"
}

if (-not (Test-Path $AppBuildScript)) {
    throw "App build script bulunamadı: $AppBuildScript"
}

Write-Host "Steam Playtest upload başlatılıyor..." -ForegroundColor Cyan
Write-Host "SteamCmd: $SteamCmdPath"
Write-Host "Script  : $AppBuildScript"
Write-Host "User    : $SteamUser"

$resolvedScript = (Resolve-Path $AppBuildScript).Path

if ([string]::IsNullOrWhiteSpace($SteamPassword)) {
    & $SteamCmdPath +login $SteamUser +run_app_build "$resolvedScript" +quit
} else {
    & $SteamCmdPath +login $SteamUser $SteamPassword +run_app_build "$resolvedScript" +quit
}

if ($LASTEXITCODE -ne 0) {
    throw "Steam upload başarısız oldu. ExitCode=$LASTEXITCODE"
}

Write-Host "Steam Playtest upload tamamlandı." -ForegroundColor Green
