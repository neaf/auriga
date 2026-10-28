#pragma once

#include <memory>
#include <string>

#include <aasdk/Channel/Bluetooth/BluetoothService.hpp>
#include <aasdk/Messenger/IMessenger.hpp>

#include "CaptureService.hpp"

namespace auriga {

class BluetoothCapture
    : public CaptureService,
      public aasdk::channel::bluetooth::IBluetoothServiceEventHandler,
      public std::enable_shared_from_this<BluetoothCapture> {
 public:
  BluetoothCapture(boost::asio::io_service &ioService,
                   aasdk::messenger::IMessenger::Pointer messenger,
                   std::string carAddress);

  void start() override;
  void stop() override;
  void pause() override;
  void resume() override;
  void fillFeatures(
      aap_protobuf::service::control::message::ServiceDiscoveryResponse
          &response) override;

  void onChannelOpenRequest(
      const aap_protobuf::service::control::message::ChannelOpenRequest &request)
      override;
  void onBluetoothPairingRequest(
      const aap_protobuf::service::bluetooth::message::BluetoothPairingRequest
          &request) override;
  void onBluetoothAuthenticationResult(
      const aap_protobuf::service::bluetooth::message::
          BluetoothAuthenticationResult &request) override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<BluetoothCapture>::shared_from_this;

  void sendAuthenticationData();

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::bluetooth::BluetoothService> channel_;
  std::string carAddress_;
};

}  // namespace auriga
