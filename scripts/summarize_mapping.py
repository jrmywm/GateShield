"""Generate a correctly labelled Markdown summary from mapped and latency CSVs."""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize(mapped, latencies, target=3.0):
    selected = [r for r in mapped if float(r['map_target_ns']) == target]
    data = {(int(r['rules']), r['architecture']): r for r in selected}
    if not data or len(data) != len(selected):
        raise ValueError('Missing or duplicate mapped configurations')
    counts = sorted({n for n, _ in data})
    if any((n, a) not in data for n in counts for a in ('parallel', 'sequential')):
        raise ValueError('Both architectures are required at every rule count')
    periods = {float(r['eval_period_ns']) for r in selected}
    if len(periods) != 1:
        raise ValueError('Common-clock summary requires one evaluation period')
    period = periods.pop()
    lines = ['# Corrected mapped results', '',
             f'Mapping target: {target:g} ns. Common evaluation clock: {period:g} ns. '
             'Times below refer to that common clock, not each design\'s estimated Tmin.', '',
             '| Rules | Area par / seq (µm²) | Seq saving | Setup slack par / seq (ns) | Worst response par / seq (ns) | Worst acceptance interval par / seq (ns) |',
             '|---|---:|---:|---:|---:|---:|']
    for n in counts:
        p, s = data[n, 'parallel'], data[n, 'sequential']
        pa, sa = float(p['area_um2']), float(s['area_um2'])
        feasible = p['meets_eval_period'] == s['meets_eval_period'] == 'True'
        response = (f"{float(p['worst_response_latency_at_eval_ns']):g} / "
                    f"{float(s['worst_response_latency_at_eval_ns']):g}") if feasible else 'not both feasible'
        interval = (f"{float(p['worst_acceptance_interval_at_eval_ns']):g} / "
                    f"{float(s['worst_acceptance_interval_at_eval_ns']):g}") if feasible else 'not both feasible'
        lines.append(f"| {n} | {pa:,.1f} / {sa:,.1f} | {100*(1-sa/pa):.2f}% | "
                     f"{float(p['setup_wns_at_eval_ns']):+.3f} / {float(s['setup_wns_at_eval_ns']):+.3f} | {response} | {interval} |")
    means = {(int(r['rules']), r['architecture']): r for r in latencies}
    lines += ['', '## Synthetic-corpus average at the common clock', '',
              '| Rules | Mean response par / seq (ns) | Mean unstalled acceptance interval par / seq (ns) |',
              '|---|---:|---:|']
    for n in counts:
        if any(data[n, a]['meets_eval_period'] != 'True' for a in ('parallel', 'sequential')):
            lines.append(f'| {n} | not both feasible | not both feasible |')
            continue
        values = [float(means[n, a]['mean_cycles']) for a in ('parallel', 'sequential')]
        lines.append(f'| {n} | {values[0]*period:.2f} / {values[1]*period:.2f} | '
                     f'{(values[0]+2)*period:.2f} / {(values[1]+2)*period:.2f} |')
    lines += ['', 'These averages describe the common synthetic transaction corpus; '
              'they do not establish real-traffic behavior. Intervals assume no receiver stalls. '
              'Area is summed library cell area. All timing is pre-layout with ideal wires and clock at one typical corner; no power or signoff claim.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapped', type=Path, default=ROOT/'build/mapped_comparison.csv')
    parser.add_argument('--latency', type=Path, default=ROOT/'build/latency_comparison.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'build/mapped_summary.md')
    args = parser.parse_args()
    with args.mapped.open(newline='') as f:
        mapped = list(csv.DictReader(f))
    with args.latency.open(newline='') as f:
        latency = list(csv.DictReader(f))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summarize(mapped, latency), encoding='utf-8', newline='\n')
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
