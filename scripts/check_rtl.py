"""Generate oracle vectors and run Icarus; fail explicitly if tools are missing."""
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.policy import Header, Rule, evaluate, pack_rule


def vectors(n):
    rng = random.Random(20261016 + n)
    # Target every rule position, every protocol encoding, range edges and priority.
    for idx in range(n):
        for protocol in range(256):
            for port in (0, 9, 10, 20, 21, 65535):
                rules = [Rule() for _ in range(n)]
                rules[idx] = Rule(port_low=10, port_high=20, allow=True, enable=True)
                yield Header(0xFFFFFFFF, port, protocol), rules
    for _ in range(2000):
        h = Header(rng.getrandbits(32), rng.randrange(65536), rng.choice((6, 17, 1)))
        rules = []
        for idx in range(n):
            # Include deliberate matches; purely random 32-bit masks rarely match.
            mask = rng.choice((0, 0xFFFFFF00, 0xFFFFFFFF, rng.getrandbits(32)))
            value = rng.choice((h.src_ip, rng.getrandbits(32)))
            low, high = rng.choice(((0, 65535), (h.dst_port, h.dst_port), (20, 10), (10, 20)))
            rules.append(Rule(value, mask, low, high, rng.choice((6, 17)),
                              bool(rng.getrandbits(1)), bool(rng.getrandbits(1)), bool(rng.getrandbits(1))))
        yield h, rules


def main():
    build = ROOT / 'build'
    build.mkdir(parents=True, exist_ok=True)
    for n in (1, 4, 8, 16):
        path = build / f'vectors_{n}.txt'
        count = 0
        with path.open('w', encoding='ascii') as f:
            for h, rules in vectors(n):
                d = evaluate(h, rules)
                packed = sum(pack_rule(r) << (108*i) for i, r in enumerate(rules))
                f.write(f'{h.src_ip:x} {h.dst_port:x} {h.protocol:x} {packed:x} {int(d.allow)} {int(d.match_found)} {d.rule_index}\n')
                count += 1
        print(f'Generated {count} reference vectors for {n} rules', flush=True)
    if '--generate-only' in sys.argv:
        print('Generation only: RTL was NOT simulated.')
        return 0
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        print('BLOCKED: install Icarus Verilog (iverilog and vvp) to run RTL checks.', file=sys.stderr)
        return 2
    for n in (1, 4, 8, 16):
        binary = build / f'parallel_{n}.vvp'
        subprocess.run(['iverilog', '-g2012', '-s', 'tb_parallel', f'-Ptb_parallel.N_RULES={n}',
                        '-o', str(binary), str(ROOT/'rtl/gateshield_parallel_core.v'),
                        str(ROOT/'tests/tb_parallel.v')], check=True)
        subprocess.run(['vvp', str(binary), f'+vectors={build / f"vectors_{n}.txt"}'], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
