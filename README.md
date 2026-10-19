# GateShield

A small packet-header policy engine for studying comparator sharing, policy correctness, and area/latency tradeoffs.

## Current milestone

Implemented: policy specification, independent Python model, parallel matching core, and registered parallel and sequential engines with programmable rule storage, request capture, response backpressure, and configuration exclusion. Python-generated vectors drive the core testbench and transaction scoreboards. A common corpus checks that both engines return identical ordered decisions despite different latencies.

Next: formal harness and library-mapped area/timing study. The Yosys comparison currently measures generic bit-level cell counts, not standard-cell area. Packet parsing and forwarding integration remain outside this project.

Run from this directory with Python 3.10 or newer:

```text
python -m unittest discover -s tests -v
python scripts/check_rtl.py
python scripts/check_engine.py
python scripts/check_synthesis.py
```

The simulation commands require `iverilog` and `vvp` on PATH. The synthesis command requires `yosys`. Intermediate files go under the ignored `build/` directory. Missing tools produce an explicit failure, never a passing RTL result. Both simulation scripts accept `--generate-only` for generating vectors without running hardware simulation.

GitHub Actions runs Python tests, Icarus core and both registered-engine simulations, cross-architecture decision replay, and generic Yosys synthesis checks on pushes and pull requests. It uploads CSV reports, synthesis statistics, and logs as `gateshield-comparison-reports`. A workflow definition alone is not evidence that the RTL has passed: check the completed run for the commit being reviewed.

The original core passed 52,544 differential cases in CI. The engine suite targets 1, 4, 8, and 16 rules with directed and seeded mixed-cycle traffic. It checks policy decisions against the independent Python evaluator and accounts for accepted, completed, and reset-canceled transactions. The checker also verifies handshakes, response production, and payload stability during receiver stalls. Both engines replay the same completed-transaction corpus; later arbitrary-cycle fuzz can produce different acceptance streams because their readiness differs. These are simulation checks, not formal proofs.

## Engine interface and timing

Both engines implement one outstanding request. The parallel engine (`rtl/gateshield_parallel.v`) registers the decision on the rising edge after acceptance. With no stalls or configuration changes, its initiation interval is three cycles. The sequential engine (`rtl/gateshield_sequential.v`) checks one rule each cycle and stops at the first match. Its production latency is k+1 cycles for a match at zero-based index k, or N_RULES cycles for no match. Its unstalled initiation interval is latency+2. Unsupported protocols take the full no-match scan. These are clock counts, not frequency measurements.

Assert `cfg_mode` and hold it until `cfg_active` is observed. This stops new requests immediately while existing work drains. Write one whole packed rule when `cfg_valid && cfg_ready`. An index outside the table is rejected. Deassert `cfg_mode` to leave configuration; requests can resume after the next rising edge. Reset clears rules and cancels pending work.

## Comparison reports

- `build/latency_comparison.csv`: observed response production cycles for the common synthetic replay corpus. Receiver stalls are excluded from production latency. Workload averages do not represent real network traffic.
- `build/generic_synthesis_comparison.csv`: flattened, pre-ABC Yosys generic cell counts and register-bit counts, with tool version. Both designs use the same rule storage format and flow. Generic cells have different implementation costs; percentages are not standard-cell area savings.

Rule-selection multiplexers and the scan counter count toward the sequential implementation. Policy storage counts toward both. Response timing depends on scan depth; this prototype makes no policy-confidentiality or constant-time claim.

Read `docs/specification.md` before changing behavior and `docs/roadmap.md` for the remaining milestones.

## Research discipline

Comparator sharing and first-match filtering are established techniques. This project does not yet claim novelty, area savings, timing performance, or power savings. Compare architectures with identical programmable policies, storage, interfaces, and synthesis constraints. Keep worst-case latency separate from average latency.
