param(
    [switch]$Clean,
    [switch]$RebuildBridge,
    [string]$SpecFile = 'packaging/specs/tetris.spec'
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
Set-Location $repoRoot

function Resolve-SpecPath([string]$specFile) {
    if ([string]::IsNullOrWhiteSpace($specFile)) {
        return Join-Path $repoRoot 'packaging\specs\tetris.spec'
    }
    if ([System.IO.Path]::IsPathRooted($specFile)) {
        return $specFile
    }
    if (Test-Path $specFile) {
        return (Resolve-Path $specFile).Path
    }
    $packagedSpec = Join-Path $repoRoot (Join-Path 'packaging\specs' $specFile)
    if (Test-Path $packagedSpec) {
        return (Resolve-Path $packagedSpec).Path
    }
    return (Join-Path $repoRoot $specFile)
}
function Resolve-QuadrixPython {
    if ($env:QUADRIX_PYTHON -and (Test-Path $env:QUADRIX_PYTHON)) {
        return $env:QUADRIX_PYTHON
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $resolved = & py -3.12 -c "import sys; print(sys.executable)"
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                return $resolved.Trim()
            }
        }
        catch {
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw 'Python bulunamadi. QUADRIX_PYTHON ayarlayin veya Python 3.12 kurun.'
}

function Get-BridgeArtifactPaths {
    $patterns = @(
        (Join-Path $repoRoot 'local_artifacts\bridge\steam_net_bridge*.pyd'),
        (Join-Path $repoRoot 'local_artifacts\bridge\steam_net_bridge*.so'),
        (Join-Path $repoRoot 'steam_net_bridge*.pyd'),
        (Join-Path $repoRoot 'steam_net_bridge*.so'),
        (Join-Path $repoRoot 'steamworks\steam_net_bridge\build*\Release\steam_net_bridge*.pyd'),
        (Join-Path $repoRoot 'steamworks\steam_net_bridge\build*\Release\steam_net_bridge*.so')
    )

    $items = @()
    foreach ($pattern in $patterns) {
        $items += Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
    }

    return @($items | Sort-Object FullName -Unique)
}

function Sync-BridgeArtifactsToRuntimeDir {
    $targetDir = Join-Path $repoRoot 'local_artifacts\bridge'
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $copied = @()
    foreach ($artifact in Get-BridgeArtifactPaths) {
        if ($artifact.DirectoryName -eq $targetDir) {
            continue
        }
        Copy-Item -Path $artifact.FullName -Destination (Join-Path $targetDir $artifact.Name) -Force
        $copied += $artifact.FullName
    }

    return $copied
}

$pythonExe = Resolve-QuadrixPython
$resolvedSpecFile = Resolve-SpecPath $SpecFile
$logDir = Join-Path $repoRoot 'reports\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$buildLog = Join-Path $logDir 'build_stdout.log'
$buildErrLog = Join-Path $logDir 'build_stderr.log'

Write-Host '==============================================' -ForegroundColor Cyan
Write-Host '  Quadrix Windows Clean Build' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host "Python: $pythonExe" -ForegroundColor Green
Write-Host "Spec: $resolvedSpecFile" -ForegroundColor Green

if ($Clean) {
    Write-Host 'Temiz build klasorleri siliniyor...' -ForegroundColor Yellow
    $pathsToRemove = @(
        (Join-Path $repoRoot 'build'),
        (Join-Path $repoRoot 'dist'),
        (Join-Path $repoRoot 'steamworks\steam_net_bridge\build_py312'),
        (Join-Path $repoRoot 'steamworks\steam_net_bridge\build_py313')
    )
    foreach ($path in $pathsToRemove) {
        if (Test-Path $path) {
            Remove-Item $path -Recurse -Force
        }
    }
}

if ($RebuildBridge) {
    Write-Host 'Eski bridge artifactleri temizleniyor...' -ForegroundColor Yellow
    Get-ChildItem -Path (Join-Path $repoRoot 'local_artifacts\bridge') -Filter 'steam_net_bridge*.pyd' -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path (Join-Path $repoRoot 'local_artifacts\bridge') -Filter 'steam_net_bridge*.so' -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path (Join-Path $repoRoot 'steam_net_bridge*.pyd') -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path (Join-Path $repoRoot 'steam_net_bridge*.so') -ErrorAction SilentlyContinue | Remove-Item -Force
}

$bridgeExists = @(Get-BridgeArtifactPaths).Count -gt 0
if ($RebuildBridge -or -not $bridgeExists) {
    Write-Host 'Steam bridge derleniyor...' -ForegroundColor Cyan
    $bridgeBat = Join-Path $repoRoot 'steamworks\steam_net_bridge\build.bat'
    if (-not (Test-Path $bridgeBat)) {
        throw 'steamworks\steam_net_bridge\build.bat bulunamadi.'
    }
    Push-Location (Split-Path -Parent $bridgeBat)
    try {
        & .\build.bat
        if ($LASTEXITCODE -ne 0) {
            throw 'Bridge derlemesi basarisiz.'
        }
    }
    finally {
        Pop-Location
    }
}

$bridgeArtifacts = @(Get-BridgeArtifactPaths)
if ($bridgeArtifacts.Count -eq 0) {
    throw 'Bridge artefact bulunamadi. Online PvP pakete eklenemeyecek.'
}

$syncedArtifacts = @(Sync-BridgeArtifactsToRuntimeDir)
if ($syncedArtifacts.Count -gt 0) {
    Write-Host 'Bridge artefactleri local_artifacts\bridge altina senkronize edildi.' -ForegroundColor Green
}

$runtimeBridgeArtifacts = @(Get-ChildItem -Path (Join-Path $repoRoot 'local_artifacts\bridge\steam_net_bridge*.pyd') -File -ErrorAction SilentlyContinue)
if ($runtimeBridgeArtifacts.Count -eq 0) {
    throw 'Bridge artefact local_artifacts\bridge altina senkronize edilemedi.'
}

Write-Host 'PyInstaller build baslatiliyor...' -ForegroundColor Cyan
$quotedSpecFile = '"{0}"' -f $resolvedSpecFile
$pyInstallerArgs = @('-m', 'PyInstaller', $quotedSpecFile, '--noconfirm', '--clean')
$env:PYTHONLEGACYWINDOWSSTDIO = '1'
if (Test-Path $buildLog) {
    Remove-Item $buildLog -Force
}
if (Test-Path $buildErrLog) {
    Remove-Item $buildErrLog -Force
}

$process = Start-Process -FilePath $pythonExe `
    -ArgumentList $pyInstallerArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $buildLog `
    -RedirectStandardError $buildErrLog `
    -Wait `
    -PassThru

if ($process.ExitCode -ne 0) {
    if (Test-Path $buildLog) {
        Get-Content $buildLog | Select-Object -Last 80
    }
    if (Test-Path $buildErrLog) {
        Get-Content $buildErrLog | Select-Object -Last 80
    }
    throw 'PyInstaller build basarisiz.'
}

if (Test-Path $buildLog) {
    Get-Content $buildLog | Select-Object -Last 60
}
if (Test-Path $buildErrLog) {
    Get-Content $buildErrLog | Select-Object -Last 60
}

Write-Host 'Windows clean build tamamlandi.' -ForegroundColor Green
Write-Host "Log: $buildLog" -ForegroundColor Green