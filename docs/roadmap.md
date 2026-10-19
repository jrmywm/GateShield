# Implementation roadmap

1. Policy foundation: implemented; core differential simulation passed in CI.
2. Registered parallel implementation: implemented with rule storage, configuration exclusion, request capture, response backpressure, and transaction tests. Check the current commit's CI for simulation and generic synthesis results.
3. Sequential implementation: implemented with one comparator group, first-match termination, identical policy and external interface. Common-corpus completed decisions and production latencies are checked; review the current commit's CI results.
4. Verification: randomized traffic, reset during processing, stalled responses, attempted invalid writes, overlapping rules. Add formal safety and bounded-progress properties with stated assumptions; cover accepted requests and responses to avoid vacuous proofs.
5. Implementation study: generic synthesis comparison and synthetic-corpus latency CSVs implemented. Next: 4/8/16 rules using one cell library, identical constraints, and common feasible clock. Report mapped area, critical paths, cycles, initiation interval, best/worst/average latency. Separate input-dependent response production from arbitrary downstream stalls. Generic-cell counts do not establish physical area savings.
6. Submission: explain established techniques, actual contributions, limitations, and reproducible evidence. Optional two-comparator variant only after all required checks pass.

Target: 10–14 working days, approximately 60–90 focused hours. Preserve two days for writing and reproduction. Drop switching analysis and intermediate architectures before sacrificing correctness checks.

## Tool gate

Python tests require no third-party packages. RTL simulation needs Icarus Verilog (`iverilog`, `vvp`). Generic synthesis smoke checks need Yosys. Mapping additionally needs a characterized cell library; timing needs OpenSTA. CI installs Icarus and Yosys on Ubuntu. Formal work may use SymbiYosys and an appropriate solver. No FPGA vendor suite is required.

## First decisions to understand personally

- Why does explicit deny differ from no match?
- Why does the lowest-index rule win even if a later rule allows?
- Why must a request capture its header?
- Why is a slower matcher not automatically more energy efficient?
- How do storage and selection overhead limit comparator sharing?
