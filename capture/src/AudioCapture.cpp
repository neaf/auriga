#include "AudioCapture.hpp"

#include <functional>
#include <stdexcept>

#include <aasdk/Channel/MediaSink/Audio/Channel/GuidanceAudioChannel.hpp>
#include <aasdk/Channel/MediaSink/Audio/Channel/MediaAudioChannel.hpp>
#include <aasdk/Channel/MediaSink/Audio/Channel/SystemAudioChannel.hpp>
#include <aasdk/Channel/MediaSink/Audio/Channel/TelephonyAudioChannel.hpp>
#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/media/shared/message/Config.pb.h>
#include <aap_protobuf/service/media/shared/message/MediaCodecType.pb.h>
#include <aap_protobuf/service/media/sink/message/AudioStreamType.pb.h>
#include <aap_protobuf/service/media/source/message/Ack.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {
namespace {

using aasdk::messenger::ChannelId;
using AudioChannel =
    aasdk::channel::mediasink::audio::IAudioMediaSinkService;

std::shared_ptr<AudioChannel> makeChannel(
    ChannelId id, boost::asio::io_service::strand &strand,
    aasdk::messenger::IMessenger::Pointer messenger) {
  using namespace aasdk::channel::mediasink::audio::channel;

  switch (id) {
    case ChannelId::MEDIA_SINK_MEDIA_AUDIO:
      return std::make_shared<MediaAudioChannel>(strand, std::move(messenger));
    case ChannelId::MEDIA_SINK_SYSTEM_AUDIO:
      return std::make_shared<SystemAudioChannel>(strand, std::move(messenger));
    case ChannelId::MEDIA_SINK_GUIDANCE_AUDIO:
      return std::make_shared<GuidanceAudioChannel>(strand,
                                                    std::move(messenger));
    case ChannelId::MEDIA_SINK_TELEPHONY_AUDIO:
      return std::make_shared<TelephonyAudioChannel>(strand,
                                                     std::move(messenger));
    default:
      throw std::invalid_argument("not an audio sink channel");
  }
}

}  // namespace

AudioCapture::AudioCapture(boost::asio::io_service &ioService,
                           aasdk::messenger::IMessenger::Pointer messenger,
                           aasdk::messenger::ChannelId channelId,
                           std::string path)
    : strand_(ioService),
      channel_(makeChannel(channelId, strand_, std::move(messenger))),
      path_(std::move(path)) {}

void AudioCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "audio channel start: " << streamName();
    channel_->receive(self);
  });
}

void AudioCapture::stop() {
  strand_.dispatch([this, self = shared_from_this()]() {
    writer_.close();
    AURIGA_INFO << "audio capture stopped: " << streamName() << ", " << bytes_
                << " bytes";
  });
}

void AudioCapture::pause() {}
void AudioCapture::resume() {}

const char *AudioCapture::streamName() const {
  switch (channel_->getId()) {
    case aasdk::messenger::ChannelId::MEDIA_SINK_MEDIA_AUDIO:
      return "media";
    case aasdk::messenger::ChannelId::MEDIA_SINK_SYSTEM_AUDIO:
      return "system";
    case aasdk::messenger::ChannelId::MEDIA_SINK_GUIDANCE_AUDIO:
      return "guidance";
    case aasdk::messenger::ChannelId::MEDIA_SINK_TELEPHONY_AUDIO:
      return "telephony";
    default:
      return "audio";
  }
}

void AudioCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *audio = service->mutable_media_sink_service();
  audio->set_available_type(
      aap_protobuf::service::media::shared::message::MediaCodecType::
          MEDIA_CODEC_AUDIO_PCM);
  audio->set_available_while_in_call(true);

  switch (channel_->getId()) {
    case aasdk::messenger::ChannelId::MEDIA_SINK_MEDIA_AUDIO:
      audio->set_audio_type(
          aap_protobuf::service::media::sink::message::AudioStreamType::
              AUDIO_STREAM_MEDIA);
      break;
    case aasdk::messenger::ChannelId::MEDIA_SINK_SYSTEM_AUDIO:
      audio->set_audio_type(
          aap_protobuf::service::media::sink::message::AudioStreamType::
              AUDIO_STREAM_SYSTEM_AUDIO);
      break;
    case aasdk::messenger::ChannelId::MEDIA_SINK_GUIDANCE_AUDIO:
      audio->set_audio_type(
          aap_protobuf::service::media::sink::message::AudioStreamType::
              AUDIO_STREAM_GUIDANCE);
      break;
    case aasdk::messenger::ChannelId::MEDIA_SINK_TELEPHONY_AUDIO:
      audio->set_audio_type(
          aap_protobuf::service::media::sink::message::AudioStreamType::
              AUDIO_STREAM_TELEPHONY);
      break;
    default:
      break;
  }

  auto *config = audio->add_audio_configs();
  config->set_sampling_rate(48000);
  config->set_number_of_bits(16);
  config->set_number_of_channels(2);

  AURIGA_INFO << "advertised audio channel " << streamName() << " ("
              << service->id() << ")";
}

void AudioCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "audio channel open request: " << streamName();

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&AudioCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void AudioCapture::onMediaChannelSetupRequest(
    const aap_protobuf::service::media::shared::message::Setup &request) {
  (void)request;
  AURIGA_INFO << "audio setup request: " << streamName();

  aap_protobuf::service::media::shared::message::Config response;
  response.set_status(
      aap_protobuf::service::media::shared::message::Config::STATUS_READY);
  response.set_max_unacked(1);
  response.add_configuration_indices(0);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&AudioCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelSetupResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void AudioCapture::onMediaChannelStartIndication(
    const aap_protobuf::service::media::shared::message::Start &indication) {
  session_ = indication.session_id();
  if (!writer_.open(path_)) {
    AURIGA_ERROR << "could not open " << path_;
  } else {
    AURIGA_INFO << "audio stream started: " << streamName() << " -> " << path_;
  }
  channel_->receive(shared_from_this());
}

void AudioCapture::onMediaChannelStopIndication(
    const aap_protobuf::service::media::shared::message::Stop &indication) {
  (void)indication;
  session_ = -1;
  writer_.close();
  AURIGA_INFO << "audio stream stopped: " << streamName();
  channel_->receive(shared_from_this());
}

void AudioCapture::onMediaWithTimestampIndication(
    aasdk::messenger::Timestamp::ValueType timestamp,
    const aasdk::common::DataConstBuffer &buffer) {
  (void)timestamp;
  writer_.write(buffer.cdata, buffer.size);
  bytes_ += buffer.size;
  sendAck();
  channel_->receive(shared_from_this());
}

void AudioCapture::onMediaIndication(
    const aasdk::common::DataConstBuffer &buffer) {
  onMediaWithTimestampIndication(0, buffer);
}

void AudioCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "audio channel error (" << streamName()
               << "): " << error.what();
}

void AudioCapture::sendAck() {
  if (session_ < 0) {
    return;
  }

  aap_protobuf::service::media::source::message::Ack indication;
  indication.set_session_id(session_);
  indication.set_ack(1);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&AudioCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendMediaAckIndication(indication, std::move(promise));
}

}  // namespace auriga
