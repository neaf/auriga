#pragma once

#include <memory>

#include <aasdk/Channel/SensorSource/SensorSourceService.hpp>
#include <aasdk/Messenger/IMessenger.hpp>

#include "CaptureService.hpp"

namespace auriga {

class SensorCapture
    : public CaptureService,
      public aasdk::channel::sensorsource::ISensorSourceServiceEventHandler,
      public std::enable_shared_from_this<SensorCapture> {
 public:
  SensorCapture(boost::asio::io_service &ioService,
                aasdk::messenger::IMessenger::Pointer messenger);

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
  void onSensorStartRequest(
      const aap_protobuf::service::sensorsource::message::SensorRequest &request)
      override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<SensorCapture>::shared_from_this;

  void sendBatch(
      const aap_protobuf::service::sensorsource::message::SensorBatch &batch);

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::sensorsource::SensorSourceService> channel_;
};

}  // namespace auriga
