"""Generic synthesis smoke check; no technology area or frequency claims."""
from pathlib import Path
import csv
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not shutil.which('yosys'):
        print('BLOCKED: yosys is required.', file=sys.stderr)
        return 2
    build = ROOT/'build'
    build.mkdir(exist_ok=True)
    version = subprocess.check_output(['yosys', '-V'], text=True).strip()
    with (build/'generic_synthesis_comparison.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(('rules', 'architecture', 'generic_cells', 'register_bit_cells', 'other_cells', 'yosys_version'))
        for architecture in ('parallel', 'sequential'):
            top = f'gateshield_{architecture}'
            for n in (1, 4, 8, 16):
                stats_path = f'build/stat_{architecture}_{n}.json'
                script = (f'read_verilog rtl/gateshield_parallel_core.v rtl/gateshield_parallel.v rtl/gateshield_sequential.v; '
                          f'chparam -set N_RULES {n} {top}; '
                          f'synth -top {top} -flatten -noabc; '
                          'select -assert-none t:$dlatch t:$_DLATCH_*; '
                          f'check -assert; tee -o {stats_path} stat -json')
                log = build/f'synthesis_{architecture}_{n}.log'
                subprocess.run(['yosys', '-Q', '-l', str(log), '-p', script],
                               cwd=ROOT, check=True, timeout=120, stdout=subprocess.DEVNULL)
                stats = json.loads((ROOT/stats_path).read_text())
                modules = list(stats['modules'].values())
                assert len(modules) == 1, 'Expected flattened top only'
                module = modules[0]
                registers = sum(count for cell, count in module['num_cells_by_type'].items() if 'DFF' in cell)
                cells = module['num_cells']
                writer.writerow((n, architecture, cells, registers, cells-registers, version))
                f.flush()
                print(f'PASS generic synthesis architecture={architecture} rules={n} cells={cells} register_bits={registers}; log={log}', flush=True)
    print('Generic logic only: no library-mapped area, timing, or power results.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
