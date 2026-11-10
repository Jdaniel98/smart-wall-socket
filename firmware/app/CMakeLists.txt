# Smart Wall Socket firmware (ESP-IDF v6.0.2 + esp_matter 1.6.x).
cmake_minimum_required(VERSION 3.16)

set(PROJECT_VER "0.1.0")
set(EXTRA_COMPONENT_DIRS ../components)

# Offline builds (no component registry): Matter off, local cJSON.
# See firmware/README.md, "Building without internet".
if(DEFINED ENV{SWS_OFFLINE})
    list(APPEND EXTRA_COMPONENT_DIRS offline_components)
    # Path to a clone of github.com/espressif/esp-mqtt named espressif__mqtt.
    if(DEFINED ENV{SWS_OFFLINE_EXTRA})
        list(APPEND EXTRA_COMPONENT_DIRS $ENV{SWS_OFFLINE_EXTRA})
    endif()
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(smart_wall_socket)

# Flags the Matter SDK expects (from Espressif's esp-matter examples).
idf_build_set_property(CXX_COMPILE_OPTIONS "-std=gnu++17;-Os;-DCHIP_HAVE_CONFIG_H" APPEND)
idf_build_set_property(C_COMPILE_OPTIONS "-Os" APPEND)
idf_build_set_property(COMPILE_OPTIONS "-Wno-format-nonliteral;-Wno-format-security" APPEND)
