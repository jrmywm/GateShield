# GateShield findings

## Evidence and scope

The supplied patches contain constant-slice RTL fixes, mapping scripts, and result CSVs. Their separately supplied findings file matched the patch's findings exactly and is archived as `docs/data/findings_supplied.md`. Its isolated experiments and area decomposition did not include scratch scripts or logs; those remain author-reported.

This integration corrects two measurement issues: response-production latency was mislabeled using initiation interval, and ABC was given 0.010 fF rather than the intended 10 fF. The supplied `mapped_comparison_sky130hd_tt.csv` remains a historical run with corrected column names. The independently rerun result is `mapped_comparison_sky130hd_tt_corrected.csv`. CI metadata identifies the source commit, library hashes, tools, and constraints.

## 1. Coding style obscured the architectural comparison

At 16 rules the original sequential engine used 25,456 generic cells versus 20,298 for parallel. Both engines used a variable-offset part-select for configuration writes; sequential also used one for reads. In this Yosys flow, those constructs produced expensive shift/mux networks. The supplied isolated experiments report:

| Construct, 16 rules | Variable-offset form | Constant-slice form |
|---|---:|---:|
| Read a 108-bit rule | 9,948 generic cells | 1,756 |
| Write a 108-bit rule | 15,020 generic cells | 1,788 |

The fix selects constant slices with index comparisons. It preserves filtering semantics and cycle counts. Variable part-selects are valid RTL; the result is specific to this coding form and synthesis flow, not an unavoidable language rule. Separate block counts must not be added to or subtracted from optimized whole-design counts.

| Rules | Parallel v0.3 â†’ fixed | Sequential v0.3 â†’ fixed | Fixed sequential / parallel |
|---|---:|---:|---:|
| 4 | 6,468 â†’ 1,864 | 8,007 â†’ 1,382 | 0.74 |
| 8 | 11,213 â†’ 3,582 | 13,955 â†’ 2,267 | 0.63 |
| 16 | 20,298 â†’ 7,554 | 25,456 â†’ 4,058 | 0.54 |

Source: `generic_synthesis_baseline_v0.3.csv` and `generic_synthesis_v0.4.csv`. These are generic counts, not physical area. Original figures are retained as archived baselines.

## 2. Response latency is not initiation interval

If edge E0 accepts a parallel request, E1 produces its response, E2 can consume it, and E3 can accept another request. Thus production latency is one cycle and the unstalled initiation interval is three cycles. Sequential matching takes k+1 cycles for a first match at zero-based rule k, or N cycles for no match. Its unstalled interval is latency plus two cycles.

The old `worst_decision_time_ns` field was `ii_worst_cycles Ã— Tmin`. It has been renamed `worst_acceptance_interval_at_min_period_ns`. New results explicitly report response latency, acceptance interval, estimated minimum-period values, and common-clock values separately.

At a **feasible common 5 ns clock**, worst cases are:

| Rules | Response production, parallel / sequential | Acceptance interval, parallel / sequential |
|---|---:|---:|
| 4 | 5 / 20 ns | 15 / 30 ns |
| 8 | 5 / 40 ns | 15 / 50 ns |
| 16 | 5 / 80 ns | 15 / 90 ns |

These conversions alone do not establish clock feasibility: inspect direct setup slack for the specific netlist. Receiver backpressure is excluded from production latency and can delay consumption indefinitely.

The common synthetic corpus has sequential mean production latencies of 3.807, 7.166, and 13.987 cycles at 4, 8, and 16 rules; parallel is one cycle. At a feasible 5 ns these become about 19.04, 35.83, and 69.93 ns for sequential and 5 ns for parallel. Average unstalled acceptance interval adds two cycles. These averages describe this corpus, not representative network traffic or the later arbitrary-cycle fuzz.

## 3. Mapping and load units

The flow maps with Yosys/ABC to SKY130 `sky130_fd_sc_hd__tt_025C_1v80`, then evaluates with OpenSTA. Assumptions: ideal wires and clock, 0.10 ns uncertainty, input/output budgets of 20% of period, `buf_2` input driving cell, and 10 fF output load. Mapping targets are 10 ns and 3 ns. The **same mapped netlists** are directly evaluated at 5 ns. A mapping target is not a closure result.

ABC's `-constr` load is in **fF**; OpenSTA uses the Liberty capacitance unit, pF here. The supplied script wrote 0.010 to both tools, giving ABC 0.01 fF and OpenSTA 10 fF. The correction writes **10.0** to ABC and **0.010** to OpenSTA. See [Yosys 0.33 ABC help](https://github.com/YosysHQ/yosys/blob/yosys-0.33/passes/techmap/abc.cc).

Old STA measurements still describe their old netlists, but those netlists were not mapped under the claimed load. Historical results at the 3 ns target are:

| Rules | Area, parallel / sequential (ÂµmÂ²) | Sequential saving | Estimated Tmin, par / seq (ns) | Slack at 5 ns, par / seq (ns) |
|---|---:|---:|---:|---:|
| 4 | 21,424 / 20,161 | 5.9% | 3.931 / 3.479 | +1.069 / +1.521 |
| 8 | 40,993 / 37,913 | 7.5% | 4.197 / 3.744 | +0.803 / +1.256 |
| 16 | 79,648 / 73,862 | 7.3% | 4.937 / 4.349 | +0.063 / +0.651 |

