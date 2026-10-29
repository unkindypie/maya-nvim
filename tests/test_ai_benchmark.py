"""Protect benchmark scoring from false success and fixture drift."""

import unittest

from ai_benchmark import equivalent, fixtures
from ai_benchmark_report import latency


class BenchmarkTest(unittest.TestCase):
    def test_inventory(self):
        cases = fixtures()
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({case["id"] for case in cases}), 24)
        for language in ("python", "lua", "typescript"):
            group = [case for case in cases if case["language"] == language]
            self.assertEqual(
                [
                    sum(c["kind"] == k for c in group)
                    for k in ("insert", "edit", "quiet")
                ],
                [4, 2, 2],
            )
            for case in group:
                self.assertTrue(
                    equivalent(case["expected"], case["expected"], language)
                )
                self.assertEqual(
                    equivalent(case["source"], case["expected"], language),
                    case["kind"] == "quiet",
                )

    def test_formatting_is_not_a_quality_failure(self):
        self.assertTrue(
            equivalent("local count = # values", "local count=#values", "lua")
        )
        self.assertTrue(equivalent("x = 'local'", 'x="local"', "python"))

    def test_semantic_changes_and_truncation_fail(self):
        self.assertFalse(
            equivalent('local mode = "normal"', 'local mode = "local"', "lua")
        )
        self.assertFalse(
            equivalent(
                "local function add(a,b) return a+b",
                "local function add(a,b) return a+b end",
                "lua",
            )
        )
        self.assertFalse(
            equivalent("return value.upper()", "return value.lower()", "python")
        )

    def test_nearest_rank_p95_and_empty(self):
        self.assertEqual(latency(list(range(1, 21)))["p95_ms"], 19)
        self.assertIsNone(latency([])["p95_ms"])


if __name__ == "__main__":
    unittest.main()
