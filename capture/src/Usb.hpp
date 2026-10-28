#pragma once

#include <libusb.h>

#include <aasdk/USB/IAOAPDevice.hpp>
#include <aasdk/USB/USBWrapper.hpp>
#include <boost/asio.hpp>

namespace auriga {

class UsbContext {
 public:
  UsbContext();
  ~UsbContext();

  UsbContext(const UsbContext &) = delete;
  UsbContext &operator=(const UsbContext &) = delete;

  libusb_context *get() const { return context_; }

 private:
  libusb_context *context_ = nullptr;
};

// Finds the AutoLink dongle in MTP mode (2717:ff40) and performs the AOA
// handshake, leaving it as 18d1:2d00. Returns false if the dongle is not
// present or does not answer the AOA protocol query.
bool switchDongleToAoa(libusb_context *context);

// Waits for the dongle's AOA accessory interface and wraps it for aasdk.
aasdk::usb::IAOAPDevice::Pointer openAoapDevice(
    aasdk::usb::USBWrapper &wrapper, boost::asio::io_service &ioService,
    libusb_context *context);

}  // namespace auriga
