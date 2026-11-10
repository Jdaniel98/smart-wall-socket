cmake_minimum_required(VERSION 3.16)
project(sws_host_tests C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

option(SWS_SANITIZE "Build tests with AddressSanitizer and UBSan" ON)
if(SWS_SANITIZE)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()

add_subdirectory(../../components/sws_core sws_core)

add_executable(sws_tests
    main.c
    test_bl0939_energy.c
    test_protection.c
    test_misc.c
)
target_compile_options(sws_tests PRIVATE -Wall -Wextra -Wno-unused-parameter)
target_link_libraries(sws_tests PRIVATE sws_core)

enable_testing()
add_test(NAME sws_tests COMMAND sws_tests)
