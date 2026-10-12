cmake_minimum_required(VERSION 3.21)
project(brainssd_native_logits_probe LANGUAGES C CXX)

# Require an existing, independently pinned checkout: never fetch at configure.
if(NOT DEFINED LLAMA_SOURCE_DIR OR NOT EXISTS "${LLAMA_SOURCE_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "Set -DLLAMA_SOURCE_DIR=<pinned llama.cpp checkout>")
endif()

set(GGML_CUDA OFF CACHE BOOL "" FORCE)
set(GGML_VULKAN OFF CACHE BOOL "" FORCE)
set(GGML_HIP OFF CACHE BOOL "" FORCE)
set(GGML_SYCL OFF CACHE BOOL "" FORCE)
set(GGML_RPC OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)

# Put the executable and its Windows DLLs into a single directory.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
add_subdirectory("${LLAMA_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/llama-dependency" EXCLUDE_FROM_ALL)

add_executable(brainssd-native-logits native_logits_probe.cpp)
target_link_libraries(brainssd-native-logits PRIVATE llama)
target_compile_features(brainssd-native-logits PRIVATE cxx_std_17)
