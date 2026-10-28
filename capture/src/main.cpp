#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <boost/asio.hpp>

#include <aasdk/Messenger/Cryptor.hpp>
#include <aasdk/Messenger/MessageInStream.hpp>
#include <aasdk/Messenger/MessageOutStream.hpp>
#include <aasdk/Messenger/Messenger.hpp>
#include <aasdk/Transport/SSLWrapper.hpp>
#include <aasdk/Transport/USBTransport.hpp>
#include <aasdk/USB/AOAPDevice.hpp>
#include <aasdk/USB/USBWrapper.hpp>

#include "AudioCapture.hpp"
#include "BluetoothCapture.hpp"
#include "HeadUnit.hpp"
#include "InputCapture.hpp"
#include "Log.hpp"
#include "MicrophoneCapture.hpp"
#include "SensorCapture.hpp"
#include "WifiProjectionCapture.hpp"
#include "Usb.hpp"
#include "VideoCapture.hpp"

namespace {

// The dongle's own Bluetooth address, advertised to the phone as the car
// address.  It has been stable across power cycles.
constexpr const char *kDongleBluetoothAddress = "ED:A2:A4:94:4F:B8";

struct Options {
  std::string outputDir = "captures";
  int durationSeconds = 0;
  bool input = true;
};

Options parseOptions(int argc, char **argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--out" && i + 1 < argc) {
      options.outputDir = argv[++i];
    } else if (arg == "--duration" && i + 1 < argc) {
      options.durationSeconds = std::stoi(argv[++i]);
    } else if (arg == "--no-input") {
      options.input = false;
    } else if (arg == "--help") {
      std::cout << "usage: " << argv[0]
                << " [--out DIR] [--duration SECONDS] [--no-input]\n"
                   "stdin commands: tap X Y | down X Y | move X Y | up X Y | quit\n";
      std::exit(0);
    }
  }
  return options;
}

}  // namespace

