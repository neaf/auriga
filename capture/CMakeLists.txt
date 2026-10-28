cmake_minimum_required(VERSION 3.16)
project(auriga_capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# aasdk and aap_protobuf are built in ../build-aasdk by the project's
# instructions; link against that tree directly. Both paths are cache
# variables so the same source builds on the Pi (armv7 Linux) and the Mac.
set(AASDK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/../aasdk" CACHE PATH "aasdk source tree")
set(AASDK_BUILD "${CMAKE_CURRENT_SOURCE_DIR}/../build-aasdk" CACHE PATH "aasdk build tree")

if(APPLE)
  # aasdk's macOS CMake builds static libraries.
  set(AASDK_LIB "${AASDK_BUILD}/lib/libaasdk.a")
  set(AAP_PROTOBUF_LIB "${AASDK_BUILD}/lib/libaap_protobuf.a")
else()
  set(AASDK_LIB "${AASDK_BUILD}/lib/libaasdk.so")
  set(AAP_PROTOBUF_LIB "${AASDK_BUILD}/lib/libaap_protobuf.so")
endif()

add_library(aasdk SHARED IMPORTED)
set_target_properties(aasdk PROPERTIES
  IMPORTED_LOCATION "${AASDK_LIB}"
  INTERFACE_INCLUDE_DIRECTORIES
    "${AASDK_SOURCE}/include;${AASDK_BUILD}/include;${AASDK_BUILD}/protobuf"
)

add_library(aap_protobuf SHARED IMPORTED)
set_target_properties(aap_protobuf PROPERTIES
  IMPORTED_LOCATION "${AAP_PROTOBUF_LIB}"
  INTERFACE_INCLUDE_DIRECTORIES "${AASDK_BUILD}/protobuf"
)

list(APPEND CMAKE_MODULE_PATH "${AASDK_SOURCE}/cmake_modules")

find_package(Boost REQUIRED COMPONENTS system log_setup log)
find_package(OpenSSL REQUIRED)
find_package(Protobuf REQUIRED)
find_package(libusb-1.0 REQUIRED)
find_package(Threads REQUIRED)

add_executable(auriga_capture
  src/main.cpp
  src/Usb.cpp
  src/HeadUnit.cpp
  src/VideoCapture.cpp
  src/AudioCapture.cpp
  src/InputCapture.cpp
  src/BluetoothCapture.cpp
  src/SensorCapture.cpp
  src/MicrophoneCapture.cpp
  src/WifiProjectionCapture.cpp
  src/WavWriter.cpp
)

target_include_directories(auriga_capture PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src
  ${LIBUSB_1_INCLUDE_DIRS}
)

target_link_libraries(auriga_capture PRIVATE
  aasdk
  aap_protobuf
  protobuf::libprotobuf
  Boost::system
  Boost::log_setup
  Boost::log
  OpenSSL::SSL
  OpenSSL::Crypto
  ${LIBUSB_1_LIBRARIES}
  Threads::Threads
)

set_target_properties(auriga_capture PROPERTIES
  BUILD_RPATH "${AASDK_BUILD}/lib"
)
