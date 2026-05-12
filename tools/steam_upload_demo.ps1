param(
    [Parameter(Mandatory = $true)]
    [string]$SteamCmdPath,

    [Parameter(Mandatory = $true)]
    [string]$SteamUser,

    [string]$SteamPassword = "",

    [string]$AppBuildScript = "",

    [string]$BuildDescription = "",

    [string]$ContentRoot = "",

    [string]$BuildOutput = "",

    [string]$SetLive = ""
)

$helperPath = Join-Path $PSScriptRoot 'steam_upload_playtest.ps1'
if (-not (Test-Path $helperPath)) {
    throw "Demo upload helper bulunamadi: $helperPath"
}

$resolvedAppBuildScript = if ([string]::IsNullOrWhiteSpace($AppBuildScript)) {
    Join-Path (Split-Path -Parent $PSScriptRoot) 'steamworks\scripts\app_build_demo.vdf'
}
else {
    $AppBuildScript
}

$invokeParams = @{
    SteamCmdPath    = $SteamCmdPath
    SteamUser       = $SteamUser
    SteamPassword   = $SteamPassword
    Target          = 'demo'
    AppBuildScript  = $resolvedAppBuildScript
    BuildDescription = $BuildDescription
    ContentRoot     = $ContentRoot
    BuildOutput     = $BuildOutput
    SetLive         = $SetLive
}

& $helperPath @invokeParams

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}