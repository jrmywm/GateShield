# Findings: sequential-engine overhead, library mapping, constrained timing

Status of every number below: measured by the scripts in `scripts/` on the date and
tool versions in the CSV files under `docs/data/`. Inferences are labelled as such.

## 1. The unexpected overhead

**Observation (v0.3 RTL, generic Yosys cells, `docs/data/generic_synthesis_baseline_v0.3.csv`).**
The sequential engine, which instantiates one comparator group instead of N, was
*larger* than the parallel engine for 4, 8 and 16 rules (16 rules: 25,456 vs 20,298).
The cell-type breakdown showed the expected saving in `$_AND_`/`$_XOR_` (shared
comparators) swamped by +9,849 `$_MUX_` cells.

**Cause.** Two statements used a variable-offset part-select on the flattened rule table:

| Statement | Where | Effect |
|---|---|---|
| `rule_table[scan_index*108 +: 108]` (read) | sequential only | barrel shifter over the whole table |
| `rule_table[cfg_index*108 +: 108] <= ...` (write) | **both** engines | barrel shifter over the whole table |

Isolated experiments at 16 rules (generic cells): read `+:` form 9,948 cells vs 1,756
for an explicit select; write `+:` form 15,020 vs 1,788 for a per-rule enable decode.
The same index arithmetic is cheap in an expression with constant offsets, expensive
when the offset is a runtime value, because the synthesizer must be able to place the
108-bit window anywhere in the 108*N-bit vector.

**Why this misled the original comparison.** The write shifter was in both engines
(about 13k of the parallel engine's 20.3k cells), so the v0.3 result compared two
designs that were each mostly shifter. The sequential engine additionally paid the read shifter.

**Fix (RTL).** Constant-slice loops: a `for` over rules with `if (cfg_index == k)` on
the write, and an `always @*` one-hot select on the read. Behavior is unchanged:
all Icarus suites pass, and the 16-rule sequential run takes exactly the same number of
cycles as before (15,761).

| Rules | Parallel before → after | Sequential before → after | Seq/Par after |
|---|---|---|---|
| 4 | 6,468 → 1,864 | 8,007 → 1,382 | 0.74 |
| 8 | 11,213 → 3,582 | 13,955 → 2,267 | 0.63 |
| 16 | 20,298 → 7,554 | 25,456 → 4,058 | 0.54 |

## 2. Standard-cell mapping and constrained timing

**Flow** (`scripts/check_mapping.py`): Yosys 0.33 `synth -flatten`, `dfflibmap`, `abc -liberty -D <target> -constr`,
then OpenSTA 3.1.0. Library: sky130_fd_sc_hd, tt_025C_1v80 (bundled in OpenSTA `examples/`);
probe and lpflow cells excluded (the exclusion list ORFS uses). Yosys 0.33 `abc` has no `-dont_use`,
so the script prunes those cells from a copy of the library.

**Constraints, identical for every design.** Ideal clock; 0.10 ns uncertainty; input and
output delay 20% of the period; driving cell `buf_2`; 10 fF output load. Each path class
(reg→reg, in→reg, reg→out, in→out) is analysed separately and converted to the minimum
period it permits, because the I/O budgets scale with the period. Mapping targets 10 ns
and 3 ns; every design is then evaluated at one common 5.0 ns clock.

**Results, 3 ns mapping target** (`docs/data/mapped_comparison_sky130hd_tt.csv`):

| Rules | Area par / seq (µm²) | Seq area saving | Tmin par / seq (ns) | Slack at 5 ns par / seq |
|---|---|---|---|---|
| 4 | 21,424 / 20,161 | 5.9% | 3.93 / 3.48 | +1.07 / +1.52 |
| 8 | 40,993 / 37,913 | 7.5% | 4.20 / 3.74 | +0.80 / +1.26 |
| 16 | 79,648 / 73,862 | 7.3% | 4.94 / 4.35 | +0.06 / +0.65 |

Designs mapped at a relaxed 10 ns target miss 5 ns at 16 rules (parallel −0.57, sequential −0.24),
so the common clock is only feasible for the more aggressively mapped netlists. No design met the 3 ns
mapping target itself: it is a best-effort ABC goal, not a closure result.

Reg→reg is the limiting class in all 12 runs. In→out paths (e.g. `rst`/`cfg_mode` → `req_ready`,
which the spec requires to be combinational) allow about 1.4–1.6 ns and do not limit.
Hold slack is about +0.33 ns with an ideal clock; that says nothing about a real clock tree.

**Throughput and efficiency (same data plus `docs/data/latency_v0.4.csv`).**

| Rules | Worst-case decision par / seq (ns) | Ratio | Corpus-average decision par / seq (ns) | Area × worst time (k µm²·ns) par / seq |
|---|---|---|---|---|
| 4 | 11.8 / 20.9 | 1.8× | 11.8 / 20.2 | 253 / 421 |
| 8 | 12.6 / 37.4 | 3.0× | 12.6 / 34.3 | 516 / 1,419 |
| 16 | 14.8 / 78.3 | 5.3× | 14.8 / 69.5 | 1,180 / 5,782 |

Decision time = initiation interval × Tmin (unstalled). The corpus is synthetic and its
mean sequential latency is close to the worst case (13.99 of 16 cycles at 16 rules), so the
average column is corpus-specific and must not be read as network behavior.

**Why sharing saves so little real area (measured decomposition, 16 rules, 3 ns target).**
Standalone rule storage with its write decode maps to 64.5k µm², i.e. 81% of the parallel
and 87% of the sequential design (68% and 72% at 4 rules). That is about 37.7 µm² per stored
bit against 20.0 µm² for the flop itself. One comparator group is about 1.2k µm²; the sequential
rule select is about 9.1k µm². Comparator sharing therefore attacks only the 13–32% of area that
is not storage, and the select multiplexer takes back a large part of what it saves.
*Inference, not verified:* `dfflibmap` appears not to use the library's enable flop, so the
enable and synchronous reset become gates around a plain `dfxtp_1`.

## 3. Design decisions

1. **Fix the RTL in place, keep the v0.3 numbers.** The write-path bug sat in both engines,
   so leaving it would have made every later comparison wrong. The baseline CSVs stay in `docs/data/`.
2. **Same storage format, write path, and interface in both engines.** The comparison is only
   meaningful if the architectures differ in matching and nothing else.
3. **Explicit one-hot select instead of `+:`.** Chosen over a rotating shift-register rule store
   (which removes the select but changes storage and the update semantics) to keep the spec's
   packed-table contract. The shift-register alternative is untested.
4. **Separate path classes with budgets that scale with the period,** so an in→out path is not
   judged against a budget meant for reg→reg.
5. **Evaluate at one common clock and also report each design's own Tmin,** per the roadmap.
6. **Mapped netlists are replayed** through the same trace generator and oracle as the RTL
   (`scripts/check_gate_level.py`): 12 netlists, all decisions and cycle-exact latencies match.
   A deliberately corrupted netlist is rejected (handshake mismatch at cycle 19), so the check can fail.
7. **Fail loudly on missing tools.** Both new scripts exit with `BLOCKED` rather than pass.

## 4. Limitations

- Pre-layout: ideal wires, no clock tree, no placement, no wire parasitics. High-fanout nets
  (`cfg_rule` to every rule, the index decode) are optimistic here and will be worse after routing.
- One typical corner (tt, 25 °C, 1.8 V). No slow corner, no OCV, no signoff.
- Area is Yosys's sum of library cell areas, not placed area or utilization.
- One library and one synthesis tool version; ABC's choices (it built a ripple-style comparator on
  the parallel critical path) are heuristic, and different versions will move the numbers.
