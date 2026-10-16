"""Independent functional policy model, deliberately without RTL timing state."""
from dataclasses import dataclass


def unsigned(value: int, width: int, name: str) -> None:
    if not isinstance(value, int) or not 0 <= value < (1 << width):
        raise ValueError(f"{name} must be an unsigned {width}-bit integer")


@dataclass(frozen=True)
class Header:
    src_ip: int
    dst_port: int
    protocol: int

    def __post_init__(self):
        for name, width in (("src_ip", 32), ("dst_port", 16), ("protocol", 8)):
            unsigned(getattr(self, name), width, name)


@dataclass(frozen=True)
class Rule:
    src_value: int = 0
    src_mask: int = 0
    port_low: int = 0
    port_high: int = 65535
    protocol: int = 0
    protocol_any: bool = True
    allow: bool = False
    enable: bool = False

    def __post_init__(self):
        for name, width in (("src_value", 32), ("src_mask", 32),
                            ("port_low", 16), ("port_high", 16), ("protocol", 8)):
            unsigned(getattr(self, name), width, name)
        for name in ("protocol_any", "allow", "enable"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be bool")


@dataclass(frozen=True)
class Decision:
    allow: bool = False
    match_found: bool = False
    rule_index: int = 0


def evaluate(header: Header, rules: list[Rule]) -> Decision:
    if header.protocol not in (6, 17):
        return Decision()
    for index, rule in enumerate(rules):
        if not rule.enable:
            continue
        if (header.src_ip ^ rule.src_value) & rule.src_mask:
            continue
        if not rule.port_low <= header.dst_port <= rule.port_high:
            continue
        if not rule.protocol_any and header.protocol != rule.protocol:
            continue
        return Decision(rule.allow, True, index)
    return Decision()


def pack_rule(rule: Rule) -> int:
    return (rule.src_value | rule.src_mask << 32 | rule.port_low << 64
            | rule.port_high << 80 | rule.protocol << 96
            | int(rule.protocol_any) << 104 | int(rule.allow) << 105
            | int(rule.enable) << 106)
