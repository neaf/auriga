#pragma once

#include <memory>

#include <aasdk/Channel/MediaSource/MediaSourceService.hpp>
#include <aasdk/Channel/MediaSource/Audio/MicrophoneAudioChannel.hpp>
#include <aasdk/Messenger/IMessenger.hpp>

#include "CaptureService.hpp"

namespace auriga {

class MicrophoneCapture
    : public CaptureService,
      public aasdk::channel::mediasource::IMediaSourceServiceEventHandler,
      public std::enable_shared_from_this<MicrophoneCapture> {
 public:
  MicrophoneCapture(boost::asio::io_service &ioService,
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
  void onMediaChannelSetupRequest(
      const aap_protobuf::service::media::shared::message::Setup &request)
      override;
  void onMediaSourceOpenRequest(
      const aap_protobuf::service::media::source::message::MicrophoneRequest
          &request) override;
  void onMediaChannelAckIndication(
      const aap_protobuf::service::media::source::message::Ack &indication)
      override;
  void onChannelError(const aasdk::error::Error &error) override;

 private:
  using std::enable_shared_from_this<MicrophoneCapture>::shared_from_this;

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::mediasource::IMediaSourceService> channel_;
};

}  // namespace auriga
