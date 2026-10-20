# Corrected mapped results

Mapping target: 3 ns. Common evaluation clock: 5 ns. Times below refer to that common clock, not each design's estimated Tmin.

| Rules | Area par / seq (µm²) | Seq saving | Setup slack par / seq (ns) | Worst response par / seq (ns) | Worst acceptance interval par / seq (ns) |
|---|---:|---:|---:|---:|---:|
| 4 | 21,473.1 / 20,176.9 | 6.04% | +1.083 / +1.569 | 5 / 20 | 15 / 30 |
| 8 | 41,018.1 / 37,905.1 | 7.59% | +0.827 / +1.231 | 5 / 40 | 15 / 50 |
| 16 | 79,652.6 / 73,914.6 | 7.20% | +0.060 / +0.588 | 5 / 80 | 15 / 90 |

## Synthetic-corpus average at the common clock

| Rules | Mean response par / seq (ns) | Mean unstalled acceptance interval par / seq (ns) |
|---|---:|---:|
| 4 | 5.00 / 19.04 | 15.00 / 29.04 |
| 8 | 5.00 / 35.83 | 15.00 / 45.83 |
| 16 | 5.00 / 69.93 | 15.00 / 79.93 |

These averages describe the common synthetic transaction corpus; they do not establish real-traffic behavior. Intervals assume no receiver stalls. Area is summed library cell area. All timing is pre-layout with ideal wires and clock at one typical corner; no power or signoff claim.