All six supplied 3 ns-target netlists passed their supplied 5 ns check; none met 3 ns. At the 10 ns mapping target, the 16-rule designs failed 5 ns. **Use the corrected rerun for current numerical conclusions.**

Minimum periods are estimated separately for regâ†’reg, inputâ†’reg, regâ†’output, and inputâ†’output paths, accounting for period-dependent I/O budgets. Estimates come from one STA operating point; direct 5 ns slack is the primary common-clock evidence.

## 3a. Independently reproduced corrected-load results

[CI run 39375335391](https://github.com/jrmywm/GateShield/actions/runs/39375335391) at source commit `fd97b98f391ffe5793d6ef89c50b51530afa30ac` passed RTL checks, all 12 mapping/STA runs, and all 12 mapped-netlist zero-delay replays. All six 3 ns-target netlists passed the direct 5 ns setup check. The 16-rule 10 ns-target netlists failed that clock, as retained in the CSV; a successful workflow does not mean every requested timing point met timing.

### Corrected-load area and timing

Mapping target: 3 ns. Common evaluation clock: 5 ns. Times below refer to that common clock, not each design's estimated Tmin.

| Rules | Area par / seq (ÂµmÂ²) | Seq saving | Setup slack par / seq (ns) | Worst response par / seq (ns) | Worst acceptance interval par / seq (ns) |
|---|---:|---:|---:|---:|---:|
| 4 | 21,473.1 / 20,176.9 | 6.04% | +1.083 / +1.569 | 5 / 20 | 15 / 30 |
| 8 | 41,018.1 / 37,905.1 | 7.59% | +0.827 / +1.231 | 5 / 40 | 15 / 50 |
| 16 | 79,652.6 / 73,914.6 | 7.20% | +0.060 / +0.588 | 5 / 80 | 15 / 90 |

### Synthetic-corpus average at the common clock

| Rules | Mean response par / seq (ns) | Mean unstalled acceptance interval par / seq (ns) |
|---|---:|---:|
| 4 | 5.00 / 19.04 | 15.00 / 29.04 |
| 8 | 5.00 / 35.83 | 15.00 / 45.83 |
| 16 | 5.00 / 69.93 | 15.00 / 79.93 |

These averages describe the common synthetic transaction corpus; they do not establish real-traffic behavior. Intervals assume no receiver stalls. Area is summed library cell area. All timing is pre-layout with ideal wires and clock at one typical corner; no power or signoff claim.

## 4. Area interpretation

The supplied standalone experiments report a 16-rule store with write decode at about 64.5k ÂµmÂ², one comparator group at 1.2k ÂµmÂ², and a sequential rule selector at 9.1k ÂµmÂ². These are **author-reported separate block experiments**, not an additive decomposition of the optimized whole netlist. Their scripts/reports were not supplied, and their mapping-load setting needs checking.

The whole-design CSV separately sums flop-cell area and other cell area. Reset/enable gates around plain flops are a plausible explanation for storage overhead, but must be confirmed from the cell types rather than inferred from area alone. Enable-only reset is an unimplemented alternative requiring a specification and verification update.

## 5. Verification and reproduction

- Policy and metric-regression tests check decisions, latency/interval labels, and ABC/STA unit conversion.
- RTL simulations check both engines against the policy oracle, including reset cancellation, forbidden writes, response stalls, and common-corpus decision replay.
- Mapping metadata records the source commit, source/pruned Liberty hashes, tools, loads, target periods, and common evaluation clock.
- Gate-level replay requires the netlist set to match the mapping manifest and the Liberty hash to match. It imports Liberty logic functions and reuses the transaction oracle. This is zero-delay functional replay, not SDF simulation or physical-cell signoff.
- `.github/workflows/mapped-study.yml` builds pinned OpenSTA/CUDD, maps 12 configurations, checks them at 5 ns, replays their mapped netlists, and uploads evidence. Consult the completed run for the reviewed commit. The supplied mutation-test claim has not been independently reproduced.

```sh
python -m unittest discover -s tests -v
python scripts/check_rtl.py
python scripts/check_engine.py
python scripts/check_synthesis.py
export STA=/path/to/sta
export GATESHIELD_LIBERTY=/path/to/sky130hd_tt.lib.gz
python scripts/check_mapping.py --eval-period 5
python scripts/check_gate_level.py
```

PowerShell uses `$env:STA = 'C:\path\to\sta.exe'` and `$env:GATESHIELD_LIBERTY = 'C:\path\to\sky130hd_tt.lib.gz'`. Hosted CI supplies the Linux toolchain without a vendor FPGA suite.

## 6. Defensible conclusions

The project measures how comparator sharing trades mapped cell area against response latency and sustainable acceptance rate under identical policy/interface semantics. The corrected-load rerun confirms 6.04%, 7.59%, and 7.20% mapped area savings at 4, 8, and 16 rules. At the common 5 ns clock, worst-case response latency is 4–16 times higher and unstalled worst-case acceptance interval is 2–6 times higher. These ratios describe different metrics and must not be interchanged.

Whether sharing is useful depends on the application's rate and latency requirements. It is not universally inferior, and comparator sharing alone is not novel.

Limits: pre-layout, one typical corner, ideal wires and clock, no clock tree or extracted parasitics, no physical signoff, no power/energy result, no formal proof, and no demonstrated real-traffic average. Summed library cell area is not die area. Positive ideal-clock hold slack does not establish hold closure after clock-tree synthesis. Variable scan latency can reveal scan depth; policy confidentiality is outside this prototype's scope.
