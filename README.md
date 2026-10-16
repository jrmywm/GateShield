# GateShield

A small packet-header policy engine for studying comparator sharing, policy correctness, and area/latency tradeoffs.

## Current milestone

Implemented: policy specification, independent Python model, directed and seeded randomized model tests, parallel combinational RTL matching core, and an Icarus testbench driven by Python-generated vectors.

Not implemented yet: registered request/response interface, configuration controller, sequential matcher, formal harness, synthesis and timing scripts. The combinational core is not a complete firewall or a deployable enforcement engine.

Run from this directory with Python 3.10 or newer:

```text
python -m unittest discover -s tests -v
python scripts/check_rtl.py
```

The second command requires `iverilog` and `vvp` on PATH and generates its intermediate files under the ignored `build/` directory. Missing tools produce an explicit failure, never a passing RTL result. To generate reference vectors without simulating RTL, use `python scripts/check_rtl.py --generate-only`.

GitHub Actions runs both the Python tests and the Icarus differential tests on pushes and pull requests. A workflow definition alone is not evidence that the RTL has passed: check the completed run.

Initial local validation: 9 Python tests passed and 52,544 reference vectors were generated across 1, 4, 8, and 16 rules. RTL simulation was not run locally because Icarus was unavailable on PATH.

Read `docs/specification.md` before changing behavior and `docs/roadmap.md` for the remaining milestones.

## Research discipline

Comparator sharing and first-match filtering are established techniques. This project does not yet claim novelty, area savings, timing performance, or power savings. Compare architectures with identical programmable policies, storage, interfaces, and synthesis constraints. Keep worst-case latency separate from average latency.
