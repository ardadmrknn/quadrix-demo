param(
    [Parameter(Mandatory = $true)]
    [string]$SteamCmdPath,

    [Parameter(Mandatory = $true)]
    [string]$SteamUser,

    [string]$SteamPassword = "",

    [string]$AppBuildScript = ".\\steamworks\\scripts\\app_build_playtest.vdf",

    [string]$BuildDescription = "",

    [string]$ContentRoot = "",

    [string]$BuildOutput = "",

    [string]$SetLive = ""
)

$ErrorActionPreference = "Stop"

function Add-TrailingSlash {
    param([string]$PathValue)
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $PathValue
    }
    if ($PathValue.EndsWith("\\") -or $PathValue.EndsWith("/")) {
        return $PathValue
    }
    return "$PathValue\\"
}

function Set-VdfField {
    param(
        [string]$VdfText,
        [string]$FieldName,
        [string]$FieldValue
    )

    $safeValue = $FieldValue.Replace('"', '')
    $pattern = '(?m)("' + [regex]::Escape($FieldName) + '"\s*")([^"]*)(")'
    if (-not [regex]::IsMatch($VdfText, $pattern)) {
        throw "VDF alanı bulunamadı: $FieldName"
    }

    return [regex]::Replace(
        $VdfText,
        $pattern,
        [System.Text.RegularExpressions.MatchEvaluator]{
            param($match)
            return $match.Groups[1].Value + $safeValue + $match.Groups[3].Value
        },
        1
    )
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path $SteamCmdPath)) {
    throw "steamcmd bulunamadı: $SteamCmdPath"
}

if (-not (Test-Path $AppBuildScript)) {
    throw "App build script bulunamadı: $AppBuildScript"
}

$resolvedScript = (Resolve-Path $AppBuildScript).Path

$resolvedContentRootInput = if ([string]::IsNullOrWhiteSpace($ContentRoot)) {
    Join-Path $repoRoot "dist"
} else {
    $ContentRoot
}

if (-not (Test-Path $resolvedContentRootInput)) {
    throw "ContentRoot bulunamadı: $resolvedContentRootInput"
}
$resolvedContentRoot = Add-TrailingSlash((Resolve-Path $resolvedContentRootInput).Path)

$resolvedBuildOutputInput = if ([string]::IsNullOrWhiteSpace($BuildOutput)) {
    Join-Path $repoRoot "steamworks\\output"
} else {
    $BuildOutput
}
if (-not (Test-Path $resolvedBuildOutputInput)) {
    New-Item -ItemType Directory -Path $resolvedBuildOutputInput -Force | Out-Null
}
$resolvedBuildOutput = Add-TrailingSlash((Resolve-Path $resolvedBuildOutputInput).Path)

$effectiveDesc = if ([string]::IsNullOrWhiteSpace($BuildDescription)) {
    "Playtest build $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
} else {
    $BuildDescription
}

Write-Host "Steam Playtest upload başlatılıyor..." -ForegroundColor Cyan
Write-Host "SteamCmd: $SteamCmdPath"
Write-Host "Script  : $resolvedScript"
Write-Host "User    : $SteamUser"
Write-Host "Desc    : $effectiveDesc"
Write-Host "SetLive : '$SetLive'"
Write-Host "Root    : $resolvedContentRoot"
Write-Host "Output  : $resolvedBuildOutput"

$vdfContent = Get-Content -LiteralPath $resolvedScript -Raw
$vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "Desc" -FieldValue $effectiveDesc
$vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "SetLive" -FieldValue $SetLive
$vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "ContentRoot" -FieldValue $resolvedContentRoot
$vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "BuildOutput" -FieldValue $resolvedBuildOutput

$tempScript = Join-Path (Split-Path -Parent $resolvedScript) (".tmp_app_build_{0}.vdf" -f [guid]::NewGuid().ToString("N"))
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempScript, $vdfContent, $utf8NoBom)

try {
    if ([string]::IsNullOrWhiteSpace($SteamPassword)) {
        & $SteamCmdPath +login $SteamUser +run_app_build "$tempScript" +quit
    } else {
        & $SteamCmdPath +login $SteamUser $SteamPassword +run_app_build "$tempScript" +quit
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Steam upload başarısız oldu. ExitCode=$LASTEXITCODE"
    }
}
finally {
    if (Test-Path $tempScript) {
        Remove-Item $tempScript -Force
    }
}

Write-Host "Steam Playtest upload tamamlandı." -ForegroundColor Green
