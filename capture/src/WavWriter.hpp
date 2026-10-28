#pragma once

#include <cstdint>
#include <fstream>
#include <string>

namespace auriga {

// Minimal PCM WAV writer. The header is patched on close so the files are
// directly playable with ffmpeg/sox.
class WavWriter {
 public:
  ~WavWriter() { close(); }

  bool open(const std::string &path, uint32_t sampleRate = 48000,
            uint16_t channels = 2, uint16_t bits = 16);
  void write(const uint8_t *data, size_t size);
  void close();
  bool isOpen() const { return file_.is_open(); }

 private:
  void writeLE16(uint16_t value);
  void writeLE32(uint32_t value);

  std::ofstream file_;
  uint32_t dataBytes_ = 0;
  uint32_t sampleRate_ = 48000;
  uint16_t channels_ = 2;
  uint16_t bits_ = 16;
};

}  // namespace auriga
