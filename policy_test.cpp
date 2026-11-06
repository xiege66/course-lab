#include "adaptive_filter_policy.h"
#include <cassert>
#include <iostream>

int main() {
  fvs_opt::Config c;
  c.mode = fvs_opt::Mode::adaptive;
  assert(c.initial(.12323, 10) == 320);
  assert(c.initial(.00545, 10) == 5120);
  assert(c.initial(0, 10) == 5120);
  assert(c.initial(1, 10) == 320);
  fvs_opt::Budget b(c, 1, 10);
  for (int i = 0; i < 320; ++i) b.observe(false);
  assert(!b.stop(0, 100, 1, false));
  assert(b.limit > 320 && b.limit <= 5120 && b.growths == 1);
  assert(!b.stop(32, 100, 1, true));  // outstanding IO blocks heuristic stop
  assert(!b.stop(9, 100, 1, false));  // fewer than K must not stop
  assert(b.stop(32, 100, 1, false) && b.early);
  fvs_opt::Budget capped(c, 0, 10);
  for (int i = 0; i < 5120; ++i) capped.observe(false);
  assert(capped.stop(0, 0, 1, true) && capped.capped);
  c.max_l = 100;
  bool threw = false;
  try { c.initial(.1, 101); } catch (const std::invalid_argument&) { threw = true; }
  assert(threw);
  std::cout << "policy tests passed\n";
}
