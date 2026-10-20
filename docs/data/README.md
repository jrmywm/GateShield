# Study data and provenance

- `generic_synthesis_baseline_v0.3.csv`, `latency_baseline_v0.3.csv`: original variable-offset RTL results, retained as a baseline.
- `generic_synthesis_v0.4.csv`, `latency_v0.4.csv`: constant-slice RTL results supplied in patch 0002. RTL/generic CI verifies the same implementation; averages refer only to the common synthetic corpus.
- `mapped_comparison_sky130hd_tt.csv`: **historical supplied mapping run**. Original measured areas/slacks are preserved. The misleading `worst_decision_time_ns` field was renamed to acceptance interval, a response-latency field was added, and actual load settings were recorded: ABC 0.01 fF, STA 0.010 pF.
- `findings_supplied.md`: exact supplied findings, archived without treating its claims as independently verified. Consult `../findings.md` for corrections and current conclusions.
- `mapped_comparison_sky130hd_tt_corrected.csv` and `mapping_metadata_corrected.json`, when present: independent corrected-load CI rerun. ABC 10 fF and STA 0.010 pF agree. Source commit, tool versions, library hashes, constraints, and CI provenance accompany these records.
- `mapped_summary_corrected.md`, when present: generated interpretation using separately named response-latency and acceptance-interval fields at the common evaluated clock.

Generate a summary with `python scripts/summarize_mapping.py --mapped docs/data/mapped_comparison_sky130hd_tt_corrected.csv --latency docs/data/latency_v0.4.csv --output docs/data/mapped_summary_corrected.md`.

Generic counts, library cell area, physical die area, response latency, and acceptance interval are different metrics. All mapped timing is pre-layout, ideal-clock/wire, single-corner analysis.
