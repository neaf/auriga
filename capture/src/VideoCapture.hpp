#pragma once

#include <fstream>
#include <memory>
#include <string>

#include <aasdk/Channel/MediaSink/Video/Channel/VideoChannel.hpp>

#include "CaptureService.hpp"

namespace auriga {

class VideoCapture
    : public CaptureService,
      public aasdk::channel::mediasink::video::
          IVideoMediaSinkServiceEventHandler,
      public std::enable_shared_from_this<VideoCapture> {
 public:
  VideoCapture(boost::asio::io_service &ioService,
               aasdk::messenger::IMessenger::Pointer messenger,
               std::string path);

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
  void onMediaChannelSetupRequest(
      const aap_protobuf::service::media::shared::message::Setup &request)
      override;
  void onMediaChannelStartIndication(
      const aap_protobuf::service::media::shared::message::Start &indication)
      override;
  void onMediaChannelStopIndication(
      const aap_protobuf::service::media::shared::message::Stop &indication)
      override;
  void onMediaWithTimestampIndication(
      aasdk::messenger::Timestamp::ValueType timestamp,
      const aasdk::common::DataConstBuffer &buffer) override;
  void onMediaIndication(const aasdk::common::DataConstBuffer &buffer) override;
  void onVideoFocusRequest(
      const aap_protobuf::service::media::video::message::
          VideoFocusRequestNotification &request) override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<VideoCapture>::shared_from_this;

  void sendAck();
  void sendVideoFocusIndication();

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::mediasink::video::channel::VideoChannel>
      channel_;
  std::string path_;
  std::ofstream file_;
  int32_t session_ = -1;
  uint64_t bytes_ = 0;
};

}  // namespace auriga
