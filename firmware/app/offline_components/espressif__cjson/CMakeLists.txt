# Stand-in for the espressif/cjson registry package, used only for
# offline builds (SWS_OFFLINE=1). Same upstream cJSON, vendored.
idf_component_register(
    SRCS ../../../third_party/cjson/cJSON.c
    INCLUDE_DIRS ../../../third_party/cjson
)
