import unittest
from scripts.check_mapping import timing_metrics, ABC_LOAD_FF, LOAD_PF


class MappingMetricsTests(unittest.TestCase):
    def test_parallel_response_is_not_acceptance_interval(self):
        result = timing_metrics('parallel', 16, 4.937, 5.0, True)
        self.assertEqual(result['worst_response_latency_at_min_period_ns'], 4.937)
        self.assertEqual(result['worst_acceptance_interval_at_min_period_ns'], 14.811)

    def test_sequential_common_clock_is_separate(self):
        result = timing_metrics('sequential', 16, 4.349, 5.0, True)
        self.assertEqual(result['worst_response_latency_at_min_period_ns'], 69.584)
        self.assertEqual(result['worst_acceptance_interval_at_min_period_ns'], 78.282)
        self.assertEqual(result['worst_response_latency_at_eval_ns'], 80.0)
        self.assertEqual(result['worst_acceptance_interval_at_eval_ns'], 90.0)

    def test_failed_clock_is_not_reported_as_operating_point(self):
        result = timing_metrics('parallel', 16, 5.569, 5.0, False)
        self.assertEqual(result['worst_response_latency_at_eval_ns'], '')
        self.assertEqual(result['worst_acceptance_interval_at_eval_ns'], '')

    def test_abc_and_sta_load_units_agree(self):
        self.assertEqual(ABC_LOAD_FF, 10.0)
        self.assertEqual(LOAD_PF, .010)

    def test_invalid_inputs(self):
        for args in (('bad', 4, 5., 5., True), ('parallel', 0, 5., 5., True),
                     ('parallel', 4, -1., 5., True)):
            with self.assertRaises(ValueError):
                timing_metrics(*args)
