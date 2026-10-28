#include "VideoCapture.hpp"

#include <functional>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/media/shared/message/Config.pb.h>
#include <aap_protobuf/service/media/shared/message/MediaCodecType.pb.h>
#include <aap_protobuf/service/media/sink/message/VideoCodecResolutionType.pb.h>
#include <aap_protobuf/service/media/sink/message/VideoFrameRateType.pb.h>
#include <aap_protobuf/service/media/source/message/Ack.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

VideoCapture::VideoCapture(boost::asio::io_service &ioService,
                           aasdk::messenger::IMessenger::Pointer messenger,
                           std::string path)
    : strand_(ioService),
      channel_(
          std::make_shared<
              aasdk::channel::mediasink::video::channel::VideoChannel>(
              strand_, std::move(messenger))),
      path_(std::move(path)) {}

void VideoCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    AURIGA_INFO << "video channel start";
    channel_->receive(self);
  });
}

void VideoCapture::stop() {
  strand_.dispatch([this, self = shared_from_this()]() {
    if (file_.is_open()) {
      file_.flush();
      file_.close();
    }
    AURIGA_INFO << "video capture stopped, " << bytes_ << " bytes";
  });
}

void VideoCapture::pause() {}
void VideoCapture::resume() {}

void VideoCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *video = service->mutable_media_sink_service();
  video->set_available_type(
      aap_protobuf::service::media::shared::message::MediaCodecType::
          MEDIA_CODEC_VIDEO_H264_BP);
  video->set_available_while_in_call(true);

  auto *config = video->add_video_configs();
  config->set_codec_resolution(
      aap_protobuf::service::media::sink::message::VideoCodecResolutionType::
          VIDEO_1280x720);
  config->set_frame_rate(
      aap_protobuf::service::media::sink::message::VideoFrameRateType::
          VIDEO_FPS_30);
  config->set_height_margin(0);
  config->set_width_margin(0);
  config->set_density(160);

  AURIGA_INFO << "advertised video channel " << service->id();
}

void VideoCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  AURIGA_INFO << "video channel open request";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&VideoCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void VideoCapture::onMediaChannelSetupRequest(
    const aap_protobuf::service::media::shared::message::Setup &request) {
  (void)request;
  AURIGA_INFO << "video setup request, opening " << path_;
  file_.open(path_, std::ios::binary | std::ios::trunc);

  aap_protobuf::service::media::shared::message::Config response;
  response.set_status(file_.is_open()
                          ? aap_protobuf::service::media::shared::message::
                                Config::STATUS_READY
                          : aap_protobuf::service::media::shared::message::
                                Config::STATUS_WAIT);
  response.set_max_unacked(1);
  response.add_configuration_indices(0);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      [this, self = shared_from_this()]() { sendVideoFocusIndication(); },
      std::bind(&VideoCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelSetupResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void VideoCapture::onMediaChannelStartIndication(
    const aap_protobuf::service::media::shared::message::Start &indication) {
  session_ = indication.session_id();
  AURIGA_INFO << "video stream started, session " << session_;
  channel_->receive(shared_from_this());
}

void VideoCapture::onMediaChannelStopIndication(
    const aap_protobuf::service::media::shared::message::Stop &indication) {
  (void)indication;
  session_ = -1;
  AURIGA_INFO << "video stream stopped";
  channel_->receive(shared_from_this());
}

void VideoCapture::onMediaWithTimestampIndication(
    aasdk::messenger::Timestamp::ValueType timestamp,
    const aasdk::common::DataConstBuffer &buffer) {
  (void)timestamp;
  if (file_.is_open() && buffer.size > 0) {
    file_.write(reinterpret_cast<const char *>(buffer.cdata),
                static_cast<std::streamsize>(buffer.size));
    bytes_ += buffer.size;
  }
  sendAck();
  channel_->receive(shared_from_this());
}

void VideoCapture::onMediaIndication(
    const aasdk::common::DataConstBuffer &buffer) {
  onMediaWithTimestampIndication(0, buffer);
}

void VideoCapture::onVideoFocusRequest(
    const aap_protobuf::service::media::video::message::
        VideoFocusRequestNotification &request) {
  (void)request;
  AURIGA_INFO << "video focus request";
  sendVideoFocusIndication();
  channel_->receive(shared_from_this());
}

void VideoCapture::sendVideoFocusIndication() {
  aap_protobuf::service::media::video::message::VideoFocusNotification
      indication;
  indication.set_focus(aap_protobuf::service::media::video::message::
                           VideoFocusMode::VIDEO_FOCUS_PROJECTED);
  indication.set_unsolicited(false);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&VideoCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendVideoFocusIndication(indication, std::move(promise));
}

void VideoCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "video channel error: " << error.what();
}

void VideoCapture::sendAck() {
  if (session_ < 0) {
    return;
  }

  aap_protobuf::service::media::source::message::Ack indication;
  indication.set_session_id(session_);
  indication.set_ack(1);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&VideoCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendMediaAckIndication(indication, std::move(promise));
}

}  // namespace auriga
