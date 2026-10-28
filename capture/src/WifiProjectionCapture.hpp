#pragma once

#include <memory>
#include <string>

#include <aasdk/Channel/WifiProjection/WifiProjectionService.hpp>
#include <aasdk/Messenger/IMessenger.hpp>

#include "CaptureService.hpp"

namespace auriga {

class WifiProjectionCapture
    : public CaptureService,
      public aasdk::channel::wifiprojection::IWifiProjectionServiceEventHandler,
      public std::enable_shared_from_this<WifiProjectionCapture> {
 public:
  WifiProjectionCapture(boost::asio::io_service &ioService,
                        aasdk::messenger::IMessenger::Pointer messenger,
                        std::string bssid);

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
  void onWifiCredentialsRequest(
      const aap_protobuf::service::wifiprojection::message::
          WifiCredentialsRequest &request) override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<WifiProjectionCapture>::shared_from_this;

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::wifiprojection::WifiProjectionService>
      channel_;
  std::string bssid_;
};

}  // namespace auriga
