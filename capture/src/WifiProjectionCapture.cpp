#include "WifiProjectionCapture.hpp"

#include <functional>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/wifiprojection/message/AccessPointType.pb.h>
#include <aap_protobuf/service/wifiprojection/message/WifiCredentialsResponse.pb.h>
#include <aap_protobuf/service/wifiprojection/message/WifiSecurityMode.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

WifiProjectionCapture::WifiProjectionCapture(
    boost::asio::io_service &ioService,
    aasdk::messenger::IMessenger::Pointer messenger, std::string bssid)
    : strand_(ioService),
      channel_(
          std::make_shared<aasdk::channel::wifiprojection::WifiProjectionService>(
              strand_, std::move(messenger))),
      bssid_(std::move(bssid)) {}

void WifiProjectionCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "wifi projection channel start";
    channel_->receive(self);
  });
}

void WifiProjectionCapture::stop() {}
void WifiProjectionCapture::pause() {}
void WifiProjectionCapture::resume() {}

void WifiProjectionCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *wifi = service->mutable_wifi_projection_service();
  wifi->set_car_wifi_bssid(bssid_);

  AURIGA_INFO << "advertised wifi projection channel " << service->id()
              << " bssid=" << bssid_;
}

void WifiProjectionCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "wifi projection channel open";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&WifiProjectionCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void WifiProjectionCapture::onWifiCredentialsRequest(
    const aap_protobuf::service::wifiprojection::message::
        WifiCredentialsRequest &request) {
  (void)request;
  AURIGA_INFO << "wifi credentials request";

  aap_protobuf::service::wifiprojection::message::WifiCredentialsResponse
      response;
  response.set_access_point_type(
      aap_protobuf::service::wifiprojection::message::AccessPointType::STATIC);
  response.set_car_wifi_ssid("AutoLink-A512");
  response.set_car_wifi_password("12345678");
  response.set_car_wifi_security_mode(
      aap_protobuf::service::wifiprojection::message::WifiSecurityMode::
          WPA2_PERSONAL);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&WifiProjectionCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendWifiCredentialsResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void WifiProjectionCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "wifi projection channel error: " << error.what();
}

}  // namespace auriga
