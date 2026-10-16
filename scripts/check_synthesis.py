"""Generic synthesis smoke check; no technology area or frequency claims."""
from pathlib import Path
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
    for n in (1, 4, 8, 16):
        script = (f'read_verilog rtl/gateshield_parallel_core.v rtl/gateshield_parallel.v; '
                  f'chparam -set N_RULES {n} gateshield_parallel; '
                  'synth -top gateshield_parallel -noabc; '
                  'select -assert-none t:$dlatch t:$_DLATCH_*; '
                  'check -assert; stat')
        log = build/f'synthesis_parallel_{n}.log'
        subprocess.run(['yosys', '-Q', '-l', str(log), '-p', script],
                       cwd=ROOT, check=True, timeout=120, stdout=subprocess.DEVNULL)
        print(f'PASS generic synthesis rules={n}; log={log}', flush=True)
    print('Generic logic only: no library-mapped area, timing, or power results.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
