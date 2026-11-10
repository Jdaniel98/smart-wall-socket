# mqtt and cjson come from the component registry (idf_component.yml). In
# offline builds the registry is off, so they are required explicitly.
set(extra_reqs "")
if(DEFINED ENV{SWS_OFFLINE})
    set(extra_reqs espressif__mqtt)
endif()

idf_component_register(
    SRCS
        app_main.c
        app_matter.cpp
        board/board_dualr3v2.c
        console.c
        control.c
        inputs.c
        metering.c
        net.c
        relays.c
        status_led.c
        storage.c
    INCLUDE_DIRS . board
    REQUIRES
        sws_core
        console
        esp_driver_gpio
        esp_driver_ledc
        esp_driver_uart
        esp_event
        esp_netif
        esp_timer
        esp_wifi
        nvs_flash
        ${extra_reqs}
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wno-unused-parameter
                       -Wno-missing-field-initializers)
