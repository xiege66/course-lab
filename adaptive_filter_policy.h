#pragma once
// Original extension for GateANN commit 71e87cbf. C++17, no ANN dependencies.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string>

namespace fvs_opt {
enum class Mode { off, selectivity, adaptive };
struct Config {
  Mode mode = Mode::off;
  uint32_t min_l = 320, max_l = 5120, target = 32, tunnel_keep = 32;
  double pq_margin = 1.25;
  static uint32_t integer(const char* key, uint32_t fallback) {
    const char* p = std::getenv(key);
    if (!p) return fallback;
    std::string s(p);
    if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
      throw std::invalid_argument(std::string(key) + " must be an integer");
    unsigned long long n = std::stoull(s);
    if (!n || n > 1000000) throw std::invalid_argument(std::string(key) + " outside 1..1000000");
    return static_cast<uint32_t>(n);
  }
  static Config environment() {
    Config c;
    std::string m = std::getenv("FVS_OPT_MODE") ? std::getenv("FVS_OPT_MODE") : "off";
    if (m == "off") return c;
    if (m == "selectivity") c.mode = Mode::selectivity;
    else if (m == "adaptive") c.mode = Mode::adaptive;
    else throw std::invalid_argument("FVS_OPT_MODE must be off/selectivity/adaptive");
    c.min_l = integer("FVS_OPT_MIN_L", c.min_l);
    c.max_l = integer("FVS_OPT_MAX_L", c.max_l);
    c.target = integer("FVS_OPT_TARGET", c.target);
    c.tunnel_keep = integer("FVS_OPT_TUNNEL_KEEP", c.tunnel_keep);
    if (c.min_l > c.max_l) throw std::invalid_argument("MIN_L exceeds MAX_L");
    if (const char* p = std::getenv("FVS_OPT_PQ_MARGIN")) {
      size_t pos = 0;
      c.pq_margin = std::stod(p, &pos);
      if (pos != std::string(p).size() || !std::isfinite(c.pq_margin) || c.pq_margin < 1)
        throw std::invalid_argument("PQ_MARGIN must be finite and >=1");
    }
    return c;
  }
  uint32_t initial(double selectivity, uint64_t k) const {
    if (k == 0 || k > max_l) throw std::invalid_argument("K outside budget bounds");
    double s = std::clamp(selectivity, 1.0 / max_l, 1.0);
    double n = std::ceil(std::max<uint64_t>(target, k) / s);
    return static_cast<uint32_t>(std::clamp(n, double(std::max<uint64_t>(min_l, k)), double(max_l)));
  }
};

// Per-query state. No shared learned state; deterministic under thread scheduling.
struct Budget {
  Config cfg;
  uint64_t k;
  uint32_t limit, expanded = 0, passed = 0, growths = 0;
  bool capped = false, early = false;
  Budget(Config c, double s, uint64_t topk) : cfg(c), k(topk), limit(c.initial(s, topk)) {}
  void observe(bool pass) { ++expanded; passed += pass; }
  bool stop(size_t valid, double frontier_pq, double kth_exact, bool pending) {
    if (expanded >= cfg.max_l) { capped = true; return true; }
    // Heuristic only: PQ error is not bounded. Never stop on it with pending IO.
    if (!pending && valid >= std::max<uint64_t>(cfg.target, k) &&
        std::isfinite(frontier_pq) && std::isfinite(kth_exact) &&
        frontier_pq > kth_exact * cfg.pq_margin) {
      early = true;
      return true;
    }
    if (expanded >= limit) {
      // Observed local pass rate is biased by graph traversal; use only to grow.
      double rate = (passed + 1.0) / (expanded + 2.0);
      double proposed = std::ceil(std::max<uint64_t>(cfg.target, k) / rate);
      uint32_t next = static_cast<uint32_t>(std::min<double>(cfg.max_l, std::max<double>(2.0 * limit, proposed)));
      if (next > limit) { limit = next; ++growths; }
    }
    return false;
  }
};
}  // namespace fvs_opt