- No power or switching analysis, so the roadmap's energy question is unanswered.
- Gate-level replay is zero-delay: it checks function, not timing, glitches, or real-cell reset behavior.
- Simulation is not formal proof. The formal harness from the roadmap is still not done.
- The I/O budget (20%), uncertainty, driving cell and load are assumptions of this study.
- CI does not run the mapping or gate-level steps: they need OpenSTA (built from source, with CUDD)
  and a Liberty file that is not stored in this repo.
- Response timing still depends on scan depth; there is no constant-time or confidentiality claim.

## 5. Conclusions the evidence supports, and ones it does not

Supported, for this RTL, library, flow and constraints: comparator sharing reduced mapped area by
about 6–8% while increasing worst-case decision time 1.8–5.3×, so it is a poor trade here. The
sequential engine does clock somewhat faster (about 10%).

Not supported: any claim about other libraries, post-layout area or timing, power, real traffic, or
that sharing can never pay off. The decomposition suggests it could pay off only if rule storage were
much cheaper relative to comparison logic (e.g. fewer rules than 4 with wider rules, or a latch or
SRAM store).

## 6. Open opportunity (not applied)

A scratch experiment (16 rules, storage only, same flow) shows that resetting only each rule's
enable bit rather than all 108 bits cuts storage area from 64.5k to 55.0k µm² (about 15%). It
changes the spec's wording ("reset clears the policy") and must be decided deliberately; it would
help both engines equally and would not change the sharing conclusion.

## 7. Reproduce

```
python scripts/check_engine.py && python scripts/check_synthesis.py   # RTL + generic
export STA=/path/to/sta GATESHIELD_LIBERTY=/path/to/sky130hd_tt.lib[.gz]
python scripts/check_mapping.py     # mapped area + timing -> build/mapped_comparison.csv
python scripts/check_gate_level.py  # replays the mapped netlists
```
