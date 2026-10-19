"""Clocked-engine differential tests, with an independent transaction scoreboard in RTL."""
from dataclasses import dataclass, field
import csv
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.policy import Header, Rule, evaluate, pack_rule


@dataclass
class Trace:
    n: int
    architecture: str = 'parallel'
    state: str = 'idle'
    rules: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    counts: dict = field(default_factory=lambda: dict(accepted=0, completed=0, canceled=0, writes=0))
    remaining: int = 0
    pending_decision: object = None
    completed_decisions: list = field(default_factory=list)
    common_completed: int = 0

    def __post_init__(self):
        assert self.architecture in ('parallel', 'sequential')
        self.rules = [Rule() for _ in range(self.n)]

    def tick(self, *, reset=0, mode=0, write=None, index=0, header=None, ready=1):
        request = header is not None
        h = header or Header(0, 0, 0)
        req_ready = not reset and not mode and self.state == 'idle'
        cfg_active = not reset and self.state == 'configure'
        cfg_ready = cfg_active and bool(mode) and index < self.n
        rsp_valid = not reset and self.state == 'respond'
        decision = evaluate(h, self.rules)
        self.rows.append(' '.join((
            str(int(reset)), str(int(mode)), str(int(write is not None)), f'{index:x}',
            f'{pack_rule(write) if write is not None else 0:x}', str(int(request)),
            f'{h.src_ip:x}', f'{h.dst_port:x}', f'{h.protocol:x}', str(int(ready)),
            str(int(req_ready)), str(int(cfg_active)), str(int(cfg_ready)), str(int(rsp_valid)),
            str(int(decision.allow)), str(int(decision.match_found)), str(decision.rule_index))))
        if reset:
            if self.state in ('evaluate', 'respond'):
                self.counts['canceled'] += 1
            self.state = 'idle'
            self.rules = [Rule() for _ in range(self.n)]
            self.pending_decision = None
        elif self.state == 'idle':
            if mode:
                self.state = 'configure'
            elif request:
                self.counts['accepted'] += 1
                self.pending_decision = decision
                # Timing follows the policy result, not a duplicated comparator scan.
                self.remaining = (1 if self.architecture == 'parallel' else
                                  decision.rule_index + 1 if decision.match_found else self.n)
                self.state = 'evaluate'
        elif self.state == 'evaluate':
            self.remaining -= 1
            if self.remaining == 0:
                self.state = 'respond'
        elif self.state == 'respond':
            if ready:
                self.counts['completed'] += 1
                self.completed_decisions.append(self.pending_decision)
                self.pending_decision = None
                self.state = 'idle'
        elif self.state == 'configure':
            if not mode:
                self.state = 'idle'
            elif cfg_ready and write is not None:
                self.rules[index] = write
                self.counts['writes'] += 1

    def configure(self, rules):
        assert self.state == 'idle'
        self.tick(mode=1)
        for index, rule in enumerate(rules):
            self.tick(mode=1, write=rule, index=index, header=Header(0, 443, 6))
        # Invalid index must not alias a legal entry.
        self.tick(mode=1, write=Rule(enable=True, allow=True), index=self.n)
        self.tick(mode=0, write=Rule(enable=True, allow=True))

    def transact(self, header, stalls=0, injection=None):
        assert self.state == 'idle'
        self.tick(header=header, write=injection)
        # Change inputs after acceptance and attempt a forbidden write while evaluating.
        while self.state == 'evaluate':
            self.tick(header=Header(header.src_ip ^ 0xFFFFFFFF, header.dst_port ^ 65535, 1),
                      write=injection)
        for _ in range(stalls):
            self.tick(ready=0, header=Header(0, 0, 6), write=injection)
        self.tick(ready=1, header=Header(0, 0, 6), write=injection)


