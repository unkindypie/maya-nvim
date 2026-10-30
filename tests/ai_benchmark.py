"""Opt-in editor quality benchmark; JSONL goes to stdout, never saved preferences.

Run with MAYA_NVIM_TEST_OLLAMA=1 bin/mvim-compatible environment and pynvim.
Exact expected buffers deliberately penalize unrelated edits. This small synthetic
suite is a regression gate, not a general model ranking. Context fidelity is
validated separately by ai_shared_context.py and ai_annotations.py.
"""

import ast
import json
import re
import urllib.request


def fixtures():
    """Four insertions, two corrections, two abstentions per language."""
    sources = {
        "python": [
            ("def add(a: int, b: int) -> int:\n    return ", "a + b"),
            ("values = [1, 2, 3]\ntotal = sum(", "values)"),
            ('name = "maya"\nupper = name.', "upper()"),
            ('from typing import Literal\nmode: Literal["local"] = ', '"local"'),
        ],
        "lua": [
            ("local function add(a, b)\n  return ", "a + b\nend"),
            ('local name = "maya"\nlocal upper = string.upper(', "name)"),
            ("local values = {1, 2, 3}\nlocal count = #", "values"),
            ('---@type "local"\nlocal mode = ', '"local"'),
        ],
        "typescript": [
            ("function add(a: number, b: number): number {\n  return ", "a + b;\n}"),
            ('const name = "maya";\nconst upper = name.', "toUpperCase();"),
            ("const values = [1, 2, 3];\nconst count = values.", "length;"),
            ('const mode: "local" = ', '"local";'),
        ],
    }
    corrections = {
        "python": [
            ("value = 'maya'\nupper = value.uper()", "upper"),
            ("values = [1, 2]\ncount = lenght(values)", "length"),
        ],
        "lua": [
            ("local value = 'maya'\nlocal upper = string.uper(value)", "upper"),
            ("local values = {1, 2}\nlocal count = table.lenght(values)", "length"),
        ],
        "typescript": [
            ("const value = 'maya';\nconst upper = value.toUperCase();", "upper"),
            ("const values = [1, 2];\nconst count = values.lenght;", "length"),
        ],
    }
    out = []
    for language, cases in sources.items():
        for i, (source, suffix) in enumerate(cases):
            out.append(
                {
                    "id": f"{language}-insert-{i}",
                    "language": language,
                    "kind": "insert",
                    "source": source,
                    "expected": source + suffix,
                }
            )
        for i, (source, change) in enumerate(corrections[language]):
            expected = source.replace("uper", "upper").replace("Uper", "Upper")
            if change == "length":
                expected = (
                    source.replace("lenght(values)", "len(values)")
                    if language == "python"
                    else source.replace("table.lenght(values)", "#values")
                    if language == "lua"
                    else source.replace("lenght", "length")
                )
            out.append(
                {
                    "id": f"{language}-edit-{i}",
                    "language": language,
                    "kind": "edit",
                    "source": source,
                    "expected": expected,
                }
            )
        for i, source in enumerate(
            [cases[0][0] + cases[0][1], cases[3][0] + cases[3][1]]
        ):
            out.append(
                {
                    "id": f"{language}-quiet-{i}",
                    "language": language,
                    "kind": "quiet",
                    "source": source,
                    "expected": source,
                }
            )
    return out


def equivalent(actual, expected, language):
    """Ignore formatting, not identifiers, literals or missing syntax."""
    if language == "python":
        try:
            return ast.dump(ast.parse(actual)) == ast.dump(ast.parse(expected))
        except SyntaxError:
            return False
    pattern = (
        r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]"
    )
    return re.findall(pattern, actual) == re.findall(pattern, expected)


def api(endpoint, path):
    with urllib.request.urlopen(endpoint + path, timeout=5) as response:
        return json.load(response)
