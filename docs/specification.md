# GateShield specification v0.1

## Scope and threat model

Evaluate trusted, parsed TCP/UDP header fields against a trusted configurable rule table. An adversary may choose any supported header and arrival sequence. Parsing, authentication, payload inspection, and packet forwarding are outside this block. Source addresses are not authenticated identities.

The surrounding system must never forward based on an invalid or unfinished decision. This requirement will be modeled by a registered interface in milestone 2; the current core only computes a combinational policy result.

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

## Planned transactional wrapper

One outstanding request. Acceptance occurs at req_valid && req_ready. Capture fields at acceptance; subsequent input changes cannot affect that transaction. Hold response data and valid until rsp_ready. Do not accept a replacement request on the response-consumption edge in the initial implementation; document the resulting initiation interval.

Synchronous active-high reset cancels pending transactions, clears response valid, and disables all rules. Reset takes priority over every handshake. Transaction accounting properties explicitly allow cancellation by reset.

Configuration mode blocks new requests. Enter only after an accepted request and its response have drained. Writes are accepted only in configuration mode, one whole rule at a time, with index bounds checking. Policy remains stable during evaluation and pending response. Service is interrupted during updates. No claim of atomic live policy replacement is made.

## Measurement boundaries

Do not compare this core's combinational latency with a complete sequential engine. Compare complete wrappers and report core breakdowns separately. Register-based rule storage and rule-selection multiplexers count toward area. Timing requires a mapped library and explicit constraints; generic logic depth is not frequency. Toggle counts are not watts.
