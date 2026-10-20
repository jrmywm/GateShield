"""Render exportable study figures. Optional dependency: matplotlib>=3.8.

Run from repository root: python scripts/plot_results.py
The RTL verification scripts do not require Matplotlib.
"""
from pathlib import Path
import csv
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'build'/'matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.ticker import FuncFormatter

OUT = ROOT/'docs'/'figures'
BLUE = '#2463A6'
ORANGE = '#CA6C2A'
INK = '#182A3B'
MUTED = '#536579'
GRID = '#DDE5EC'
SOURCE = 'Source: docs/data/ and the mapped-study CI evidence | 20 October 2026'


def setup():
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 12,
        'text.color': INK, 'axes.labelcolor': INK,
        'xtick.color': MUTED, 'ytick.color': MUTED,
        'axes.edgecolor': GRID, 'axes.spines.top': False,
        'axes.spines.right': False, 'axes.titleweight': 'bold',
        'svg.fonttype': 'none', 'figure.facecolor': 'white',
        'savefig.facecolor': 'white',
    })
    OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    for extension in ('png', 'svg'):
        path = OUT/f'{name}.{extension}'
        fig.savefig(path, dpi=190)
        if extension == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n', encoding='utf-8', newline='\n')
    plt.close(fig)
    print(f'Created {name}.png and .svg')


def cell_plot():
    with (ROOT/'docs/data/generic_synthesis_v0.4.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    data = {(int(r['rules']), r['architecture']): int(r['generic_cells']) for r in rows}
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.subplots_adjust(left=.10, right=.96, top=.74, bottom=.22)
    fig.text(.10, .94, 'GateShield | Synthesis comparison', fontsize=22, weight='bold')
    fig.text(.10, .885, 'Constant-slice rule access removes the earlier synthesis artifact.', fontsize=13, color=MUTED)
    ns = (4, 8, 16)
    for offset, architecture, color in ((-.19, 'parallel', BLUE), (.19, 'sequential', ORANGE)):
        values = [data[n, architecture] for n in ns]
        bars = ax.bar([i+offset for i in range(3)], values, width=.32,
                      color=color, label=architecture.capitalize(), zorder=3)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x()+bar.get_width()/2, value+420, f'{value:,}',
                    ha='center', va='bottom', fontsize=12, weight='bold')
    for i, n in enumerate(ns):
        change = 100*(data[n, 'sequential']/data[n, 'parallel']-1)
        ax.text(i, max(data[n, 'parallel'], data[n, 'sequential'])+1600, f'{change:+.1f}% sequential',
                ha='center', color=ORANGE, fontsize=11,
                bbox=dict(boxstyle='round,pad=.35', fc='#FFF2E7', ec='none'))
    ax.set_xticks(range(3), [f'{n} rules' for n in ns])
    ax.set_ylim(0, 10500)
    ax.set_ylabel('Total generic bit-level cells')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(axis='y', color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc='upper left', bbox_to_anchor=(0, 1.17), ncol=2, frameon=False)
    fig.text(.10, .12, 'Both totals include rule storage, datapath, selection, and control.', fontsize=11, color=MUTED)
    fig.text(.10, .075, 'Flattened Yosys synthesis before ABC mapping. Cell count is not physical area.', fontsize=11, color=MUTED)
    fig.text(.10, .03, SOURCE, fontsize=9, color=MUTED)
    save(fig, '01_generic_cell_comparison')


