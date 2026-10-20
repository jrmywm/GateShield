"""Gate-level replay of the library-mapped netlists.

Run scripts/check_mapping.py first. Each mapped netlist (build/map/<arch>_<n>_t*.v)
is converted back to plain gates with Yosys (library cell functions imported from the
Liberty file), then driven by the SAME seeded traces, testbench and oracle assertions
that scripts/check_engine.py uses for the RTL. Decisions, rule indices and production
latencies must match cycle-exactly, so this checks what technology mapping produced,
not just the RTL it started from.

Zero-delay simulation: this finds functional errors introduced by mapping. It says
nothing about timing, glitches, or reset/initialization behavior of real cells.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_engine  # noqa: E402  (reuses make_trace and the oracle)

MAP = ROOT / 'build' / 'map'
BUILD = ROOT / 'build'


def main():
    for tool in ('yosys', 'iverilog', 'vvp'):
        if not shutil.which(tool):
            print(f'BLOCKED: {tool} is required.', file=sys.stderr)
            return 2
    lib = MAP / 'library_pruned.lib'
    netlists = sorted(MAP.glob('*_t*.v'))
    netlists = [p for p in netlists if re.fullmatch(r'(parallel|sequential)_\d+_t[0-9.]+', p.stem)]
    if not lib.exists() or not netlists:
        print('BLOCKED: run scripts/check_mapping.py first (no mapped netlists found).',
              file=sys.stderr)
        return 2
    manifest = BUILD / 'mapped_comparison.csv'
    metadata = MAP / 'metadata.json'
    if not manifest.exists() or not metadata.exists():
        raise SystemExit('BLOCKED: mapping manifest and metadata are required; rerun mapping.')
    with manifest.open(newline='') as stream:
        expected_tags = {f"{r['architecture']}_{r['rules']}_t{float(r['map_target_ns']):g}"
                         for r in csv.DictReader(stream)}
    actual_tags = {p.stem for p in netlists}
    if actual_tags != expected_tags:
        raise SystemExit(f'FAIL: mapped netlist set differs from manifest: {actual_tags ^ expected_tags}')
    meta = json.loads(metadata.read_text())
    if hashlib.sha256(lib.read_bytes()).hexdigest() != meta['liberty_pruned_sha256']:
        raise SystemExit('FAIL: pruned Liberty changed after mapping')
    traces = {}
    checked = 0
    for netlist in netlists:
        arch, n, target = re.fullmatch(r'(\w+?)_(\d+)_t([0-9.]+)', netlist.stem).groups()
        n = int(n)
        top = f'gateshield_{arch}'
        if (arch, n) not in traces:
            trace = check_engine.make_trace(n, arch)
            traces[arch, n] = trace
            (BUILD / f'gl_{arch}_{n}.txt').write_text('\n'.join(trace.rows) + '\n', encoding='ascii')
        trace = traces[arch, n]
        flat = MAP / f'{netlist.stem}.gates.v'
        subprocess.run(['yosys', '-Q', '-q', '-p',
                        f'read_liberty -overwrite -ignore_miss_func -ignore_miss_dir '
                        f'-setattr liberty_cell {lib}; read_verilog -defer {netlist}; '
                        f'hierarchy -top {top}; flatten; opt_clean; '
                        f'write_verilog -noattr {flat}'],
                       check=True, timeout=300, stdout=subprocess.DEVNULL)
        text = flat.read_text()
        assert 'sky130' not in text, f'{flat}: library cells remain after flattening'
        # The testbench overrides N_RULES; a mapped netlist is already specialized.
        text, subs = re.subn(rf'^module {top}\(', f'module {top} #(parameter N_RULES = {n}) (',
                             text, flags=re.M)
        assert subs == 1
        flat.write_text(text)
        binary = BUILD / f'gl_{arch}_{n}_t{target}.vvp'
        transcript = BUILD / f'gl_responses_{arch}_{n}_t{target}.txt'
        subprocess.run(['iverilog', '-g2012', '-s', 'tb_engine', f'-Ptb_engine.N_RULES={n}',
                        f'-Ptb_engine.SEQUENTIAL={int(arch == "sequential")}',
                        '-o', str(binary), str(flat), str(ROOT / 'tests/tb_engine.v')],
                       check=True, timeout=120)
        subprocess.run(['vvp', str(binary), f'+vectors={BUILD / f"gl_{arch}_{n}.txt"}',
                        f'+responses={transcript}'], check=True, timeout=600,
                       stdout=subprocess.DEVNULL)
        rows = [tuple(map(int, r.split())) for r in transcript.read_text().splitlines()]
        expected = [(int(d.allow), int(d.match_found), d.rule_index)
                    for d in trace.completed_decisions]
        assert [r[:3] for r in rows] == expected, (netlist.stem, 'gate-level decisions differ')
        for r in rows:
            expected_latency = 1 if arch == 'parallel' else (r[2] + 1 if r[1] else n)
            assert r[3] == expected_latency, (netlist.stem, r, 'gate-level latency differs')
        checked += 1
        print(f'PASS gate-level {netlist.stem}: {len(rows)} decisions, '
              f'cycle-exact latencies match', flush=True)
    print(f'{checked} mapped netlists replayed. Zero-delay functional check only.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
