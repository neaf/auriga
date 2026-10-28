#pragma once

#include <atomic>
#include <functional>
#include <memory>
#include <vector>

#include <boost/asio.hpp>

// IControlServiceChannelEventHandler.hpp uses these two types without
// including their headers, so they must come first.
#include <aap_protobuf/shared/MessageStatus.pb.h>
#include <aap_protobuf/service/control/message/ByeByeRequest.pb.h>

#include <aasdk/Channel/Control/IControlServiceChannelEventHandler.hpp>
#include <aasdk/Messenger/ICryptor.hpp>
#include <aasdk/Messenger/IMessenger.hpp>
#include <aasdk/Transport/ITransport.hpp>
#include <aap_protobuf/service/control/message/AudioFocusNotification.pb.h>

#include "CaptureService.hpp"

namespace aasdk::channel::control {
class ControlServiceChannel;
}

namespace auriga {

class HeadUnit : public aasdk::channel::control::IControlServiceChannelEventHandler,
                 public std::enable_shared_from_this<HeadUnit> {
 public:
  using QuitCallback = std::function<void()>;

  HeadUnit(boost::asio::io_service &ioService,
           aasdk::messenger::ICryptor::Pointer cryptor,
           aasdk::transport::ITransport::Pointer transport,
           aasdk::messenger::IMessenger::Pointer messenger,
           std::vector<CaptureService::Pointer> services);

  void start(QuitCallback quitCallback);
  void stop();

  void onVersionResponse(
      uint16_t majorCode, uint16_t minorCode,
      aap_protobuf::shared::MessageStatus status) override;
  void onHandshake(const aasdk::common::DataConstBuffer &payload) override;
  void onServiceDiscoveryRequest(
      const aap_protobuf::service::control::message::ServiceDiscoveryRequest
          &request) override;
  void onAudioFocusRequest(
      const aap_protobuf::service::control::message::AudioFocusRequest &request)
      override;
  void onByeByeRequest(
      const aap_protobuf::service::control::message::ByeByeRequest &request)
      override;
  void onByeByeResponse(
      const aap_protobuf::service::control::message::ByeByeResponse &response)
      override;
  void onBatteryStatusNotification(
      const aap_protobuf::service::control::message::BatteryStatusNotification
          &notification) override;
  void onNavigationFocusRequest(
      const aap_protobuf::service::control::message::NavFocusRequestNotification
          &request) override;
  void onVoiceSessionRequest(
      const aap_protobuf::service::control::message::VoiceSessionNotification
          &request) override;
  void onPingRequest(
      const aap_protobuf::service::control::message::PingRequest &request)
      override;
  void onPingResponse(
      const aap_protobuf::service::control::message::PingResponse &response)
      override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<HeadUnit>::shared_from_this;

  void triggerQuit();
  void schedulePing();
  void sendPing();

  boost::asio::io_service::strand strand_;
  boost::asio::deadline_timer pingTimer_;
  aasdk::messenger::ICryptor::Pointer cryptor_;
  aasdk::transport::ITransport::Pointer transport_;
  aasdk::messenger::IMessenger::Pointer messenger_;
  std::shared_ptr<aasdk::channel::control::ControlServiceChannel> control_;
  std::vector<CaptureService::Pointer> services_;
  QuitCallback quitCallback_;
  std::atomic<bool> quitting_{false};
  bool pingStarted_ = false;
};

}  // namespace auriga
