"""Preregistered candidate corpus. Expected answers must not be tuned to outputs."""

from ai_benchmark import equivalent, fixtures

CURSOR = "«cursor»"


def cases():
    result = []
    for case in fixtures():
        result.append({**case, "split": "original", "cursor": len(case["source"])})
    additions = {
        "python": [
            (
                "insert",
                "from schema import Mode\nmode: Mode = «cursor»",
                '"local"',
                {"schema.py": 'from typing import Literal\nMode = Literal["local"]\n'},
            ),
            (
                "insert",
                "def add(a: int, b: int) -> int:\n    return «cursor»\n\nassert add(2, 3) == 5",
                "a + b",
                {},
            ),
            (
                "insert",
                "values = [1, 2, 3]\ntotal = sum(«cursor»)\nprint(total)",
                "values",
                {},
            ),
            (
                "insert",
                "\n".join(f"constant_{i} = {i}" for i in range(180))
                + '\nname = "maya"\nupper = name.«cursor»',
                "upper()",
                {},
            ),
            (
                "edit",
                "items = [1, 2, 3]\ncount = len(items«cursor»",
                "items = [1, 2, 3]\ncount = len(items)",
                {},
            ),
            (
                "edit",
                "def add(a, b):\n    return a - b«cursor»\n\nassert add(2, 3) == 5",
                "def add(a, b):\n    return a + b\n\nassert add(2, 3) == 5",
                {},
            ),
            (
                "edit",
                'name = "maya"\nupper = name.uper()«cursor»\nprint(upper)',
                'name = "maya"\nupper = name.upper()\nprint(upper)',
                {},
            ),
            (
                "edit",
                "values = [1, 2]\ncount = lenght(values)«cursor»\nprint(count)",
                "values = [1, 2]\ncount = len(values)\nprint(count)",
                {},
            ),
            (
                "quiet",
                'from typing import Literal\nmode: Literal["local"] = "local"«cursor»',
                None,
                {},
            ),
            (
                "quiet",
                "def add(a, b):\n    return a + b«cursor»\n\nassert add(2, 3) == 5",
                None,
                {},
            ),
            (
                "quiet",
                "values = [1, 2, 3]\ntotal = sum(values)«cursor»\nprint(total)",
                None,
                {},
            ),
            (
                "quiet",
                "\n".join(f"constant_{i} = {i}" for i in range(180))
                + '\nname = "maya"\nupper = name.upper()«cursor»',
                None,
                {},
            ),
        ],
        "lua": [
            (
                "insert",
                '---@alias EvalMode "local"\n---@type EvalMode\nlocal mode = «cursor»',
                '"local"',
                {},
            ),
            (
                "insert",
                "local function add(a, b)\n  return «cursor»\nend\nassert(add(2, 3) == 5)",
                "a + b",
                {},
            ),
            (
                "insert",
                'local name = "maya"\nlocal upper = string.upper(«cursor»)\nprint(upper)',
                "name",
                {},
            ),
            (
                "insert",
                "\n".join(f"local constant_{i} = {i}" for i in range(180))
                + "\nlocal values = {1, 2}\nlocal count = #«cursor»",
                "values",
                {},
            ),
            (
                "edit",
                'local name = "maya"\nlocal upper = string.upper(name«cursor»',
                'local name = "maya"\nlocal upper = string.upper(name)',
                {},
            ),
            (
                "edit",
                "local function add(a, b)\n  return a - b«cursor»\nend\nassert(add(2, 3) == 5)",
                "local function add(a, b)\n  return a + b\nend\nassert(add(2, 3) == 5)",
                {},
            ),
            (
                "edit",
                'local name = "maya"\nlocal upper = string.uper(name)«cursor»\nprint(upper)',
                'local name = "maya"\nlocal upper = string.upper(name)\nprint(upper)',
                {},
            ),
            (
                "edit",
                "local values = {1, 2}\nlocal count = table.lenght(values)«cursor»\nprint(count)",
                "local values = {1, 2}\nlocal count = #values\nprint(count)",
                {},
            ),
            ("quiet", '---@type "local"\nlocal mode = "local"«cursor»', None, {}),
            (
                "quiet",
                "local function add(a, b)\n  return a + b«cursor»\nend\nassert(add(2, 3) == 5)",
                None,
                {},
            ),
            (
                "quiet",
                'local name = "maya"\nlocal upper = string.upper(name)«cursor»\nprint(upper)',
                None,
                {},
            ),
            (
                "quiet",
                "\n".join(f"local constant_{i} = {i}" for i in range(180))
                + "\nlocal values = {1, 2}\nlocal count = #values«cursor»",
                None,
                {},
            ),
        ],
        "typescript": [
            (
                "insert",
                'import type { Mode } from "./schema";\nconst mode: Mode = «cursor»',
                '"local";',
                {"schema.ts": 'export type Mode = "local";\n'},
            ),
            (
                "insert",
                "function add(a: number, b: number): number {\n  return «cursor»\n}\nconsole.assert(add(2, 3) === 5);",
                "a + b;",
                {},
            ),
            (
                "insert",
                'const name = "maya";\nconst upper = name.«cursor»;\nconsole.log(upper);',
                "toUpperCase()",
                {},
            ),
            (
                "insert",
                "\n".join(f"const constant_{i} = {i};" for i in range(180))
                + "\nconst values = [1, 2];\nconst count = values.«cursor»",
                "length;",
                {},
            ),
            (
                "edit",
                "const values = [1, 2];\nconst count = values.lenght;«cursor»",
                "const values = [1, 2];\nconst count = values.length;",
                {},
            ),
            (
                "edit",
                "function add(a: number, b: number): number {\n  return a - b;«cursor»\n}\nconsole.assert(add(2, 3) === 5);",
                "function add(a: number, b: number): number {\n  return a + b;\n}\nconsole.assert(add(2, 3) === 5);",
                {},
            ),
            (
                "edit",
                'const name = "maya";\nconst upper = name.toUperCase();«cursor»\nconsole.log(upper);',
                'const name = "maya";\nconst upper = name.toUpperCase();\nconsole.log(upper);',
                {},
            ),
            (
                "edit",
                "const values = [1, 2];\nconst count = values.lenght;«cursor»\nconsole.log(count);",
                "const values = [1, 2];\nconst count = values.length;\nconsole.log(count);",
                {},
            ),
            ("quiet", 'const mode: "local" = "local";«cursor»', None, {}),
            (
                "quiet",
                "function add(a: number, b: number): number {\n  return a + b;«cursor»\n}\nconsole.assert(add(2, 3) === 5);",
                None,
                {},
            ),
            (
                "quiet",
                'const name = "maya";\nconst upper = name.toUpperCase();«cursor»\nconsole.log(upper);',
                None,
                {},
            ),
            (
                "quiet",
                "\n".join(f"const constant_{i} = {i};" for i in range(180))
                + "\nconst values = [1, 2];\nconst count = values.length;«cursor»",
                None,
                {},
            ),
        ],
    }
    for language, entries in additions.items():
        for i, (kind, marked, answer, files) in enumerate(entries):
            offset = marked.index(CURSOR)
            source = marked.replace(CURSOR, "")
            expected = (
                marked.replace(CURSOR, answer) if kind == "insert" else answer or source
            )
            result.append(
                {
                    "id": f"{language}-expanded-{i}",
                    "language": language,
                    "kind": kind,
                    "source": source,
                    "expected": expected,
                    "cursor": offset,
                    "files": files,
                    "split": "development" if i % 2 == 0 else "held-out",
                }
            )
    return result


def correct(actual, case):
    # Only explicitly preregistered formatting variations: quote style for these
    # simple literals and optional statement-ending TypeScript semicolons.
    expected = case["expected"]
    if case["language"] in ("lua", "typescript"):
        actual, expected = (
            text.replace("'maya'", '"maya"').replace("'local'", '"local"')
            for text in (actual, expected)
        )
    if case["language"] == "typescript":
        import re

        actual, expected = (
            re.sub(r";(?=\s*(?:\n|$|}))", "", text) for text in (actual, expected)
        )
    return equivalent(actual, expected, case["language"])
