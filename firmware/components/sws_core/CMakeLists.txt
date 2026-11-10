# sws_core: portable firmware logic. Builds as an ESP-IDF component on the
# device and as a plain static library for host unit tests.
#
# cJSON: on the device we use Espressif's registry package (esp-matter already
# depends on it, so linking a second copy would clash). Host tests use the
# vendored copy in third_party/cjson.

set(SWS_CORE_SRCS
    src/bl0939.c
    src/energy.c
    src/protection.c
    src/proto.c
    src/relay_drive.c
    src/schedule.c
)

if(ESP_PLATFORM)
    # Online builds get cjson from idf_component.yml; offline builds use the
    # stand-in under app/offline_components.
    set(cjson_req "")
    if(DEFINED ENV{SWS_OFFLINE})
        set(cjson_req espressif__cjson)
    endif()
    idf_component_register(
        SRCS ${SWS_CORE_SRCS}
        INCLUDE_DIRS include
        REQUIRES ${cjson_req}
    )
else()
    add_library(sws_core STATIC ${SWS_CORE_SRCS} ../../third_party/cjson/cJSON.c)
    target_include_directories(sws_core PUBLIC include ../../third_party/cjson)
    target_compile_options(sws_core PRIVATE -Wall -Wextra -Werror -Wno-unused-parameter)
    target_link_libraries(sws_core PUBLIC m)
endif()