int main(int argc, char **argv) {
  const Options options = parseOptions(argc, argv);
  std::filesystem::create_directories(options.outputDir);

  try {
    auriga::UsbContext usbContext;
    boost::asio::io_service ioService;
    boost::asio::io_service::work work(ioService);
    aasdk::usb::USBWrapper usbWrapper(usbContext.get());

    // The dongle can cycle out of AOA between the probe and this process, so
    // keep retrying the switch/open instead of giving up after one miss.
    aasdk::usb::IAOAPDevice::Pointer aoapDevice;
    for (int attempt = 0; attempt < 240 && !aoapDevice; ++attempt) {
      auto handle = usbWrapper.openDeviceWithVidPid(0x18D1, 0x2D00);
      if (handle) {
        try {
          aoapDevice = aasdk::usb::AOAPDevice::create(usbWrapper, ioService,
                                                      handle);
          AURIGA_INFO << "opened AOA accessory";
        } catch (const std::exception &error) {
          AURIGA_WARN << "AOAPDevice::create failed: " << error.what();
        }
      } else {
        if (attempt % 4 == 0) {
          AURIGA_INFO << "waiting for AOA, switching...";
        }
        auriga::switchDongleToAoa(usbContext.get());
      }
      if (!aoapDevice) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
      }
    }
    if (!aoapDevice) {
      throw std::runtime_error("timed out waiting for AOA device");
    }

    auto transport =
        std::make_shared<aasdk::transport::USBTransport>(ioService, aoapDevice);
    auto sslWrapper = std::make_shared<aasdk::transport::SSLWrapper>();
    auto cryptor = std::make_shared<aasdk::messenger::Cryptor>(sslWrapper);
    cryptor->init();

    auto messageInStream =
        std::make_shared<aasdk::messenger::MessageInStream>(
            ioService, transport, cryptor);
    auto messageOutStream =
        std::make_shared<aasdk::messenger::MessageOutStream>(
            ioService, transport, cryptor);
    auto messenger = std::make_shared<aasdk::messenger::Messenger>(
        ioService, messageInStream, messageOutStream);

    std::vector<auriga::CaptureService::Pointer> services;

    auto video = std::make_shared<auriga::VideoCapture>(
        ioService, messenger, options.outputDir + "/video.h264");
    services.push_back(video);

    const auto audioChannels = {
        aasdk::messenger::ChannelId::MEDIA_SINK_MEDIA_AUDIO,
        aasdk::messenger::ChannelId::MEDIA_SINK_SYSTEM_AUDIO,
        aasdk::messenger::ChannelId::MEDIA_SINK_GUIDANCE_AUDIO,
        aasdk::messenger::ChannelId::MEDIA_SINK_TELEPHONY_AUDIO,
    };
    for (const auto channel : audioChannels) {
      std::string name;
      switch (channel) {
        case aasdk::messenger::ChannelId::MEDIA_SINK_MEDIA_AUDIO:
          name = "media";
          break;
        case aasdk::messenger::ChannelId::MEDIA_SINK_SYSTEM_AUDIO:
          name = "system";
          break;
        case aasdk::messenger::ChannelId::MEDIA_SINK_GUIDANCE_AUDIO:
          name = "guidance";
          break;
        case aasdk::messenger::ChannelId::MEDIA_SINK_TELEPHONY_AUDIO:
          name = "telephony";
          break;
        default:
          name = "audio";
          break;
      }
      services.push_back(std::make_shared<auriga::AudioCapture>(
          ioService, messenger, channel,
          options.outputDir + "/audio-" + name + ".wav"));
    }

    auto bluetooth = std::make_shared<auriga::BluetoothCapture>(
        ioService, messenger, kDongleBluetoothAddress);
    services.push_back(bluetooth);

    auto microphone =
        std::make_shared<auriga::MicrophoneCapture>(ioService, messenger);
    services.push_back(microphone);

    auto sensor = std::make_shared<auriga::SensorCapture>(ioService, messenger);
    services.push_back(sensor);

    auto wifiProjection = std::make_shared<auriga::WifiProjectionCapture>(
        ioService, messenger, "e8:5c:b1:b5:c6:41");
    services.push_back(wifiProjection);

    std::shared_ptr<auriga::InputCapture> input;
    if (options.input) {
      input = std::make_shared<auriga::InputCapture>(
          ioService, messenger, options.outputDir + "/input.jsonl");
      services.push_back(input);
    }

    auto headUnit = std::make_shared<auriga::HeadUnit>(
        ioService, cryptor, transport, messenger, services);

    headUnit->start([&ioService]() { ioService.stop(); });

    boost::asio::signal_set signals(ioService, SIGINT, SIGTERM);
    signals.async_wait(
        [&ioService](const boost::system::error_code &error, int) {
          if (!error) {
            AURIGA_INFO << "signal received, stopping";
            ioService.stop();
          }
        });

    boost::asio::deadline_timer timer(ioService);
    if (options.durationSeconds > 0) {
      timer.expires_from_now(
          boost::posix_time::seconds(options.durationSeconds));
      timer.async_wait([&ioService](const boost::system::error_code &error) {
        if (!error) {
          AURIGA_INFO << "duration reached, stopping";
          ioService.stop();
        }
      });
    }

    std::vector<std::thread> threads;
    for (int i = 0; i < 4; ++i) {
      threads.emplace_back([&ioService, context = usbContext.get()]() {
        timeval timeout{0, 100000};
        while (!ioService.stopped()) {
          libusb_handle_events_timeout_completed(context, &timeout, nullptr);
        }
      });
    }
    for (int i = 0; i < 3; ++i) {
      threads.emplace_back([&ioService]() { ioService.run(); });
    }

    if (input) {
      std::thread([input]() {
        std::string line;
        while (std::getline(std::cin, line)) {
          std::istringstream stream(line);
          std::string command;
          uint32_t x = 0;
          uint32_t y = 0;
          stream >> command;
          if (command == "tap" && stream >> x >> y) {
            input->tap(x, y);
          } else if (command == "down" && stream >> x >> y) {
            input->down(x, y);
          } else if (command == "move" && stream >> x >> y) {
            input->move(x, y);
          } else if (command == "up" && stream >> x >> y) {
            input->up(x, y);
          } else if (command == "quit") {
            break;
          }
        }
      }).detach();
    }

    ioService.run();
    for (auto &thread : threads) {
      if (thread.joinable()) {
        thread.join();
      }
    }

    AURIGA_INFO << "captures written to " << options.outputDir;
    return 0;
  } catch (const std::exception &error) {
    AURIGA_ERROR << "fatal: " << error.what();
    return 1;
  }
}
