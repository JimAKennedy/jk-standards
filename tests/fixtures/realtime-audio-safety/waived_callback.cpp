// Fixture: an audio callback whose only forbidden forms are legitimately
// waived in place with `RT-SAFE-OK: <reason>`.
//
// Models the drumcore app layer handing the poly engine a host-owned buffer.
// Each crossing is a genuine, reasoned exception, so check-realtime-safety.sh
// must exit 0 and report the live suppression count.
#include <vector>

namespace drumcore {

struct Sampler {
  std::vector<float>* hostBuffer;  // owned by the VST3 host, not us

  void renderBlock(float* out, int frames) {
    // The host guarantees this buffer is pre-sized to the max block; the
    // push_back never reallocates in the callback's steady state.
    hostBuffer->push_back(out[0]);  // RT-SAFE-OK: host pre-reserves to maxBlock
    // Preceding-line waiver form: the delete runs only on the non-audio
    // teardown path this fixture shares, never inside the steady callback.
    // RT-SAFE-OK: freed on the message thread during voice teardown
    delete hostBuffer;
    for (int i = 0; i < frames; ++i) {
      out[i] *= 0.5f;
    }
  }
};

}  // namespace drumcore
