// Fixture: an audio callback with unwaived real-time-safety violations.
//
// Models the poly engine's per-block render entry point (engine/src/voice.cpp
// in the reusable JUCE-style audio engine) as consumed by the drumcore app.
// Every forbidden operation below runs on the audio thread with no waiver, so
// check-realtime-safety.sh must flag each one and exit 1.
#include <mutex>
#include <vector>
#include <cstdio>

namespace poly {

struct Voice {
  std::mutex mutex;
  std::vector<float> scratch;

  // Called from the audio driver's callback — hard-real-time context.
  void renderBlock(float* out, int frames) {
    std::lock_guard<std::mutex> guard(mutex);   // mutex on the audio thread
    float* tmp = new float[frames];             // heap allocation per block
    for (int i = 0; i < frames; ++i) {
      scratch.push_back(out[i]);                // unbounded container growth
      tmp[i] = out[i] * 0.5f;
    }
    printf("rendered %d frames\n", frames);      // syscall / blocking I/O
    delete[] tmp;                                // heap free
  }
};

}  // namespace poly
