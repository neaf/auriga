#pragma once

#include <iostream>
#include <mutex>
#include <sstream>

namespace auriga {

inline std::mutex &logMutex() {
  static std::mutex mutex;
  return mutex;
}

class LogLine {
 public:
  explicit LogLine(const char *level) : lock_(logMutex()) {
    std::cerr << "[" << level << "] ";
  }

  template <typename T>
  LogLine &operator<<(const T &value) {
    std::cerr << value;
    return *this;
  }

  ~LogLine() { std::cerr << std::endl; }

 private:
  std::unique_lock<std::mutex> lock_;
};

}  // namespace auriga

#define AURIGA_INFO ::auriga::LogLine("info")
#define AURIGA_WARN ::auriga::LogLine("warn")
#define AURIGA_ERROR ::auriga::LogLine("error")
