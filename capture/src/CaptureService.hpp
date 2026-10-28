#pragma once

#include <memory>

#include <aap_protobuf/service/control/message/ServiceDiscoveryResponse.pb.h>

namespace auriga {

class CaptureService {
 public:
  using Pointer = std::shared_ptr<CaptureService>;

  virtual ~CaptureService() = default;

  virtual void start() = 0;
  virtual void stop() = 0;
  virtual void pause() = 0;
  virtual void resume() = 0;
  virtual void fillFeatures(
      aap_protobuf::service::control::message::ServiceDiscoveryResponse &response) = 0;
};

}  // namespace auriga
