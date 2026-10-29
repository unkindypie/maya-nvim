import json
import unittest

from ai_candidate_cases import cases, correct
from ai_candidate_report import no_preview_category, response_text


class CandidateCorpusTests(unittest.TestCase):
    def test_balanced_expansion_and_split(self):
        corpus = cases()
        self.assertEqual(len(corpus), 60)
        self.assertEqual(len({case["id"] for case in corpus}), 60)
        expanded = [case for case in corpus if case["split"] != "original"]
        for language in ("lua", "python", "typescript"):
            for kind in ("insert", "edit", "quiet"):
                selected = [
                    c
                    for c in expanded
                    if c["language"] == language and c["kind"] == kind
                ]
                self.assertEqual(len(selected), 4)
                self.assertEqual(sum(c["split"] == "held-out" for c in selected), 2)

    def test_answers_and_cursor_are_well_formed(self):
        for case in cases():
            self.assertLessEqual(case["cursor"], len(case["source"]))
            self.assertTrue(correct(case["expected"], case), case["id"])
            self.assertNotIn("«cursor»", case["source"])

    def test_narrow_format_variants_preserve_syntax_and_literals(self):
        lua = {"language": "lua", "expected": 'local mode = "local"'}
        self.assertTrue(correct("local mode = 'local'", lua))
        self.assertFalse(correct('local mode = "normal"', lua))
        self.assertFalse(
            correct(
                "local function add(a,b) return a+b",
                {
                    "language": "lua",
                    "expected": "local function add(a,b) return a+b end",
                },
            )
        )
        ts = {"language": "typescript", "expected": 'const mode: "local" = "local";'}
        self.assertTrue(correct("const mode: 'local' = 'local'", ts))
        self.assertFalse(correct('const mode: "local" = "normal";', ts))


class CandidateResponseTests(unittest.TestCase):
    def test_stream_fragments_and_finish_marker(self):
        request = {
            "chunks": [
                'data: {"choices":[{"text":"return "}]}\n\n',
                'data: {"choices":[{"text":"a + b"}]}\n\n',
                "data: [DONE]\n\n",
            ]
        }
        self.assertEqual(response_text(request), "return a + b")

    def test_prefill_noop_is_distinct_from_unshown_changed_text(self):
        request = {
            "body": {
                "prompt": "<|file_sep|>current/file.py\nhead\ntail<|cursor|>\n<|file_sep|>updated/file.py\nhead\n"
            },
            "chunks": [json.dumps({"response": "tail\n"})],
        }
        row = {"visible": False, "requests": [request]}
        self.assertEqual(no_preview_category(row), "model_noop")
        request["chunks"] = [json.dumps({"response": "changed\n"})]
        self.assertEqual(no_preview_category(row), "nonempty_unshown_response")
        row["visible"] = True
        self.assertIsNone(no_preview_category(row))


if __name__ == "__main__":
    unittest.main()
