param(
    [Parameter(Mandatory = $true)]
    [string]$SteamCmdPath,

    [Parameter(Mandatory = $true)]
    [string]$SteamUser,

    [string]$SteamPassword = "",

    [ValidateSet("playtest", "main")]
    [string]$Target = "playtest",

    [string]$AppBuildScript = "",

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

function New-DepotBuildVdf {
    param(
        [string]$DepotId,
        [string[]]$FileExclusions
    )

    $lines = @(
        '"DepotBuild"',
        '{',
        "    \"DepotID\" \"$DepotId\"",
        '',
        '    "FileMapping"',
        '    {',
        '        "LocalPath" "*"',
        '        "DepotPath" "."',
        '        "Recursive" "1"',
        '    }',
        ''
    )

    foreach ($exclusion in $FileExclusions) {
        $safeExclusion = $exclusion.Replace('"', '')
        $lines += "    \"FileExclusion\" \"$safeExclusion\""
    }

    $lines += '}'
    return ($lines -join [Environment]::NewLine)
}

function New-AppBuildVdf {
    param(
        [string]$AppId,
        [string]$DepotId,
        [string]$DepotFileName,
        [string]$Description,
        [string]$SetLiveValue,
        [string]$ContentRootValue,
        [string]$BuildOutputValue
    )

    $safeDescription = $Description.Replace('"', '')
    $safeSetLive = $SetLiveValue.Replace('"', '')
    $safeContentRoot = $ContentRootValue.Replace('"', '')
    $safeBuildOutput = $BuildOutputValue.Replace('"', '')

    return @"
"AppBuild"
{
    "AppID" "$AppId"
    "Desc" "$safeDescription"
    "SetLive" "$safeSetLive"
    "ContentRoot" "$safeContentRoot"
    "BuildOutput" "$safeBuildOutput"

    "Depots"
    {
        "$DepotId" "$DepotFileName"
    }
}
"@
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path $SteamCmdPath)) {
    throw "steamcmd bulunamadı: $SteamCmdPath"
}

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
    if ($Target -eq 'main') {
        "Main app build $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    }
    else {
        "Playtest build $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    }
} else {
    $BuildDescription
}

$targetConfig = switch ($Target) {
    'main' {
        @{
            AppId = '4414520'
            DepotId = '4414521'
            FileExclusions = @('*.pdb', '*.log', 'steam_appid.txt', '*.spec')
        }
    }
    default {
        @{
            AppId = '4428040'
            DepotId = '4428041'
            FileExclusions = @('*.pdb', '*.log')
        }
    }
}

$tempScript = $null
$tempDepotScript = $null

if ([string]::IsNullOrWhiteSpace($AppBuildScript)) {
    $scriptsDir = Join-Path $repoRoot 'steamworks\scripts'
    $guid = [guid]::NewGuid().ToString('N')
    $tempDepotScript = Join-Path $scriptsDir (".tmp_depot_build_{0}.vdf" -f $guid)
    $tempScript = Join-Path $scriptsDir (".tmp_app_build_{0}.vdf" -f $guid)
    $tempDepotName = Split-Path -Leaf $tempDepotScript

    $depotContent = New-DepotBuildVdf -DepotId $targetConfig.DepotId -FileExclusions $targetConfig.FileExclusions
    $appBuildContent = New-AppBuildVdf \
        -AppId $targetConfig.AppId \
        -DepotId $targetConfig.DepotId \
        -DepotFileName $tempDepotName \
        -Description $effectiveDesc \
        -SetLiveValue $SetLive \
        -ContentRootValue $resolvedContentRoot \
        -BuildOutputValue $resolvedBuildOutput

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempDepotScript, $depotContent, $utf8NoBom)
    [System.IO.File]::WriteAllText($tempScript, $appBuildContent, $utf8NoBom)
    $resolvedScript = $tempScript
}
else {
    if (-not (Test-Path $AppBuildScript)) {
        throw "App build script bulunamadı: $AppBuildScript"
    }

    $resolvedScript = (Resolve-Path $AppBuildScript).Path
}

Write-Host "Steam upload başlatılıyor..." -ForegroundColor Cyan
Write-Host "SteamCmd: $SteamCmdPath"
Write-Host "Target  : $Target"
Write-Host "Script  : $resolvedScript"
Write-Host "User    : $SteamUser"
Write-Host "Desc    : $effectiveDesc"
Write-Host "SetLive : '$SetLive'"
Write-Host "Root    : $resolvedContentRoot"
Write-Host "Output  : $resolvedBuildOutput"

if (-not [string]::IsNullOrWhiteSpace($AppBuildScript)) {
    $vdfContent = Get-Content -LiteralPath $resolvedScript -Raw
    $vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "Desc" -FieldValue $effectiveDesc
    $vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "SetLive" -FieldValue $SetLive
    $vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "ContentRoot" -FieldValue $resolvedContentRoot
    $vdfContent = Set-VdfField -VdfText $vdfContent -FieldName "BuildOutput" -FieldValue $resolvedBuildOutput

    $tempScript = Join-Path (Split-Path -Parent $resolvedScript) (".tmp_app_build_{0}.vdf" -f [guid]::NewGuid().ToString("N"))
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempScript, $vdfContent, $utf8NoBom)
    $resolvedScript = $tempScript
}

try {
    if ([string]::IsNullOrWhiteSpace($SteamPassword)) {
        & $SteamCmdPath +login $SteamUser +run_app_build "$resolvedScript" +quit
    } else {
        & $SteamCmdPath +login $SteamUser $SteamPassword +run_app_build "$resolvedScript" +quit
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Steam upload başarısız oldu. ExitCode=$LASTEXITCODE"
    }
}
finally {
    if (Test-Path $tempScript) {
        Remove-Item $tempScript -Force
    }
    if ($tempDepotScript -and (Test-Path $tempDepotScript)) {
        Remove-Item $tempDepotScript -Force
    }
}

Write-Host "Steam upload tamamlandı." -ForegroundColor Green
