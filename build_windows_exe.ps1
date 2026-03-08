param(
    [switch]$Clean,
    [switch]$RebuildBridge,
    [string]$SpecFile = 'tetris.spec'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

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
        } catch {
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw 'Python bulunamadi. QUADRIX_PYTHON ayarlayin veya Python 3.12 kurun.'
}

$pythonExe = Resolve-QuadrixPython
$buildLog = Join-Path $repoRoot 'build_stdout.log'
$buildErrLog = Join-Path $repoRoot 'build_stderr.log'

Write-Host '==============================================' -ForegroundColor Cyan
Write-Host '  Quadrix Windows Clean Build' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host "Python: $pythonExe" -ForegroundColor Green
Write-Host "Spec: $SpecFile" -ForegroundColor Green

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
    Get-ChildItem -Path $repoRoot -Filter 'steam_net_bridge*.pyd' -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $repoRoot -Filter 'steam_net_bridge*.so' -ErrorAction SilentlyContinue | Remove-Item -Force
}

$bridgeExists = @(Get-ChildItem -Path $repoRoot -Filter 'steam_net_bridge*.pyd' -ErrorAction SilentlyContinue).Count -gt 0
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

Write-Host 'PyInstaller build baslatiliyor...' -ForegroundColor Cyan
$pyInstallerArgs = @('-m', 'PyInstaller', $SpecFile, '--noconfirm', '--clean')
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