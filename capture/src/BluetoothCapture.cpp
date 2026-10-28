#include "BluetoothCapture.hpp"

#include <functional>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/bluetooth/message/BluetoothAuthenticationData.pb.h>
#include <aap_protobuf/service/bluetooth/message/BluetoothPairingMethod.pb.h>
#include <aap_protobuf/service/bluetooth/message/BluetoothPairingResponse.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

BluetoothCapture::BluetoothCapture(
    boost::asio::io_service &ioService,
    aasdk::messenger::IMessenger::Pointer messenger, std::string carAddress)
    : strand_(ioService),
      channel_(std::make_shared<aasdk::channel::bluetooth::BluetoothService>(
          strand_, std::move(messenger))),
      carAddress_(std::move(carAddress)) {}

void BluetoothCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "bluetooth channel start";
    channel_->receive(self);
  });
}

void BluetoothCapture::stop() {}
void BluetoothCapture::pause() {}
void BluetoothCapture::resume() {}

void BluetoothCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *bluetooth = service->mutable_bluetooth_service();
  bluetooth->set_car_address(carAddress_);
  bluetooth->add_supported_pairing_methods(
      aap_protobuf::service::bluetooth::message::BluetoothPairingMethod::
          BLUETOOTH_PAIRING_PIN);
  bluetooth->add_supported_pairing_methods(
      aap_protobuf::service::bluetooth::message::BluetoothPairingMethod::
          BLUETOOTH_PAIRING_NUMERIC_COMPARISON);

  AURIGA_INFO << "advertised bluetooth channel " << service->id()
              << " car=" << carAddress_;
}

void BluetoothCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "bluetooth channel open";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&BluetoothCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void BluetoothCapture::onBluetoothPairingRequest(
    const aap_protobuf::service::bluetooth::message::BluetoothPairingRequest
        &request) {
  AURIGA_INFO << "bluetooth pairing request from " << request.phone_address()
              << " method "
              << aap_protobuf::service::bluetooth::message::
                     BluetoothPairingMethod_Name(request.pairing_method());

  aap_protobuf::service::bluetooth::message::BluetoothPairingResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);
  // The phone is already paired to the dongle's Bluetooth. Reporting
  // "already paired" makes the phone skip the head-unit pairing exchange.
  // Sending fake authentication data here (the old PIN 123456) makes the
  // dongle reset the AA session with AASDK Error 10.
  response.set_already_paired(true);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this()]() {
        AURIGA_INFO << "reported already paired; not sending auth data";
      },
      std::bind(&BluetoothCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendBluetoothPairingResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void BluetoothCapture::sendAuthenticationData() {
  aap_protobuf::service::bluetooth::message::BluetoothAuthenticationData data;
  data.set_auth_data("123456");
  data.set_pairing_method(
      aap_protobuf::service::bluetooth::message::BluetoothPairingMethod::
          BLUETOOTH_PAIRING_PIN);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this()]() {
        AURIGA_INFO << "sent bluetooth auth data (PIN 123456)";
      },
      std::bind(&BluetoothCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendBluetoothAuthenticationData(data, std::move(promise));
}

void BluetoothCapture::onBluetoothAuthenticationResult(
    const aap_protobuf::service::bluetooth::message::
        BluetoothAuthenticationResult &request) {
  AURIGA_INFO << "bluetooth authentication result: "
              << aap_protobuf::shared::MessageStatus_Name(request.status());
  channel_->receive(shared_from_this());
}

void BluetoothCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "bluetooth channel error: " << error.what();
}

}  // namespace auriga
