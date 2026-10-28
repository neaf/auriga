#include "HeadUnit.hpp"

#include <algorithm>
#include <chrono>
#include <stdexcept>

#include <aasdk/Channel/Control/ControlServiceChannel.hpp>
#include <aap_protobuf/service/control/message/AuthResponse.pb.h>
#include <aap_protobuf/service/control/message/ByeByeResponse.pb.h>
#include <aap_protobuf/service/control/message/DriverPosition.pb.h>
#include <aap_protobuf/service/control/message/NavFocusNotification.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/media/video/message/VideoFocusNotification.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

HeadUnit::HeadUnit(boost::asio::io_service &ioService,
                   aasdk::messenger::ICryptor::Pointer cryptor,
                   aasdk::transport::ITransport::Pointer transport,
                   aasdk::messenger::IMessenger::Pointer messenger,
                   std::vector<CaptureService::Pointer> services)
    : strand_(ioService),
      pingTimer_(ioService),
      cryptor_(std::move(cryptor)),
      transport_(std::move(transport)),
      messenger_(std::move(messenger)),
      control_(std::make_shared<aasdk::channel::control::ControlServiceChannel>(
          strand_, messenger_)),
      services_(std::move(services)) {}

void HeadUnit::start(QuitCallback quitCallback) {
  quitCallback_ = std::move(quitCallback);

  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "starting head unit";
    for (auto &service : services_) {
      service->start();
    }

    auto promise = aasdk::channel::SendPromise::defer(strand_);
    promise->then(
        []() {},
        std::bind(&HeadUnit::onChannelError, shared_from_this(),
                  std::placeholders::_1));
    control_->sendVersionRequest(std::move(promise));
    control_->receive(shared_from_this());
  });
}

void HeadUnit::stop() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "stopping head unit";
    pingTimer_.cancel();
    for (auto &service : services_) {
      try {
        service->stop();
      } catch (const std::exception &error) {
        AURIGA_WARN << "service stop failed: " << error.what();
      }
    }

    try {
      messenger_->stop();
    } catch (const std::exception &error) {
      AURIGA_WARN << "messenger stop failed: " << error.what();
    }
    try {
      transport_->stop();
    } catch (const std::exception &error) {
      AURIGA_WARN << "transport stop failed: " << error.what();
    }
    try {
      cryptor_->deinit();
    } catch (const std::exception &error) {
      AURIGA_WARN << "cryptor deinit failed: " << error.what();
    }
  });
}

void HeadUnit::onVersionResponse(
    uint16_t majorCode, uint16_t minorCode,
    aap_protobuf::shared::MessageStatus status) {
  AURIGA_INFO << "version response " << majorCode << "." << minorCode
              << " status " << aap_protobuf::shared::MessageStatus_Name(status);

  if (status ==
      aap_protobuf::shared::MessageStatus::STATUS_NO_COMPATIBLE_VERSION) {
    AURIGA_ERROR << "phone rejected the Android Auto version";
    triggerQuit();
    return;
  }

  try {
    cryptor_->doHandshake();
    auto promise = aasdk::channel::SendPromise::defer(strand_);
    promise->then(
        []() {},
        std::bind(&HeadUnit::onChannelError, shared_from_this(),
                  std::placeholders::_1));
    control_->sendHandshake(cryptor_->readHandshakeBuffer(), std::move(promise));
    control_->receive(shared_from_this());
  } catch (const std::exception &error) {
    AURIGA_ERROR << "TLS handshake start failed: " << error.what();
    triggerQuit();
  }
}

void HeadUnit::onHandshake(const aasdk::common::DataConstBuffer &payload) {
  AURIGA_INFO << "TLS handshake data: " << payload.size << " bytes";
  try {
    cryptor_->writeHandshakeBuffer(payload);
    if (!cryptor_->doHandshake()) {
      auto promise = aasdk::channel::SendPromise::defer(strand_);
      promise->then(
          []() {},
          std::bind(&HeadUnit::onChannelError, shared_from_this(),
                    std::placeholders::_1));
      control_->sendHandshake(cryptor_->readHandshakeBuffer(),
                              std::move(promise));
    } else {
      AURIGA_INFO << "TLS handshake complete";
      aap_protobuf::service::control::message::AuthResponse authComplete;
      authComplete.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

      auto promise = aasdk::channel::SendPromise::defer(strand_);
      promise->then(
          []() {},
          std::bind(&HeadUnit::onChannelError, shared_from_this(),
                    std::placeholders::_1));
      control_->sendAuthComplete(authComplete, std::move(promise));
    }

    control_->receive(shared_from_this());
  } catch (const std::exception &error) {
    AURIGA_ERROR << "TLS handshake failed: " << error.what();
    triggerQuit();
  }
}

