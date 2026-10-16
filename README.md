# GateShield

A small packet-header policy engine for studying comparator sharing, policy correctness, and area/latency tradeoffs.

## Current milestone

Implemented: policy specification, independent Python model, parallel matching core, and registered parallel engine with programmable rule storage, request capture, response backpressure, and configuration exclusion. Python-generated vectors drive both the core testbench and a transaction scoreboard for the engine.

Next: sequential matcher, formal harness, and library-mapped area/timing study. The current Yosys script only checks generic synthesizability. Packet parsing and forwarding integration remain outside this project.

Run from this directory with Python 3.10 or newer:

```text
python -m unittest discover -s tests -v
python scripts/check_rtl.py
python scripts/check_engine.py
python scripts/check_synthesis.py
```

The simulation commands require `iverilog` and `vvp` on PATH. The synthesis command requires `yosys`. Intermediate files go under the ignored `build/` directory. Missing tools produce an explicit failure, never a passing RTL result. Both simulation scripts accept `--generate-only` for generating vectors without running hardware simulation.

GitHub Actions runs Python tests, Icarus core and registered-engine simulations, and generic Yosys synthesis checks on pushes and pull requests. A workflow definition alone is not evidence that the RTL has passed: check the completed run for the commit being reviewed.

The original core passed 52,544 differential cases in CI. The engine suite targets 1, 4, 8, and 16 rules with directed and seeded mixed-cycle traffic. It checks policy decisions against the independent Python evaluator and accounts for accepted, completed, and reset-canceled transactions. The checker also verifies handshakes, response production, and payload stability during receiver stalls. These are simulation checks, not formal proofs.

## Engine interface and timing

`rtl/gateshield_parallel.v` implements one outstanding request. Request acceptance captures the header; the next rising edge registers the decision. With no stalls or configuration changes, response consumption occurs on the following edge and the next request is accepted one edge later: initiation interval is three cycles. The combinational core's parallelism does not imply one request per cycle through this wrapper.

Assert `cfg_mode` and hold it until `cfg_active` is observed. This stops new requests immediately while existing work drains. Write one whole packed rule when `cfg_valid && cfg_ready`. An index outside the table is rejected. Deassert `cfg_mode` to leave configuration; requests can resume after the next rising edge. Reset clears rules and cancels pending work.

Read `docs/specification.md` before changing behavior and `docs/roadmap.md` for the remaining milestones.

## Research discipline

Comparator sharing and first-match filtering are established techniques. This project does not yet claim novelty, area savings, timing performance, or power savings. Compare architectures with identical programmable policies, storage, interfaces, and synthesis constraints. Keep worst-case latency separate from average latency.
