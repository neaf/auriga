#pragma once

#include <memory>
#include <string>

#include <aasdk/Channel/MediaSink/Audio/IAudioMediaSinkService.hpp>
#include <aasdk/Channel/MediaSink/Audio/IAudioMediaSinkServiceEventHandler.hpp>
#include <aasdk/Messenger/ChannelId.hpp>
#include <aasdk/Messenger/IMessenger.hpp>

#include "CaptureService.hpp"
#include "WavWriter.hpp"

namespace auriga {

class AudioCapture
    : public CaptureService,
      public aasdk::channel::mediasink::audio::
          IAudioMediaSinkServiceEventHandler,
      public std::enable_shared_from_this<AudioCapture> {
 public:
  AudioCapture(boost::asio::io_service &ioService,
               aasdk::messenger::IMessenger::Pointer messenger,
               aasdk::messenger::ChannelId channelId, std::string path);

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
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<AudioCapture>::shared_from_this;

  void sendAck();
  const char *streamName() const;

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::mediasink::audio::IAudioMediaSinkService>
      channel_;
  std::string path_;
  WavWriter writer_;
  int32_t session_ = -1;
  uint64_t bytes_ = 0;
};

}  // namespace auriga