void HeadUnit::onServiceDiscoveryRequest(
    const aap_protobuf::service::control::message::ServiceDiscoveryRequest
        &request) {
  AURIGA_INFO << "service discovery request from '" << request.device_name()
              << "' / '" << request.label_text() << "'";

  aap_protobuf::service::control::message::ServiceDiscoveryResponse response;
  response.set_driver_position(
      aap_protobuf::service::control::message::DriverPosition::
          DRIVER_POSITION_LEFT);
  response.set_display_name("Auriga Capture");
  response.set_probe_for_support(false);

  auto *connectionConfiguration = response.mutable_connection_configuration();
  auto *pingConfiguration = connectionConfiguration->mutable_ping_configuration();
  pingConfiguration->set_tracked_ping_count(5);
  pingConfiguration->set_timeout_ms(3000);
  pingConfiguration->set_interval_ms(1000);
  pingConfiguration->set_high_latency_threshold_ms(200);

  auto *headUnitInfo = response.mutable_headunit_info();
  headUnitInfo->set_make("Auriga");
  headUnitInfo->set_model("Raspberry Pi 3");
  headUnitInfo->set_year("2026");
  headUnitInfo->set_vehicle_id("auriga-pi");
  headUnitInfo->set_head_unit_make("Auriga");
  headUnitInfo->set_head_unit_model("AA Capture");
  headUnitInfo->set_head_unit_software_build("1");
  headUnitInfo->set_head_unit_software_version("1.0");

  for (auto &service : services_) {
    service->fillFeatures(response);
  }

  AURIGA_INFO << "advertising " << response.channels_size() << " channels";
  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this()]() {
        if (!pingStarted_) {
          pingStarted_ = true;
          sendPing();
          schedulePing();
        }
      },
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendServiceDiscoveryResponse(response, std::move(promise));
  control_->receive(shared_from_this());
}

void HeadUnit::onAudioFocusRequest(
    const aap_protobuf::service::control::message::AudioFocusRequest &request) {
  const auto state =
      request.audio_focus_type() ==
              aap_protobuf::service::control::message::AudioFocusRequestType::
                  AUDIO_FOCUS_RELEASE
          ? aap_protobuf::service::control::message::AudioFocusStateType::
                AUDIO_FOCUS_STATE_LOSS
          : aap_protobuf::service::control::message::AudioFocusStateType::
                AUDIO_FOCUS_STATE_GAIN;

  aap_protobuf::service::control::message::AudioFocusNotification response;
  response.set_focus_state(state);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendAudioFocusResponse(response, std::move(promise));
  control_->receive(shared_from_this());
}

void HeadUnit::onByeByeRequest(
    const aap_protobuf::service::control::message::ByeByeRequest &request) {
  AURIGA_INFO << "phone requested shutdown, reason " << request.reason();
  aap_protobuf::service::control::message::ByeByeResponse response;

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this()]() { triggerQuit(); },
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendShutdownResponse(response, std::move(promise));
}

void HeadUnit::onByeByeResponse(
    const aap_protobuf::service::control::message::ByeByeResponse &response) {
  (void)response;
  AURIGA_INFO << "shutdown acknowledged";
  triggerQuit();
}

void HeadUnit::onBatteryStatusNotification(
    const aap_protobuf::service::control::message::BatteryStatusNotification
        &notification) {
  (void)notification;
  control_->receive(shared_from_this());
}

void HeadUnit::onNavigationFocusRequest(
    const aap_protobuf::service::control::message::NavFocusRequestNotification
        &request) {
  (void)request;
  aap_protobuf::service::control::message::NavFocusNotification response;
  response.set_focus_type(
      aap_protobuf::service::control::message::NavFocusType::NAV_FOCUS_PROJECTED);
  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendNavigationFocusResponse(response, std::move(promise));
  control_->receive(shared_from_this());
}

void HeadUnit::onVoiceSessionRequest(
    const aap_protobuf::service::control::message::VoiceSessionNotification
        &request) {
  (void)request;
  control_->receive(shared_from_this());
}

void HeadUnit::onPingRequest(
    const aap_protobuf::service::control::message::PingRequest &request) {
  aap_protobuf::service::control::message::PingResponse response;
  response.set_timestamp(request.timestamp());

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendPingResponse(response, std::move(promise));
  control_->receive(shared_from_this());
}

void HeadUnit::onPingResponse(
    const aap_protobuf::service::control::message::PingResponse &response) {
  (void)response;
  control_->receive(shared_from_this());
}

void HeadUnit::schedulePing() {
  if (quitting_.load()) {
    return;
  }

  pingTimer_.expires_from_now(boost::posix_time::seconds(2));
  pingTimer_.async_wait(strand_.wrap(
      [this, self = shared_from_this()](const boost::system::error_code &error) {
        if (!error && !quitting_.load()) {
          sendPing();
          schedulePing();
        }
      }));
}

void HeadUnit::sendPing() {
  const auto timestamp =
      std::chrono::duration_cast<std::chrono::microseconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count();

  aap_protobuf::service::control::message::PingRequest request;
  request.set_timestamp(timestamp);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&HeadUnit::onChannelError, shared_from_this(),
                std::placeholders::_1));
  control_->sendPingRequest(request, std::move(promise));
}

void HeadUnit::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    AURIGA_WARN << "channel aborted: " << error.what();
    return;
  }
  AURIGA_ERROR << "channel error: " << error.what();
  triggerQuit();
}

void HeadUnit::triggerQuit() {
  if (quitting_.exchange(true)) {
    return;
  }
  AURIGA_INFO << "session finished";
  if (quitCallback_) {
    quitCallback_();
  }
}

}  // namespace auriga