def latency_plot():
    ns = (4, 8, 16)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7))
    fig.subplots_adjust(left=.07, right=.96, top=.72, bottom=.25, wspace=.25)
    fig.text(.07, .94, 'GateShield | Cycle-latency tradeoff', fontsize=22, weight='bold')
    fig.text(.07, .885, 'Specified cycle bounds, checked in RTL simulation; no clock-frequency claim.', fontsize=13, color=MUTED)
    for ax, sequential, parallel, title, ylabel in (
        (axes[0], ns, (1, 1, 1), 'Response production', 'Clock cycles after request acceptance'),
        (axes[1], tuple(n+2 for n in ns), (3, 3, 3), 'Unstalled initiation interval', 'Clock cycles between accepted requests'),
    ):
        ax.plot(ns, sequential, color=ORANGE, marker='o', lw=2.5, ms=7,
                label='Sequential: last match / no match')
        ax.plot(ns, parallel, color=BLUE, marker='o', lw=2.5, ms=7,
                label='Parallel: every decision')
        for x, y in zip(ns, sequential):
            ax.annotate(str(y), (x, y), xytext=(0, 10), textcoords='offset points',
                        ha='center', color=ORANGE, weight='bold')
        ax.annotate(str(parallel[-1]), (ns[-1], parallel[-1]), xytext=(0, 10),
                    textcoords='offset points', ha='center', color=BLUE, weight='bold')
        ax.set_title(title, fontsize=15, pad=15)
        ax.set_xlabel('Number of rules')
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(ns)
        ax.set_xlim(2.8, 17.2)
        ax.set_ylim(0, 21)
        ax.set_yticks((0, 4, 8, 12, 16, 20))
        ax.grid(color=GRID, axis='y')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower left', bbox_to_anchor=(.06, .13),
               ncol=2, frameon=False, fontsize=11)
    fig.text(.07, .105, 'A sequential first-rule match has the same cycle counts as parallel: latency 1, interval 3.', fontsize=11, color=MUTED)
    fig.text(.07, .065, 'Production excludes receiver stalls. Intervals assume no stalls, reset, or configuration changes.', fontsize=10, color=MUTED)
    fig.text(.07, .025, SOURCE, fontsize=9, color=MUTED)
    save(fig, '02_cycle_latency_comparison')


def architecture_plot():
    fig, ax = plt.subplots(figsize=(14, 9))
    fig.subplots_adjust(left=.02, right=.98, top=.98, bottom=.02)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')

    def box(x, y, w, h, text, color, fontsize=11, fill='white'):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=.4',
                                   linewidth=1.3, facecolor=fill, edgecolor=color))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fontsize, color=INK)

    def arrow(start, end, color=INK, style='-'):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=13,
                                    lw=1.4, color=color, linestyle=style))

    ax.text(4, 96, 'GateShield | Two implementations, one policy', fontsize=23, weight='bold')
    ax.text(4, 91.5, 'Conceptual RTL architecture | first matching rule wins; default DENY', fontsize=13, color=MUTED)
    for y, color in ((51, BLUE), (11, ORANGE)):
        ax.add_patch(FancyBboxPatch((3, y), 94, 35, boxstyle='round,pad=.5',
                                   linewidth=0, facecolor='#F4F7FA'))

    ax.text(6, 81.5, 'A. Parallel engine', fontsize=16, weight='bold', color=BLUE)
    box(6, 59, 17, 11, 'Captured\nheader', BLUE)
    box(32, 72, 25, 7, 'Policy registers: N rules', BLUE)
    box(32, 57, 25, 11, 'N rule-comparison\ngroups', BLUE)
    box(64, 57, 12, 11, 'Priority\nselector', BLUE)
    box(82, 57, 12, 11, 'Response\nregisters', BLUE)
    arrow((23.4, 64.5), (31.5, 62.5), BLUE)
    arrow((44.5, 71.5), (44.5, 68.5), BLUE)
    arrow((57.4, 62.5), (63.5, 62.5), BLUE)
    arrow((76.4, 62.5), (81.5, 62.5), BLUE)
    ax.text(6, 53.5, 'All rules evaluated together; response produced after 1 cycle.', fontsize=11, color=MUTED)

    ax.text(6, 41.5, 'B. Sequential engine', fontsize=16, weight='bold', color=ORANGE)
    box(6, 19, 17, 11, 'Captured\nheader', ORANGE)
    box(32, 32, 25, 7, 'Policy registers: N rules', ORANGE)
    box(32, 17, 11, 11, 'Rule\nselector', ORANGE)
    box(49, 17, 18, 11, 'One shared\ncomparison group', ORANGE, fontsize=10)
    box(82, 17, 12, 11, 'Response\nregisters', ORANGE)
    box(64, 32, 14, 7, 'Scan counter', ORANGE)
    # Captured header feeds the comparator directly, not the policy selector.
    ax.plot((23.4, 26, 26, 46.5, 46.5), (24.5, 24.5, 30.4, 30.4, 25), color=ORANGE, lw=1.4)
    arrow((46.5, 25), (48.5, 25), ORANGE)
    arrow((37.5, 31.5), (37.5, 28.5), ORANGE)
    arrow((43.4, 22.5), (48.5, 22.5), ORANGE)
    arrow((67.4, 22.5), (81.5, 22.5), ORANGE)
    # Counter selects a rule and advances only while scanning.
    ax.plot((63.5, 60, 60, 44.5, 44.5), (35.5, 35.5, 29.8, 29.8, 26.5),
            color=MUTED, lw=1.3, linestyle='--')
    arrow((44.5, 26.5), (43.5, 26.5), MUTED, '--')
    ax.text(6, 13.2, 'Check one rule each cycle; stop at first match, otherwise DENY after N cycles.', fontsize=11, color=MUTED)

    ax.text(4, 7.5, 'Both: one outstanding request, stable stalled responses, configuration only after draining.', fontsize=11, color=MUTED)
    ax.text(4, 3.5, 'Conceptual diagram; not an extracted netlist. Source: constant-slice RTL implementation.', fontsize=10, color=MUTED)
    save(fig, '03_architecture_comparison')


