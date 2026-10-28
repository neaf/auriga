#include "MicrophoneCapture.hpp"

#include <functional>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/media/shared/message/AudioConfiguration.pb.h>
#include <aap_protobuf/service/media/shared/message/Config.pb.h>
#include <aap_protobuf/service/media/shared/message/MediaCodecType.pb.h>
#include <aap_protobuf/service/media/source/message/MicrophoneResponse.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

MicrophoneCapture::MicrophoneCapture(
    boost::asio::io_service &ioService,
    aasdk::messenger::IMessenger::Pointer messenger)
    : strand_(ioService),
      channel_(
          std::make_shared<
              aasdk::channel::mediasource::audio::MicrophoneAudioChannel>(
              strand_, std::move(messenger))) {}

void MicrophoneCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "microphone channel start";
    channel_->receive(self);
  });
}

void MicrophoneCapture::stop() {}
void MicrophoneCapture::pause() {}
void MicrophoneCapture::resume() {}

void MicrophoneCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *source = service->mutable_media_source_service();
  source->set_available_type(
      aap_protobuf::service::media::shared::message::MediaCodecType::
          MEDIA_CODEC_AUDIO_PCM);

  auto *config = source->mutable_audio_config();
  config->set_sampling_rate(48000);
  config->set_number_of_bits(16);
  config->set_number_of_channels(1);

  AURIGA_INFO << "advertised microphone channel " << service->id();
}

void MicrophoneCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "microphone channel open";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&MicrophoneCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void MicrophoneCapture::onMediaChannelSetupRequest(
    const aap_protobuf::service::media::shared::message::Setup &request) {
  (void)request;
  AURIGA_INFO << "microphone setup request";

  aap_protobuf::service::media::shared::message::Config response;
  response.set_status(
      aap_protobuf::service::media::shared::message::Config::STATUS_READY);
  response.set_max_unacked(1);
  response.add_configuration_indices(0);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&MicrophoneCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelSetupResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void MicrophoneCapture::onMediaSourceOpenRequest(
    const aap_protobuf::service::media::source::message::MicrophoneRequest
        &request) {
  AURIGA_INFO << "microphone open request open=" << request.open()
              << " anc=" << request.anc_enabled()
              << " ec=" << request.ec_enabled();

  aap_protobuf::service::media::source::message::MicrophoneResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);
  response.set_session_id(0);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&MicrophoneCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendMicrophoneOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void MicrophoneCapture::onMediaChannelAckIndication(
    const aap_protobuf::service::media::source::message::Ack &indication) {
  (void)indication;
  channel_->receive(shared_from_this());
}

void MicrophoneCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "microphone channel error: " << error.what();
}

}  // namespace auriga
