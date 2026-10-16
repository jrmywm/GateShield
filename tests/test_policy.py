import random
import unittest
from dataclasses import replace
from model.policy import Header, Rule, Decision, evaluate, pack_rule


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.h = Header(0x0A00002A, 8883, 6)
        self.r = Rule(0x0A000000, 0xFFFFFF00, 8883, 8883, 6, False, True, True)

    def test_default_deny_and_disabled(self):
        self.assertEqual(evaluate(self.h, []), Decision())
        self.assertEqual(evaluate(self.h, [replace(self.r, enable=False)]), Decision())

    def test_priority_and_explicit_deny(self):
        deny = replace(self.r, allow=False)
        self.assertEqual(evaluate(self.h, [deny, self.r]), Decision(False, True, 0))
        self.assertEqual(evaluate(self.h, [self.r, deny]), Decision(True, True, 0))

    def test_later_rule_index(self):
        self.assertEqual(evaluate(self.h, [Rule(), self.r]), Decision(True, True, 1))

    def test_mask_and_unmasked_rule_bits(self):
        self.assertTrue(evaluate(self.h, [replace(self.r, src_value=0x0A0000FF)]).allow)
        self.assertFalse(evaluate(replace(self.h, src_ip=0x0A000100), [self.r]).allow)
        self.assertTrue(evaluate(self.h, [replace(self.r, src_mask=0)]).allow)

    def test_port_boundaries_and_reversed_range(self):
        rule = replace(self.r, port_low=10, port_high=20)
        for port, expected in ((9, False), (10, True), (20, True), (21, False)):
            self.assertEqual(evaluate(replace(self.h, dst_port=port), [rule]).allow, expected)
        self.assertFalse(evaluate(self.h, [replace(self.r, port_low=9000)]).match_found)

    def test_protocol_and_wildcard(self):
        self.assertFalse(evaluate(replace(self.h, protocol=17), [self.r]).allow)
        wildcard = replace(self.r, protocol_any=True)
        self.assertTrue(evaluate(replace(self.h, protocol=17), [wildcard]).allow)
        for protocol in (0, 1, 255):
            self.assertEqual(evaluate(replace(self.h, protocol=protocol), [wildcard]), Decision())

    def test_unsigned_validation(self):
        for args in ((-1, 0, 6), (1 << 32, 0, 6), (0, 65536, 6), (0, 0, 256)):
            with self.assertRaises(ValueError):
                Header(*args)
        with self.assertRaises(ValueError):
            Rule(port_low=-1)

    def test_packing_against_explicit_fields(self):
        rule = Rule(0x12345678, 0xFFFFFFFF, 0xABCD, 0xEF01, 17, True, False, True)
        bits = f'{pack_rule(rule):0108b}'
        expected = '0' + '1' + '0' + '1' + f'{17:08b}{0xEF01:016b}{0xABCD:016b}{0xFFFFFFFF:032b}{0x12345678:032b}'
        self.assertEqual(bits, expected)

    def test_seeded_priority_and_disabled_invariance(self):
        rng = random.Random(20261016)
        for _ in range(1000):
            h = Header(rng.getrandbits(32), rng.randrange(65536), rng.choice((6, 17)))
            action = bool(rng.getrandbits(1))
            first = Rule(allow=action, enable=True)
            later = Rule(allow=not action, enable=True)
            self.assertEqual(evaluate(h, [Rule(), first, later]), Decision(action, True, 1))


if __name__ == '__main__':
    unittest.main()
