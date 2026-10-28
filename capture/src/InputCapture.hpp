#pragma once

#include <fstream>
#include <memory>
#include <string>

#include <aasdk/Channel/InputSource/InputSourceService.hpp>

#include "CaptureService.hpp"

namespace auriga {

class InputCapture
    : public CaptureService,
      public aasdk::channel::inputsource::IInputSourceServiceEventHandler,
      public std::enable_shared_from_this<InputCapture> {
 public:
  InputCapture(boost::asio::io_service &ioService,
               aasdk::messenger::IMessenger::Pointer messenger,
               std::string logPath);

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
  void onKeyBindingRequest(
      const aap_protobuf::service::media::sink::message::KeyBindingRequest
          &request) override;
  void onChannelError(const aasdk::error::Error &error) override;

  // Coordinates are in the advertised 1280x720 touchscreen space.
  void down(uint32_t x, uint32_t y);
  void move(uint32_t x, uint32_t y);
  void up(uint32_t x, uint32_t y);
  void tap(uint32_t x, uint32_t y);

 private:
  using std::enable_shared_from_this<InputCapture>::shared_from_this;

  void sendTouch(uint32_t x, uint32_t y,
                 aap_protobuf::service::inputsource::message::PointerAction
                     action);

  boost::asio::io_service::strand strand_;
  std::shared_ptr<aasdk::channel::inputsource::InputSourceService> channel_;
  std::string logPath_;
  std::ofstream log_;
  bool open_ = false;
};

}  // namespace auriga
