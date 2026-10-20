# Source of plotted results

**Historical v0.3 baseline only.** Current figures use the constant-slice v0.4 data under `docs/data/`. Original figures are archived under `docs/figures/archive_v0.3/`.

The generic-cell CSV is transcribed from the completed synthesis job for source commit `cc6f4132708b19b2e7bb9c21dedb6f75c86a304d`:

- Run: https://github.com/jrmywm/GateShield/actions/runs/39187451888
- Source job: `117852759787`; comparison data is also in the run's `gateshield-comparison-reports` artifact.
- Artifact ID: `12158857036`, digest `sha256:f1f922e9e67af54b95f4d938634eaac5ac5dc024375fcbd4774c32610df57c1f`.
- Flow: `synth -flatten -noabc`, generic bit-level cells, no technology library.

The latency figure uses the implemented cycle contract, checked by the run's cross-architecture transaction simulations. It shows first-match and last-match/no-match bounds; it does not plot a measured workload average or clock frequency. Latency excludes receiver stalls. Initiation intervals assume an always-ready receiver, sustained requests, no reset, and no configuration changes.

The figures focus on production configurations of 4, 8, and 16 rules. The 1-rule configuration remains in the CSV as an edge-case test result.

Generic cells are not equal-area objects. These results do not establish physical area, timing in nanoseconds, or power. The architecture diagram is a conceptual explanation of the RTL, not an extracted gate-level schematic.
