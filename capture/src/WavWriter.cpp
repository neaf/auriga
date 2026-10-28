#include "WavWriter.hpp"

namespace auriga {

void WavWriter::writeLE16(uint16_t value) {
  const uint8_t bytes[2] = {static_cast<uint8_t>(value & 0xFF),
                            static_cast<uint8_t>((value >> 8) & 0xFF)};
  file_.write(reinterpret_cast<const char *>(bytes), sizeof(bytes));
}

void WavWriter::writeLE32(uint32_t value) {
  const uint8_t bytes[4] = {static_cast<uint8_t>(value & 0xFF),
                            static_cast<uint8_t>((value >> 8) & 0xFF),
                            static_cast<uint8_t>((value >> 16) & 0xFF),
                            static_cast<uint8_t>((value >> 24) & 0xFF)};
  file_.write(reinterpret_cast<const char *>(bytes), sizeof(bytes));
}

bool WavWriter::open(const std::string &path, uint32_t sampleRate,
                     uint16_t channels, uint16_t bits) {
  close();
  file_.open(path, std::ios::binary | std::ios::trunc);
  if (!file_.is_open()) {
    return false;
  }

  sampleRate_ = sampleRate;
  channels_ = channels;
  bits_ = bits;
  dataBytes_ = 0;

  const uint16_t blockAlign =
      static_cast<uint16_t>(channels_ * (bits_ / 8));
  const uint32_t byteRate = sampleRate_ * blockAlign;

  file_.write("RIFF", 4);
  writeLE32(36);  // patched in close()
  file_.write("WAVE", 4);
  file_.write("fmt ", 4);
  writeLE32(16);
  writeLE16(1);  // PCM
  writeLE16(channels_);
  writeLE32(sampleRate_);
  writeLE32(byteRate);
  writeLE16(blockAlign);
  writeLE16(bits_);
  file_.write("data", 4);
  writeLE32(0);  // patched in close()
  return true;
}

void WavWriter::write(const uint8_t *data, size_t size) {
  if (!file_.is_open() || data == nullptr || size == 0) {
    return;
  }
  file_.write(reinterpret_cast<const char *>(data),
              static_cast<std::streamsize>(size));
  dataBytes_ += static_cast<uint32_t>(size);
}

void WavWriter::close() {
  if (!file_.is_open()) {
    return;
  }

  file_.seekp(4);
  writeLE32(36 + dataBytes_);
  file_.seekp(40);
  writeLE32(dataBytes_);
  file_.close();
}

}  // namespace auriga
