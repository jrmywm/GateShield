"""Library-mapped area and constrained-timing study (Yosys + ABC + OpenSTA).

For each architecture x rule count x mapping target this script:
  1. synthesizes the RTL, maps flops (dfflibmap) and logic (abc) onto a Liberty
     library, and records Yosys's library-based area;
  2. runs OpenSTA with one identical SDC (ideal clock, fixed I/O budgets, fixed
     driving cell and load);
  3. converts the worst slack of each path class into the minimum clock period
     that class would allow, because the I/O budgets scale with the period.

Results: build/mapped_comparison.csv and per-design logs under build/map/.

Tools: yosys, sta (OpenSTA), and a Liberty file. The Liberty file is NOT stored in
this repo; pass --liberty or set GATESHIELD_LIBERTY (plain .lib or .lib.gz). The
study was developed with sky130_fd_sc_hd tt_025C_1v80 (OpenSTA examples/).
Missing tools or library fail explicitly; this never produces a quiet pass.

This is a pre-layout, ideal-wire, single-corner estimate. See docs/findings.md.
"""
from pathlib import Path
import argparse
import csv
import fnmatch
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build' / 'map'

# Constraints shared by every design (documented in docs/findings.md).
IO_FRACTION = 0.20          # input and output delay, as a fraction of the period
UNCERTAINTY_NS = 0.10       # setup clock uncertainty
DRIVING_CELL = ('sky130_fd_sc_hd__buf_2', 'X')
LOAD_PF = 0.010
ABC_LOAD_FF = LOAD_PF * 1000.0  # ABC -constr uses fF; OpenSTA uses this library's pF.
# Cells excluded from mapping (same list OpenROAD-flow-scripts uses for sky130hd).
DONT_USE = ('sky130_fd_sc_hd__probe_p_8', 'sky130_fd_sc_hd__probec_p_8',
            'sky130_fd_sc_hd__lpflow_*')
# Path class -> (from, to, fraction of the period consumed by external budgets).
GROUPS = {
    'reg2reg': ('[all_registers -clock_pins]', '[all_registers -data_pins]', 0.0),
    'in2reg':  ('[all_inputs]', '[all_registers -data_pins]', IO_FRACTION),
    'reg2out': ('[all_registers -clock_pins]', '[all_outputs]', IO_FRACTION),
    'in2out':  ('[all_inputs]', '[all_outputs]', 2 * IO_FRACTION),
}
RTL = ('rtl/gateshield_parallel_core.v', 'rtl/gateshield_parallel.v',
       'rtl/gateshield_sequential.v')


def timing_metrics(arch, n, min_period, eval_period, meets_eval):
    """Keep response production distinct from the single-outstanding service interval."""
    if arch not in ('parallel', 'sequential') or n < 1 or min_period <= 0 or eval_period <= 0:
        raise ValueError('Invalid architecture, rule count, or period')
    latency = 1 if arch == 'parallel' else n
    interval = latency + 2
    return {
        'latency_worst_cycles': latency,
        'ii_best_cycles': 3, 'ii_worst_cycles': interval,
        'worst_response_latency_at_min_period_ns': round(latency * min_period, 3),
        'worst_acceptance_interval_at_min_period_ns': round(interval * min_period, 3),
        'worst_response_latency_at_eval_ns': round(latency * eval_period, 3) if meets_eval else '',
        'worst_acceptance_interval_at_eval_ns': round(interval * eval_period, 3) if meets_eval else '',
    }


def load_liberty(path):
    """Return (pruned_lib_path, {cell: area}, library_name). Prunes DONT_USE."""
    raw = path.read_bytes()
    text = (gzip.decompress(raw) if path.suffix == '.gz' else raw).decode('utf-8')
    name = re.search(r'library \("?([^")\s]+)"?\)', text).group(1)
    cell_re = re.compile(r'^[ \t]*cell \("([^"]+)"\) \{', re.M)
    out, pos = [], 0
    while True:
        m = cell_re.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        depth, j = 0, m.end() - 1
        while True:
            depth += (text[j] == '{') - (text[j] == '}')
            if depth == 0:
                break
            j += 1
        if any(fnmatch.fnmatch(m.group(1), p) for p in DONT_USE):
            out.append(text[pos:m.start()])
        else:
            out.append(text[pos:j + 1])
        pos = j + 1
    pruned = ''.join(out)
    BUILD.mkdir(parents=True, exist_ok=True)
    pruned_path = BUILD / 'library_pruned.lib'
    pruned_path.write_text(pruned, encoding='utf-8')
    areas, cur = {}, None
    for line in pruned.splitlines():
        m = re.match(r'    cell \("([^"]+)"\)', line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'        area : ([0-9.]+);', line)
        if m and cur and cur not in areas:
            areas[cur] = float(m.group(1))
    return pruned_path, areas, name