def mapped_plot():
    path = ROOT/'docs/data/mapped_comparison_sky130hd_tt_corrected.csv'
    if not path.exists():
        print('Mapped figure skipped: corrected rerun snapshot is not available.')
        return
    with path.open(newline='') as f:
        rows = [r for r in csv.DictReader(f) if float(r['map_target_ns']) == 3.0]
    data = {(int(r['rules']), r['architecture']): r for r in rows}
    ns = (4, 8, 16)
    if any(data[n, a]['meets_eval_period'] != 'True' for n in ns for a in ('parallel', 'sequential')):
        raise ValueError('Cannot plot common-clock operating results for a failing design')
    periods = {float(r['eval_period_ns']) for r in rows}
    if len(periods) != 1:
        raise ValueError('Common-clock figure requires one evaluation period')
    period = periods.pop()
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7))
    fig.subplots_adjust(left=.08, right=.96, top=.73, bottom=.25, wspace=.27)
    fig.text(.08, .94, 'GateShield | Mapped area and response latency', fontsize=21, weight='bold')
    fig.text(.08, .885, f'SKY130 HD typical corner | 3 ns mapping target | evaluated at a common {period:g} ns clock', fontsize=12, color=MUTED)
    left, right = axes
    for off, arch, color in ((-.19,'parallel',BLUE),(.19,'sequential',ORANGE)):
        values = [float(data[n,arch]['area_um2']) for n in ns]
        bars = left.bar([i+off for i in range(3)], values, width=.32, color=color, label=arch.capitalize(), zorder=3)
        for bar, value in zip(bars, values):
            left.text(bar.get_x()+bar.get_width()/2,value+1800,f'{value/1000:.1f}k',ha='center',fontsize=10,weight='bold')
        latency = [float(data[n,arch]['worst_response_latency_at_eval_ns']) for n in ns]
        right.plot(ns,latency,color=color,lw=2.5,marker='o',label=arch.capitalize())
        for n, value in zip(ns,latency):
            right.annotate(f'{value:g}',(n,value),xytext=(0,10),textcoords='offset points',ha='center',color=color,weight='bold')
    left.set_title('Mapped cell area',fontsize=15,pad=15)
    left.set_ylabel('Sum of library cell areas (µm²)',fontsize=11)
    left.set_xticks(range(3), [str(n) for n in ns]);left.set_xlabel('Number of rules')
    left.set_ylim(0,100000);left.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x/1000:g}k'))
    right.set_title('Worst-case response production',fontsize=15,pad=15)
    right.set_ylabel('Nanoseconds after request acceptance',fontsize=11)
    right.set_xticks(ns);right.set_xlabel('Number of rules');right.set_xlim(2.8,17.2);right.set_ylim(0,95)
    for ax in axes:
        ax.grid(axis='y',color=GRID,zorder=0);ax.set_axisbelow(True)
    handles,labels=left.get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower left',bbox_to_anchor=(.07,.13),ncol=2,frameon=False)
    intervals = [float(data[16,a]['worst_acceptance_interval_at_eval_ns']) for a in ('parallel','sequential')]
    fig.text(.08,.105,f'Response production is not acceptance interval. At 16 rules the unstalled intervals are {intervals[0]:g} ns / {intervals[1]:g} ns.',fontsize=10,color=MUTED)
    fig.text(.08,.065,'Pre-layout, ideal wires/clock, one corner. Mapped cell area is not die area; no power claim.',fontsize=10,color=MUTED)
    fig.text(.08,.025,SOURCE,fontsize=9,color=MUTED)
    save(fig,'04_mapped_area_and_latency')


if __name__ == '__main__':
    setup()
    cell_plot()
    latency_plot()
    architecture_plot()
    mapped_plot()