def make_trace(n, architecture='parallel'):
    t = Trace(n, architecture)
    h = Header(0x0A00002A, 8883, 6)
    poison = Rule(enable=True, allow=True)
    t.tick(reset=1, mode=1, write=poison, header=h)
    t.transact(h, stalls=3)  # Reset policy must deny.
    # Position-sensitive allow/deny and overlapping rules.
    for idx in range(n):
        rules = [Rule() for _ in range(n)]
        rules[idx] = Rule(src_value=h.src_ip, src_mask=0xFFFFFFFF,
                          port_low=8883, port_high=8883, protocol=6,
                          protocol_any=False, allow=bool(idx % 2 == 0), enable=True)
        t.configure(rules)
        t.transact(h, stalls=3, injection=poison)
        t.transact(Header(h.src_ip, 8882, 6), injection=poison)
        t.transact(Header(h.src_ip, 8883, 17))
        t.transact(Header(h.src_ip, 8883, 1))

    rules = [Rule(allow=False, enable=True)] + [poison for _ in range(n-1)]
    t.configure(rules)
    t.transact(h, stalls=5, injection=poison)

    # Mode requests must wait for a stalled response; attempted writes cannot mutate it.
    t.tick(header=h)
    t.tick(mode=1, write=poison)
    for _ in range(5):
        t.tick(mode=1, ready=0, write=poison, header=h)
    t.tick(mode=1, ready=1, write=poison)
    t.tick(mode=1, write=poison)  # Enter mode; this write is not accepted yet.
    t.tick(mode=0)
    t.transact(h)

    # Reset cancels both in-flight evaluation and a stalled response, and clears policy.
    t.tick(header=h)
    t.tick(reset=1, mode=1, write=poison)
    t.transact(h)
    t.tick(header=h)
    while t.state == 'evaluate':
        t.tick()
    t.tick(ready=0)
    t.tick(reset=1)
    t.transact(h)

    # Reset after several scanning cycles, while a configuration request is pending.
    if n > 2:
        t.tick(header=h)
        if architecture == 'sequential':
            for _ in range(n // 2):
                t.tick(mode=1, write=poison, ready=0)
        t.tick(reset=1, mode=1, write=poison)
        t.transact(h)

    rng = random.Random(20261016 + n)
    for _ in range(20):
        rules = []
        for _ in range(n):
            low, high = rng.choice(((0, 65535), (443, 443), (8000, 9000), (20, 10)))
            rules.append(Rule(rng.choice((0, 0x0A000000, h.src_ip)),
                              rng.choice((0, 0xFFFFFF00, 0xFFFFFFFF)), low, high,
                              rng.choice((6, 17)), bool(rng.getrandbits(1)),
                              bool(rng.getrandbits(1)), bool(rng.getrandbits(1))))
        t.configure(rules)
        for _ in range(30):
            hdr = Header(rng.choice((h.src_ip, rng.getrandbits(32))),
                         rng.choice((0, 443, 8000, 8883, 9000, 65535)),
                         rng.choice((6, 17, 1, 255)))
            t.transact(hdr, stalls=rng.randrange(5), injection=poison)
    # Both architectures replay this same completed transaction/policy corpus.
    # Later mixed-cycle fuzz intentionally accepts different streams due to readiness.
    t.common_completed = len(t.completed_decisions)
    # Mixed-cycle traffic covers configuration requests withdrawing before drain,
    # requests held while busy, backpressure, and repeated resets.
    for _ in range(3000):
        t.tick(reset=int(rng.randrange(100) == 0), mode=int(rng.randrange(4) == 0),
               write=rng.choice((None, poison, Rule())), index=rng.randrange(n + 1),
               header=rng.choice((None, h, Header(0, 443, 17))), ready=rng.getrandbits(1))
    # Drain with no cancellation at EOF.
    for _ in range(n + 5):
        t.tick()
    assert t.state == 'idle'
    assert t.counts['accepted'] == t.counts['completed'] + t.counts['canceled']
    assert t.counts['canceled'] >= 2
    return t


def main():
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    traces = {}
    for architecture in ('parallel', 'sequential'):
        for n in (1, 4, 8, 16):
            trace = make_trace(n, architecture)
            traces[architecture, n] = trace
            (build/f'engine_{architecture}_{n}.txt').write_text('\n'.join(trace.rows) + '\n', encoding='ascii')
            print(f'Generated engine architecture={architecture} rules={n} cycles={len(trace.rows)} {trace.counts}', flush=True)
    for n in (1, 4, 8, 16):
        a, b = traces['parallel', n], traces['sequential', n]
        assert a.common_completed == b.common_completed
        assert a.completed_decisions[:a.common_completed] == b.completed_decisions[:b.common_completed]
    if '--generate-only' in sys.argv:
        print('Generation only: RTL was NOT simulated.')
        return 0
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        print('BLOCKED: iverilog and vvp are required.', file=sys.stderr)
        return 2
    responses = {}
    for architecture in ('parallel', 'sequential'):
        for n in (1, 4, 8, 16):
            binary = build/f'engine_{architecture}_{n}.vvp'
            transcript = build/f'responses_{architecture}_{n}.txt'
            subprocess.run(['iverilog', '-g2012', '-Wall', '-s', 'tb_engine',
                            f'-Ptb_engine.N_RULES={n}',
                            f'-Ptb_engine.SEQUENTIAL={int(architecture == "sequential")}',
                            '-o', str(binary), str(ROOT/'rtl/gateshield_parallel_core.v'),
                            str(ROOT/'rtl/gateshield_parallel.v'),
                            str(ROOT/'rtl/gateshield_sequential.v'), str(ROOT/'tests/tb_engine.v')],
                           check=True, timeout=60)
            subprocess.run(['vvp', str(binary),
                            f'+vectors={build/f"engine_{architecture}_{n}.txt"}',
                            f'+responses={transcript}'], check=True, timeout=60)
            rows = [tuple(map(int, row.split())) for row in transcript.read_text().splitlines()]
            trace = traces[architecture, n]
            expected = [(int(d.allow), int(d.match_found), d.rule_index) for d in trace.completed_decisions]
            assert [row[:3] for row in rows] == expected, (architecture, n, 'response stream differs')
            for row in rows:
                expected_latency = (1 if architecture == 'parallel' else row[2] + 1 if row[1] else n)
                assert row[3] == expected_latency, (architecture, n, row, 'latency differs')
            responses[architecture, n] = rows[:trace.common_completed]
    with (build/'latency_comparison.csv').open('w', newline='', encoding='ascii') as f:
        writer = csv.writer(f)
        writer.writerow(('rules', 'architecture', 'common_transactions', 'min_cycles', 'max_cycles', 'mean_cycles'))
        for n in (1, 4, 8, 16):
            assert ([row[:3] for row in responses['parallel', n]] ==
                    [row[:3] for row in responses['sequential', n]])
            print(f'PASS cross-architecture replay rules={n} completed={len(responses["parallel", n])}')
            for architecture in ('parallel', 'sequential'):
                values = [row[3] for row in responses[architecture, n]]
                writer.writerow((n, architecture, len(values), min(values), max(values), sum(values)/len(values)))
    print('Latency CSV describes this synthetic replay corpus, not real network traffic.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