def write_sdc(path, period):
    io = IO_FRACTION * period
    path.write_text(
        f'create_clock -name clk -period {period} [get_ports clk]\n'
        f'set_clock_uncertainty {UNCERTAINTY_NS} [get_clocks clk]\n'
        'set data_in [lsearch -all -inline -not [all_inputs] [get_ports clk]]\n'
        f'set_input_delay {io} -clock clk $data_in\n'
        f'set_output_delay {io} -clock clk [all_outputs]\n'
        f'set_driving_cell -lib_cell {DRIVING_CELL[0]} -pin {DRIVING_CELL[1]} $data_in\n'
        f'set_load {LOAD_PF} [all_outputs]\n', encoding='utf-8')


def map_design(arch, n, period, lib, tag):
    top = f'gateshield_{arch}'
    netlist = BUILD / f'{tag}.v'
    constr = BUILD / 'abc.constr'
    constr.write_text(f'set_driving_cell {DRIVING_CELL[0]}\nset_load {ABC_LOAD_FF}\n')
    stat = BUILD / f'{tag}.stat.txt'
    # read_liberty -lib gives `check` the port directions of library cells; without it
    # every mapped cell output looks undriven and `check -assert` fails spuriously.
    script = (f'read_liberty -lib -overwrite {lib}; '
              f'read_verilog {" ".join(RTL)}; chparam -set N_RULES {n} {top}; '
              f'synth -top {top} -flatten; dfflibmap -liberty {lib}; '
              f'abc -liberty {lib} -D {int(period * 1000)} -constr {constr}; '
              f'opt_clean -purge; check -assert; '
              f'tee -q -o {stat} stat -liberty {lib}; '
              f'write_verilog -noattr -noexpr {netlist}')
    log = BUILD / f'{tag}.yosys.log'
    res = subprocess.run(['yosys', '-Q', '-q', '-l', str(log), '-p', script], cwd=ROOT,
                         timeout=600, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode:
        tail = '\n'.join(log.read_text().splitlines()[-15:])
        raise SystemExit(f'FAIL yosys mapping {tag}:\n{tail}\n{res.stderr[-500:]}')
    counts = {m.group(1): int(m.group(2)) for m in
              re.finditer(r'^\s+(sky130\S+)\s+(\d+)\s*$', stat.read_text(), re.M)}
    stat_text = stat.read_text()
    assert '$_' not in stat_text, f'{tag}: unmapped generic cells remain'
    total = float(re.search(r'Chip area for module .*: ([0-9.]+)', stat_text).group(1))
    return netlist, counts, total


def run_sta(sta, lib, netlist, top, period, tag):
    sdc = BUILD / f'{tag}.sdc'
    write_sdc(sdc, period)
    lines = [f'read_liberty {lib}', f'read_verilog {netlist}', f'link_design {top}',
             f'read_sdc {sdc}', 'puts "CHECK_BEGIN"', 'check_setup -verbose', 'puts "CHECK_END"']
    for name, (frm, to, _) in GROUPS.items():
        lines.append(f'set pe [find_timing_paths -from {frm} -to {to} -path_delay max '
                     '-group_path_count 1]')
        lines.append(f'if {{[llength $pe] == 0}} {{puts "GROUP {name} none"}} else {{ '
                     f'set p [lindex $pe 0]; puts "GROUP {name} [get_property $p slack] '
                     '[get_full_name [get_property $p startpoint]] '
                     '[get_full_name [get_property $p endpoint]]" }')
    lines.append('report_worst_slack -min -digits 4')
    for name, (frm, to, _) in GROUPS.items():
        lines.append(f'puts "REPORT {name}"; report_checks -from {frm} -to {to} '
                     '-path_delay max -group_path_count 1 -format full -digits 3')
    tcl = BUILD / f'{tag}.tcl'
    tcl.write_text('\n'.join(lines) + '\n')
    res = subprocess.run([sta, '-no_init', '-exit', str(tcl)], cwd=ROOT, text=True,
                         capture_output=True, timeout=600, check=True)
    (BUILD / f'{tag}.sta.log').write_text(res.stdout + res.stderr)
    out = res.stdout
    if re.search(r'(?m)^Error[: ]', out + res.stderr):
        raise RuntimeError(f'{tag}: OpenSTA reported an error; inspect its log')
    check = out.split('CHECK_BEGIN')[1].split('CHECK_END')[0]
    assert 'no clock' not in check.lower() and 'unconstrained' not in check.lower(), \
        f'{tag}: STA setup check reported problems:\n{check}'
    slacks, ends = {}, {}
    for m in re.finditer(r'^GROUP (\w+) (none|(-?[0-9.]+) (\S+) (\S+))$', out, re.M):
        if m.group(2) != 'none':
            slacks[m.group(1)] = float(m.group(3))
            ends[m.group(1)] = f'{m.group(4)} -> {m.group(5)}'
    hold = float(re.search(r'worst slack min (-?[0-9.]+)', out).group(1))
    version = re.search(r'OpenSTA (\S+)', out).group(1)
    return slacks, ends, hold, version


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--liberty', default=os.environ.get('GATESHIELD_LIBERTY'))
    parser.add_argument('--sta', default=os.environ.get('STA') or shutil.which('sta'))
    parser.add_argument('--targets', default='10,3',
                        help='comma-separated abc target periods in ns (default 10,3)')
    parser.add_argument('--rules', default='4,8,16')
    parser.add_argument('--eval-period', type=float, default=5.0,
                        help='common STA clock period in ns for every design (default 5.0)')
    args = parser.parse_args()
    targets = [float(t) for t in args.targets.split(',')]
    rules = [int(r) for r in args.rules.split(',')]
    if not targets or not rules or min(targets) <= 0 or min(rules) < 1 or args.eval_period <= 0:
        parser.error('Periods and rule counts must be positive')
    for tool, ok in (('yosys', shutil.which('yosys')), ('sta (OpenSTA)', args.sta),
                     ('--liberty / GATESHIELD_LIBERTY', args.liberty)):
        if not ok:
            print(f'BLOCKED: {tool} is required.', file=sys.stderr)
            return 2
    liberty = Path(args.liberty)
    if not liberty.exists():
        print(f'BLOCKED: liberty file not found: {liberty}', file=sys.stderr)
        return 2
    lib, areas, libname = load_liberty(liberty)
    yosys_version = subprocess.check_output(['yosys', '-V'], text=True).strip()
    metadata = {
        'liberty_source': str(liberty),
        'liberty_source_sha256': hashlib.sha256(liberty.read_bytes()).hexdigest(),
        'liberty_pruned_sha256': hashlib.sha256(lib.read_bytes()).hexdigest(),
        'library': libname, 'yosys_version': yosys_version,
        'abc_output_load_ff': ABC_LOAD_FF, 'sta_output_load_pf': LOAD_PF,
        'io_fraction': IO_FRACTION, 'uncertainty_ns': UNCERTAINTY_NS,
        'common_period_ns': args.eval_period, 'mapping_targets_ns': targets,
        'rule_counts': rules,
    }
    try:
        metadata['rtl_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        metadata['rtl_commit'] = 'unknown'
    (BUILD/'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    flop_cells = {c for c in areas if re.match(r'sky130_fd_sc_hd__(df|edf|sdf|dl)', c)}
    rows = []
    for target in targets:
        for arch in ('parallel', 'sequential'):
            for n in rules:
                tag = f'{arch}_{n}_t{target:g}'
                netlist, counts, total = map_design(arch, n, target, lib, tag)
                slacks, ends, hold, sta_version = run_sta(
                    args.sta, lib, netlist, f'gateshield_{arch}', args.eval_period, tag)
                pmin = {g: args.eval_period - slacks[g] / (1.0 - GROUPS[g][2]) for g in slacks}
                wns = min(slacks.values())
                limiter = max(pmin, key=pmin.get)
                flops = sum(c for k, c in counts.items() if k in flop_cells)
                flop_area = sum(counts[k] * areas[k] for k in counts if k in flop_cells)
                rows.append({
                    'rules': n, 'architecture': arch, 'map_target_ns': target,
                    'area_um2': round(total, 1), 'flop_count': flops,
                    'flop_area_um2': round(flop_area, 1),
                    'logic_area_um2': round(total - flop_area, 1),
                    'cell_count': sum(counts.values()),
                    'min_period_ns': round(pmin[limiter], 3),
                    'fmax_mhz': round(1000.0 / pmin[limiter], 1),
                    'limiting_class': limiter, 'limiting_path': ends[limiter],
                    **{f'min_period_{g}_ns': round(p, 3) for g, p in pmin.items()},
                    'eval_period_ns': args.eval_period, 'setup_wns_at_eval_ns': round(wns, 3),
                    'meets_eval_period': wns >= 0, 'hold_wns_ns': hold,
                    **timing_metrics(arch, n, pmin[limiter], args.eval_period, wns >= 0),
                    'abc_output_load_ff': ABC_LOAD_FF, 'sta_output_load_pf': LOAD_PF,
                    'liberty': libname, 'yosys_version': yosys_version,
                    'sta_version': sta_version})
                print(f'{"MET" if wns >= 0 else "VIOLATED"} mapped {tag}: area={total:.0f}um2 flops={flops} '
                      f'Tmin={pmin[limiter]:.3f}ns ({limiter}) wns@{args.eval_period:g}ns={wns:.3f} hold_wns={hold}', flush=True)
    out = ROOT / 'build' / 'mapped_comparison.csv'
    with out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {out}. Pre-layout, ideal wires, single typical corner: not signoff.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
