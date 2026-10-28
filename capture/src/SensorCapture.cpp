#include "SensorCapture.hpp"

#include <functional>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/sensorsource/message/DrivingStatus.pb.h>
#include <aap_protobuf/service/sensorsource/message/NightModeData.pb.h>
#include <aap_protobuf/service/sensorsource/message/SensorBatch.pb.h>
#include <aap_protobuf/service/sensorsource/message/SensorStartResponseMessage.pb.h>
#include <aap_protobuf/service/sensorsource/message/SensorType.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

SensorCapture::SensorCapture(boost::asio::io_service &ioService,
                             aasdk::messenger::IMessenger::Pointer messenger)
    : strand_(ioService),
      channel_(
          std::make_shared<aasdk::channel::sensorsource::SensorSourceService>(
              strand_, std::move(messenger))) {}

void SensorCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "sensor channel start";
    channel_->receive(self);
  });
}

void SensorCapture::stop() {}
void SensorCapture::pause() {}
void SensorCapture::resume() {}

void SensorCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *sensor = service->mutable_sensor_source_service();
  sensor->add_sensors()->set_sensor_type(
      aap_protobuf::service::sensorsource::message::SensorType::
          SENSOR_DRIVING_STATUS_DATA);
  sensor->add_sensors()->set_sensor_type(
      aap_protobuf::service::sensorsource::message::SensorType::
          SENSOR_LOCATION);
  sensor->add_sensors()->set_sensor_type(
      aap_protobuf::service::sensorsource::message::SensorType::
          SENSOR_NIGHT_MODE);

  AURIGA_INFO << "advertised sensor channel " << service->id();
}

void SensorCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "sensor channel open";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&SensorCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void SensorCapture::onSensorStartRequest(
    const aap_protobuf::service::sensorsource::message::SensorRequest
        &request) {
  const auto type = request.type();
  AURIGA_INFO << "sensor start request type "
              << aap_protobuf::service::sensorsource::message::SensorType_Name(
                     type);

  aap_protobuf::service::sensorsource::message::SensorStartResponseMessage
      response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this(), type]() {
        aap_protobuf::service::sensorsource::message::SensorBatch batch;
        switch (type) {
          case aap_protobuf::service::sensorsource::message::SensorType::
              SENSOR_DRIVING_STATUS_DATA:
            batch.add_driving_status_data()->set_status(
                aap_protobuf::service::sensorsource::message::DrivingStatus::
                    DRIVE_STATUS_UNRESTRICTED);
            break;
          case aap_protobuf::service::sensorsource::message::SensorType::
              SENSOR_NIGHT_MODE:
            batch.add_night_mode_data()->set_night_mode(false);
            break;
          case aap_protobuf::service::sensorsource::message::SensorType::
              SENSOR_LOCATION:
            // The Pi has no GPS. Send an empty batch; the phone will use its
            // own location instead of a fabricated head-unit position.
            break;
          default:
            break;
        }
        sendBatch(batch);
      },
      std::bind(&SensorCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendSensorStartResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void SensorCapture::sendBatch(
    const aap_protobuf::service::sensorsource::message::SensorBatch &batch) {
  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&SensorCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendSensorEventIndication(batch, std::move(promise));
}

void SensorCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "sensor channel error: " << error.what();
}

}  // namespace auriga
