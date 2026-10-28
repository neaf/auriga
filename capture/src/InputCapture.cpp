#include "InputCapture.hpp"

#include <chrono>
#include <functional>
#include <thread>

#include <aap_protobuf/service/Service.pb.h>
#include <aap_protobuf/service/control/message/ChannelOpenResponse.pb.h>
#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>
#include <aap_protobuf/service/inputsource/message/InputReport.pb.h>
#include <aap_protobuf/service/inputsource/message/PointerAction.pb.h>
#include <aap_protobuf/service/media/sink/message/KeyBindingResponse.pb.h>
#include <aap_protobuf/shared/MessageStatus.pb.h>

#include "Log.hpp"

namespace auriga {

InputCapture::InputCapture(boost::asio::io_service &ioService,
                           aasdk::messenger::IMessenger::Pointer messenger,
                           std::string logPath)
    : strand_(ioService),
      channel_(std::make_shared<
               aasdk::channel::inputsource::InputSourceService>(
          strand_, std::move(messenger))),
      logPath_(std::move(logPath)) {}

void InputCapture::start() {
  strand_.dispatch([this, self = shared_from_this()]() {
    log_.open(logPath_, std::ios::out | std::ios::trunc);
    AURIGA_INFO << "input channel start, log " << logPath_;
    channel_->receive(self);
  });
}

void InputCapture::stop() {
  strand_.dispatch([this, self = shared_from_this()]() {
    if (log_.is_open()) {
      log_.flush();
      log_.close();
    }
  });
}

void InputCapture::pause() {}
void InputCapture::resume() {}

void InputCapture::fillFeatures(
    aap_protobuf::service::control::message::ServiceDiscoveryResponse
        &response) {
  auto *service = response.add_channels();
  service->set_id(static_cast<uint32_t>(channel_->getId()));

  auto *input = service->mutable_input_source_service();
  auto *touchscreen = input->add_touchscreen();
  touchscreen->set_width(1280);
  touchscreen->set_height(720);

  AURIGA_INFO << "advertised input channel " << service->id();
}

void InputCapture::onChannelOpenRequest(
    const aap_protobuf::service::control::message::ChannelOpenRequest &request) {
  (void)request;
  open_ = true;
  AURIGA_INFO << "input channel open";

  aap_protobuf::service::control::message::ChannelOpenResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&InputCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendChannelOpenResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void InputCapture::onKeyBindingRequest(
    const aap_protobuf::service::media::sink::message::KeyBindingRequest
        &request) {
  (void)request;
  AURIGA_INFO << "key binding request";

  aap_protobuf::service::media::sink::message::KeyBindingResponse response;
  response.set_status(aap_protobuf::shared::MessageStatus::STATUS_SUCCESS);

  auto promise = aasdk::channel::SendPromise::defer(strand_);
  promise->then(
      []() {},
      std::bind(&InputCapture::onChannelError, shared_from_this(),
                std::placeholders::_1));
  channel_->sendKeyBindingResponse(response, std::move(promise));
  channel_->receive(shared_from_this());
}

void InputCapture::onChannelError(const aasdk::error::Error &error) {
  if (error.getCode() == aasdk::error::ErrorCode::OPERATION_ABORTED) {
    return;
  }
  AURIGA_ERROR << "input channel error: " << error.what();
}

void InputCapture::down(uint32_t x, uint32_t y) {
  sendTouch(x, y,
            aap_protobuf::service::inputsource::message::PointerAction::
                ACTION_DOWN);
}

void InputCapture::move(uint32_t x, uint32_t y) {
  sendTouch(x, y,
            aap_protobuf::service::inputsource::message::PointerAction::
                ACTION_MOVED);
}

void InputCapture::up(uint32_t x, uint32_t y) {
  sendTouch(x, y,
            aap_protobuf::service::inputsource::message::PointerAction::
                ACTION_UP);
}

void InputCapture::tap(uint32_t x, uint32_t y) {
  down(x, y);
  std::this_thread::sleep_for(std::chrono::milliseconds(80));
  up(x, y);
}

void InputCapture::sendTouch(
    uint32_t x, uint32_t y,
    aap_protobuf::service::inputsource::message::PointerAction action) {
  strand_.dispatch([this, self = shared_from_this(), x, y, action]() {
    if (!open_) {
      AURIGA_WARN << "touch ignored: input channel not open";
      return;
    }

    const auto timestamp =
        std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count();

    aap_protobuf::service::inputsource::message::InputReport report;
    report.set_timestamp(timestamp);
    auto *touch = report.mutable_touch_event();
    touch->set_action(action);
    touch->set_action_index(0);
    auto *pointer = touch->add_pointer_data();
    pointer->set_x(x);
    pointer->set_y(y);
    pointer->set_pointer_id(0);

    if (log_.is_open()) {
      log_ << "{\"t\":" << timestamp << ",\"action\":" << action
           << ",\"x\":" << x << ",\"y\":" << y << "}\n";
    }

    auto promise = aasdk::channel::SendPromise::defer(strand_);
    promise->then(
        []() {},
        std::bind(&InputCapture::onChannelError, shared_from_this(),
                  std::placeholders::_1));
    channel_->sendInputReport(report, std::move(promise));
  });
}

}  // namespace auriga
