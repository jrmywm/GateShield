# GateShield specification v0.2

## Scope and threat model

Evaluate trusted, parsed TCP/UDP header fields against a trusted configurable rule table. An adversary may choose any supported header and arrival sequence. Parsing, authentication, payload inspection, and packet forwarding are outside this block. Source addresses are not authenticated identities.

The surrounding system must never forward based on an invalid or unfinished decision. The registered engine supplies a valid/ready response interface. It evaluates headers; the surrounding forwarding logic must enforce the decision.

## Policy semantics

Header: unsigned source IPv4 address (32 bits), destination port (16 bits), protocol (8 bits). TCP=6, UDP=17. Other protocols are denied even if a wildcard rule exists.

Rules are ordered by ascending array index. First enabled matching rule wins. No match means deny. An explicit deny rule still returns match_found=1. No-match returns allow=0, match_found=0, rule_index=0; rule_index is meaningful only when match_found=1.

A match requires:

1. Rule enabled.
2. `(src_ip & src_mask) == (src_value & src_mask)`; arbitrary masks are supported, not only CIDR masks.
3. `port_low <= dst_port <= port_high`. Reversed ranges match nothing.
4. `protocol_any` or exact protocol equality.

All comparisons are unsigned. A zero source mask matches every source. A port range of 0..65535 matches every port. Wildcard protocol means either supported protocol, never arbitrary unsupported protocols.

## Rule packing

Each rule is 108 bits. Rule 0 occupies the least-significant 108 bits of the flattened table.

| Bits | Field |
|---|---|
| 31:0 | src_value |
| 63:32 | src_mask |
| 79:64 | port_low |
| 95:80 | port_high |
| 103:96 | protocol |
| 104 | protocol_any |
| 105 | allow |
| 106 | enable |
| 107 | reserved, ignored; software writes zero |

Supported production rule counts: 4, 8, 16. The initial simulation also exercises 1 rule to expose index-width edge cases.

## Registered transactional wrapper

One outstanding request. Acceptance occurs at req_valid && req_ready. Capture fields at acceptance; subsequent input changes cannot affect that transaction. Hold response data and valid until rsp_ready. Do not accept a replacement request on the response-consumption edge in the initial implementation; document the resulting initiation interval.

Synchronous active-high reset cancels pending transactions, clears response valid, and disables all rules. Reset takes priority over every handshake. Transaction accounting properties explicitly allow cancellation by reset.

Configuration mode blocks new requests. Enter only after an accepted request and its response have drained. Writes are accepted only in configuration mode, one whole rule at a time, with index bounds checking. Policy remains stable during evaluation and pending response. Service is interrupted during updates. No claim of atomic live policy replacement is made.

### Ports

| Group | Ports | Semantics |
|---|---|---|
| Clock/reset | clk, rst | Rising edge, synchronous active-high reset; initialize with reset before requests |
| Request | req_valid, req_ready, req_src_ip, req_dst_port, req_protocol | Acceptance at a rising edge where valid and ready are both high |
| Response | rsp_valid, rsp_ready, rsp_allow, rsp_match_found, rsp_rule_index | Receiver consumes at a rising edge where valid and ready are both high |
| Configuration mode | cfg_mode, cfg_active | Trusted level request and mode acknowledgement |
| Rule write | cfg_valid, cfg_ready, cfg_index, cfg_rule | Whole-rule write at a rising-edge handshake |

`cfg_mode` immediately suppresses request readiness. Hold it asserted until `cfg_active`, while allowing outstanding responses to drain. Mode entry does not accept a write on the entry edge. In active mode, writes require cfg_mode=1 and cfg_index<N_RULES. `CFG_INDEX_W=$clog2(N_RULES+1)` intentionally permits invalid indices even for power-of-two table sizes; these never assert cfg_ready or modify storage. Output rule indices use INDEX_W=max(1,$clog2(N_RULES)).

Deasserting cfg_mode blocks further writes immediately; the engine leaves active mode on the next rising edge. Withdrawal before mode entry cancels the mode request. Reset masks all handshake outputs immediately while asserted, and clears state/storage on a rising edge. Configuration must be repeated after reset. Rule bit 107 is cleared on writes.

Invalid response payloads are zero. Valid response payloads remain stable until consumption or reset. Input request fields may change after acceptance without affecting the captured transaction. Upstream producers should hold a pending valid request stable until accepted under normal ready/valid protocol operation.

### Parallel-engine cycle contract

If edge E0 accepts a request, edge E1 registers its decision and asserts rsp_valid after the edge. Edge E2 can consume the response at the earliest. Edge E3 can accept the next request. Thus response production latency is one clock period and unstalled initiation interval is three cycles. Backpressure can delay consumption indefinitely, so response consumption has no unconditional finite bound. Configuration requests do not cancel pending transactions. Reset does.

The engine uses IDLE, EVALUATE, RESPOND, and CONFIGURE states. All architectures in the later comparison must expose the same policy/update semantics; different response latencies are allowed and measured.

## Measurement boundaries

Do not compare this core's combinational latency with a complete sequential engine. Compare complete wrappers and report core breakdowns separately. Register-based rule storage and rule-selection multiplexers count toward area. Timing requires a mapped library and explicit constraints; generic logic depth is not frequency. Toggle counts are not watts.
