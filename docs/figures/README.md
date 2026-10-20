# GateShield figures

PNG images are convenient for previews and slides; SVG files retain vector quality for document export. Install the optional plotting dependency with `python -m pip install -r scripts/requirements-figures.txt`, then regenerate all three figures with `python scripts/plot_results.py`. The RTL verification commands do not require this dependency.

1. **Generic cell comparison** — [PNG](01_generic_cell_comparison.png), [SVG](01_generic_cell_comparison.svg). Fixed constant-slice RTL at 4, 8, and 16 rules. Sequential now uses fewer generic cells. These are pre-ABC counts, not physical area.
2. **Cycle-latency comparison** — [PNG](02_cycle_latency_comparison.png), [SVG](02_cycle_latency_comparison.svg). Cycle-contract bounds checked in RTL simulation; no frequency or real-traffic average is shown.
3. **Architecture comparison** — [PNG](03_architecture_comparison.png), [SVG](03_architecture_comparison.svg). Conceptual explanation of the two implemented datapaths, not a synthesized schematic.
4. **Mapped area and common-clock response latency** — [PNG](04_mapped_area_and_latency.png), [SVG](04_mapped_area_and_latency.svg). Corrected-load rerun at a common 5 ns clock, using 3 ns-target netlists that pass the setup check. Mapping target is not operating period.

Current source measurements and scope: [findings](../findings.md). The original source notes and figures are historical: [v0.3 notes](../results/README.md), `archive_v0.3/`.

Suggested application caption: "GateShield compares two implementations of identical programmable filtering semantics. Constant-slice rule access removes an initial synthesis artifact. The study separates generic cell counts, mapped area, response-production latency, and acceptance interval, and evaluates the mapped netlists at one common clock."
