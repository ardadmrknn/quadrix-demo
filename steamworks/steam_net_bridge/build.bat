@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ═══════════════════════════════════════════════════════════════════
REM  Quadrix Steam Net Bridge — Windows Build Script
REM  
REM  Gereksinimler:
REM    1. Visual Studio 2019/2022 (veya Build Tools) kurulu olmalı
REM    2. Python 3.x + pybind11:  pip install pybind11
REM    3. CMake (VS ile birlikte gelir, ayrı kurulum gerekmez)
REM    4. Steamworks SDK:  steamworks\sdk\ altına çıkarılmış olmalı
REM
REM  Kullanım:
REM    cd steamworks\steam_net_bridge
REM    build.bat
REM ═══════════════════════════════════════════════════════════════════

echo.
echo ╔═══════════════════════════════════════════╗
echo ║  Quadrix Steam Net Bridge — Derleniyor    ║
echo ╚═══════════════════════════════════════════╝
echo.

REM ── Visual Studio cmake'ini bul ──────────────────────────────────
REM Önce sistem PATH'te cmake var mı kontrol et
where cmake >nul 2>&1
if %ERRORLEVEL% neq 0 (
    REM VS2022 CMake
    if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" (
        set "PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%PATH%"
        echo [BILGI] VS2022 CMake bulundu.
    ) else if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" (
        set "PATH=C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%PATH%"
        echo [BILGI] VS2022 Pro CMake bulundu.
    ) else if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" (
        set "PATH=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%PATH%"
        echo [BILGI] VS2022 Enterprise CMake bulundu.
    ) else (
        echo [HATA] cmake bulunamadi. VS2022 veya ayri CMake kurulumu gerekli.
        echo        Kurulum: winget install cmake
        exit /b 1
    )
)

REM ── Python secimi (varsayilan: 3.12) ─────────────────────────────
set "PYTHON_EXE="

if defined QUADRIX_PYTHON (
    set "PYTHON_EXE=%QUADRIX_PYTHON%"
) else (
    where py >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        py -3.12 -c "import sys; print(sys.executable)" >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            for /f "usebackq delims=" %%i in (`py -3.12 -c "import sys; print(sys.executable)"`) do set "PYTHON_EXE=%%i"
        )
    )

    if not defined PYTHON_EXE (
        where python >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            for /f "usebackq delims=" %%i in (`python -c "import sys; print(sys.executable)"`) do set "PYTHON_EXE=%%i"
        )
    )
)

if not defined PYTHON_EXE (
    echo [HATA] Python bulunamadi.
    echo        Python 3.12 kurun veya QUADRIX_PYTHON ortam degiskeni verin.
    exit /b 1
)

echo [BILGI] Kullanilan Python: !PYTHON_EXE!
set "PY_TAG_FILE=%TEMP%\quadrix_py_tag.txt"
"!PYTHON_EXE!" -c "import sys; print(str(sys.version_info.major) + str(sys.version_info.minor))" > "!PY_TAG_FILE!" 2>nul
set /p PY_TAG=<"!PY_TAG_FILE!"
del /f /q "!PY_TAG_FILE!" >nul 2>&1
if not defined PY_TAG set "PY_TAG=312"
set "BUILD_DIR=build_py!PY_TAG!"
echo [BILGI] Build dizini: !BUILD_DIR!

REM Pybind11 kontrolü
"!PYTHON_EXE!" -c "import pybind11" >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [BILGI] pybind11 kuruluyor...
    "!PYTHON_EXE!" -m pip install pybind11
)

REM Pybind11 cmake dizinini otomatik bul
set "PYBIND11_DIR_FILE=%TEMP%\quadrix_pybind11_dir.txt"
"!PYTHON_EXE!" -c "import pybind11; print(pybind11.get_cmake_dir())" > "!PYBIND11_DIR_FILE!" 2>nul
set /p PYBIND11_CMAKE_DIR=<"!PYBIND11_DIR_FILE!"
del /f /q "!PYBIND11_DIR_FILE!" >nul 2>&1
if not defined PYBIND11_CMAKE_DIR (
    echo [HATA] pybind11 CMake dizini bulunamadi.
    echo        "!PYTHON_EXE!" -m pip install pybind11 komutunu kontrol edin.
    exit /b 1
)
echo [BILGI] pybind11 cmake dizini: !PYBIND11_CMAKE_DIR!

REM SDK kontrolü
if not exist "..\sdk\public\steam\steam_api.h" (
    echo [HATA] Steamworks SDK bulunamadi!
    echo        steamworks\sdk\ dizinine SDK'yi cikartin.
    echo        Indirme: https://partner.steamgames.com
    exit /b 1
)

REM Build dizini
if not exist "!BUILD_DIR!" mkdir "!BUILD_DIR!"
cd /d "!BUILD_DIR!"

REM CMake configure + build
cmake .. -G "Visual Studio 17 2022" -A x64 ^
    -Dpybind11_DIR="!PYBIND11_CMAKE_DIR!" ^
    -DPYBIND11_FINDPYTHON=ON ^
    -DPython_EXECUTABLE="!PYTHON_EXE!" ^
    -DPYTHON_EXECUTABLE="!PYTHON_EXE!" ^
    -DCMAKE_BUILD_TYPE=Release

if !ERRORLEVEL! neq 0 (
    echo.
    echo [BILGI] VS2022 bulunamadiysa VS2019 deneniyor...
    if exist "CMakeCache.txt" del /f /q "CMakeCache.txt" >nul 2>&1
    if exist "CMakeFiles" rmdir /s /q "CMakeFiles" >nul 2>&1
    cmake .. -G "Visual Studio 16 2019" -A x64 ^
        -Dpybind11_DIR="!PYBIND11_CMAKE_DIR!" ^
        -DPYBIND11_FINDPYTHON=ON ^
        -DPython_EXECUTABLE="!PYTHON_EXE!" ^
        -DPYTHON_EXECUTABLE="!PYTHON_EXE!" ^
        -DCMAKE_BUILD_TYPE=Release
)

cmake --build . --config Release
if !ERRORLEVEL! neq 0 (
    echo [HATA] Derleme basarisiz!
    cd ..
    exit /b 1
)

REM DLL'i local_artifacts/bridge klasorune kopyala
echo.
echo [KOPYALAMA] steam_net_bridge.pyd dosyasi local_artifacts/bridge klasorune kopyalaniyor...
if not exist "..\..\..\local_artifacts\bridge" mkdir "..\..\..\local_artifacts\bridge"
for /r "Release" %%f in (steam_net_bridge*.pyd) do (
    copy /Y "%%f" "..\..\..\local_artifacts\bridge" >nul
    echo   → %%~nxf kopyalandi
)

cd ..
echo.
echo ═══════════════════════════════════════════
echo   Derleme basarili!
echo   steam_net_bridge (Python !PY_TAG!) local_artifacts/bridge altinda hazir.
echo ═══════════════════════════════════════════
echo.
endlocal
