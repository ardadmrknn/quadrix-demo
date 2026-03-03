cmake_minimum_required(VERSION 3.18)
project(steam_net_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ── Steamworks SDK yolu ─────────────────────────────────────────────
# SDK'yı steamworks/sdk/ altına çıkar.  Yapı şöyle olmalı:
#   steamworks/sdk/public/steam/steam_api.h
#   steamworks/sdk/redistributable_bin/win64/steam_api64.lib
#
# Eğer farklı yerdeyse  -DSTEAMWORKS_SDK_DIR=<yol>  ile geçilebilir.
if(NOT DEFINED STEAMWORKS_SDK_DIR)
    set(STEAMWORKS_SDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk"
        CACHE STRING "Steamworks SDK kök dizini")
endif()

if(NOT EXISTS "${STEAMWORKS_SDK_DIR}/public/steam/steam_api.h")
    message(FATAL_ERROR
        "Steamworks SDK bulunamadi!\n"
        "  Beklenen: ${STEAMWORKS_SDK_DIR}/public/steam/steam_api.h\n"
        "  SDK'yi https://partner.steamgames.com adresinden indirip\n"
        "  steamworks/sdk/ dizinine cikartin.")
endif()

# ── Pybind11 + Python ───────────────────────────────────────────────
set(PYBIND11_FINDPYTHON ON)
find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

# ── Kaynak dosyalar ─────────────────────────────────────────────────
pybind11_add_module(steam_net_bridge steam_net_bridge.cpp)

target_include_directories(steam_net_bridge PRIVATE
    "${STEAMWORKS_SDK_DIR}/public"
)

# ── Platform linklemesi ─────────────────────────────────────────────
if(WIN32)
    if(CMAKE_SIZEOF_VOID_P EQUAL 8)
        set(STEAM_LIB_DIR "${STEAMWORKS_SDK_DIR}/redistributable_bin/win64")
        target_link_libraries(steam_net_bridge PRIVATE
            "${STEAM_LIB_DIR}/steam_api64.lib")
    else()
        set(STEAM_LIB_DIR "${STEAMWORKS_SDK_DIR}/redistributable_bin")
        target_link_libraries(steam_net_bridge PRIVATE
            "${STEAM_LIB_DIR}/steam_api.lib")
    endif()
elseif(APPLE)
    set(STEAM_LIB_DIR "${STEAMWORKS_SDK_DIR}/redistributable_bin/osx")
    target_link_libraries(steam_net_bridge PRIVATE
        "${STEAM_LIB_DIR}/libsteam_api.dylib")
elseif(UNIX)
    set(STEAM_LIB_DIR "${STEAMWORKS_SDK_DIR}/redistributable_bin/linux64")
    target_link_libraries(steam_net_bridge PRIVATE
        "${STEAM_LIB_DIR}/libsteam_api.so")
endif()

# ── Çıktıyı projenin kök dizinine kopyala ──────────────────────────
# (src/ içinden import edilebilmesi için)
set(QUADRIX_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")

install(TARGETS steam_net_bridge
    LIBRARY DESTINATION "${QUADRIX_ROOT}"
    RUNTIME DESTINATION "${QUADRIX_ROOT}"
)
