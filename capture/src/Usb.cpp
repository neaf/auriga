#include "Usb.hpp"

#include <chrono>
#include <cstring>
#include <stdexcept>
#include <thread>

#include <aasdk/USB/AOAPDevice.hpp>

#include "Log.hpp"

namespace auriga {
namespace {

constexpr uint16_t kDongleVendor = 0x2717;
constexpr uint16_t kDongleProduct = 0xFF40;
constexpr uint16_t kAoapVendor = 0x18D1;
constexpr uint16_t kAoapProduct = 0x2D00;

constexpr uint8_t kGetProtocol = 51;
constexpr uint8_t kSendString = 52;
constexpr uint8_t kStart = 53;

bool sendString(libusb_device_handle *handle, int index, const char *value) {
  const int transferred = libusb_control_transfer(
      handle, LIBUSB_ENDPOINT_OUT | LIBUSB_REQUEST_TYPE_VENDOR, kSendString, 0,
      static_cast<uint16_t>(index),
      reinterpret_cast<unsigned char *>(const_cast<char *>(value)),
      static_cast<uint16_t>(std::strlen(value) + 1), 1000);
  return transferred >= 0;
}

}  // namespace

UsbContext::UsbContext() {
  if (libusb_init(&context_) != 0) {
    context_ = nullptr;
    throw std::runtime_error("libusb_init failed");
  }
}

UsbContext::~UsbContext() {
  if (context_ != nullptr) {
    libusb_exit(context_);
  }
}

bool switchDongleToAoa(libusb_context *context) {
  libusb_device **devices = nullptr;
  const ssize_t count = libusb_get_device_list(context, &devices);
  if (count < 0) {
    AURIGA_ERROR << "libusb_get_device_list failed";
    return false;
  }

  libusb_device_handle *handle = nullptr;
  for (ssize_t i = 0; i < count; ++i) {
    libusb_device_descriptor descriptor{};
    if (libusb_get_device_descriptor(devices[i], &descriptor) != 0) {
      continue;
    }
    if (descriptor.idVendor == kDongleVendor &&
        descriptor.idProduct == kDongleProduct) {
      if (libusb_open(devices[i], &handle) == 0) {
        break;
      }
      handle = nullptr;
    }
  }
  libusb_free_device_list(devices, 1);

  if (handle == nullptr) {
    AURIGA_WARN << "AutoLink dongle not found in MTP mode";
    return false;
  }

  unsigned char protocol[2] = {0, 0};
  const int transferred = libusb_control_transfer(
      handle, LIBUSB_ENDPOINT_IN | LIBUSB_REQUEST_TYPE_VENDOR, kGetProtocol, 0,
      0, protocol, sizeof(protocol), 1000);
  if (transferred < 2) {
    AURIGA_ERROR << "AOA GET_PROTOCOL failed: " << transferred;
    libusb_close(handle);
    return false;
  }

  const int version = protocol[0] | (protocol[1] << 8);
  AURIGA_INFO << "AOA protocol version " << version;

  const bool strings_ok =
      sendString(handle, 0, "Auriga") &&
      sendString(handle, 1, "Auriga Pi Capture") &&
      sendString(handle, 2, "Android Auto capture head unit") &&
      sendString(handle, 3, "1.0") && sendString(handle, 4, "") &&
      sendString(handle, 5, "auriga-pi");
  if (!strings_ok) {
    AURIGA_ERROR << "AOA SEND_STRING failed";
    libusb_close(handle);
    return false;
  }

  // The dongle may drop off the bus immediately after this request, so a
  // negative return is not necessarily fatal.
  const int started = libusb_control_transfer(
      handle, LIBUSB_ENDPOINT_OUT | LIBUSB_REQUEST_TYPE_VENDOR, kStart, 0, 0,
      nullptr, 0, 1000);
  AURIGA_INFO << "AOA ACCESSORY_START returned " << started;
  libusb_close(handle);
  return true;
}

aasdk::usb::IAOAPDevice::Pointer openAoapDevice(
    aasdk::usb::USBWrapper &wrapper, boost::asio::io_service &ioService,
    libusb_context *context) {
  (void)context;

  for (int attempt = 0; attempt < 50; ++attempt) {
    auto handle = wrapper.openDeviceWithVidPid(kAoapVendor, kAoapProduct);
    if (handle) {
      try {
        auto device = aasdk::usb::AOAPDevice::create(wrapper, ioService, handle);
        AURIGA_INFO << "opened AOA accessory";
        return device;
      } catch (const std::exception &error) {
        AURIGA_WARN << "AOAPDevice::create failed: " << error.what();
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }

  throw std::runtime_error("timed out waiting for 18d1:2d00");
}

}  // namespace auriga
