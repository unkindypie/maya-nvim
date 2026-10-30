"""Opt-in, paired local candidate trials. Output JSONL belongs outside the repo."""

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from ai_benchmark import api
from ai_candidate_cases import cases, correct
from ai_candidate_support import Capture, close, start
from integration import wait

LSP = {
    "python": ["ty", "server"],
    "typescript": ["typescript-language-server", "--stdio"],
    "lua": ["lua-language-server"],
}


def trial(nvim, case, capture, manual=False, candidate="blink"):
    nvim.exec_lua("_G.eval_cancel()")
    nvim.exec_lua("_G.eval_reset()")
    time.sleep(0.3)
    nvim.input("<Esc>")
    wait(nvim, 'vim.fn.mode()=="n"')
    nvim.exec_lua(
        "vim.api.nvim_buf_set_lines(0,0,-1,false,...)", case["source"].split("\n")
    )
    before = case["source"][: case["cursor"]]
    row, col = before.count("\n") + 1, len(before.rsplit("\n", 1)[-1])
    nvim.current.window.cursor = (
        row,
        max(0, col if col < len(nvim.current.buffer[row - 1]) else col - 1),
    )
    if case["kind"] == "insert":
        nvim.input("A" if col == len(nvim.current.buffer[row - 1]) else "i")
        wait(nvim, 'vim.fn.mode()=="i"')
    nvim.exec_lua('require("maya.ai_context").refresh()')
    time.sleep(0.45)
    context = nvim.exec_lua('return require("maya.ai_context").get()')
    baseline = len(capture.rows)
    t0 = time.monotonic()
    if manual:
        time.sleep(0.2 if case["kind"] == "insert" else 0.65)
    nvim.exec_lua("_G.eval_request(...)", manual)
    preview = None
    settled = False
    ready = None
    while time.monotonic() - t0 < 12:
        visible, pending = nvim.exec_lua(
            "return {_G.eval_visible(),_G.eval_pending() or false}"
        )
        now = time.monotonic()
        if visible and preview is None:
            preview = (now - t0) * 1000
        rows = capture.rows[baseline:]
        # Wait until the stream is complete before accepting a partial preview.
        if rows and all("finished" in r for r in rows) and not pending:
            if ready is None:
                ready = (now - t0) * 1000
            if now - max(r["finished"] for r in rows) > 0.12:
                settled = True
                break
        time.sleep(0.01)
    elapsed = (time.monotonic() - t0) * 1000
    visible = nvim.exec_lua("return _G.eval_visible()")
    before_accept = len(capture.rows)
    if visible:
        nvim.exec_lua("_G.eval_accept()")
        time.sleep(0.15)
    actual = "\n".join(nvim.current.buffer[:])
    nvim.exec_lua("_G.eval_cancel()")
    post_accept_requests = len(capture.rows) - before_accept
    rows = capture.rows[baseline:before_accept]
    success = (
        correct(actual, case) and settled and not any(r.get("error") for r in rows)
    )
    if case["kind"] == "quiet":
        success = success and preview is None
    return {
        "case": case["id"],
        "kind": case["kind"],
        "split": case["split"],
        "visible": preview is not None,
        "preview_ms": preview,
        "elapsed_ms": elapsed,
        "correct": success,
        "safe_preview_ms": ready if success and visible else None,
        "unchanged": actual == case["source"],
        "actual": actual,
        "timed_out": not settled,
        "context": context,
        "post_accept_requests": post_accept_requests,
        "requests": [
            {
                **r,
                "started": r["started"] - t0,
                "finished": r.get("finished", time.monotonic()) - t0,
            }
            for r in rows
        ],
        "overlap": any(
            a["started"] < b.get("finished", float("inf"))
            and b["started"] < a.get("finished", float("inf"))
            for i, a in enumerate(rows)
            for b in rows[i + 1 :]
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cursortab", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--cases", nargs="*")
    parser.add_argument(
        "--candidates",
        nargs="+",
        default=["cursortab"],
        choices=["cursortab"],
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        default=True,
        help="Controlled explicit requests (default); use ai_candidate_typing.py for native events",
    )
    parser.add_argument("--no-lsp", action="store_true")
    parser.add_argument("--context-chars", type=int, default=6000)
    parser.add_argument("--buffer-stream", action="store_true")
    args = parser.parse_args()
    if os.environ.get("MAYA_NVIM_TEST_OLLAMA") != "1":
        parser.error("Set MAYA_NVIM_TEST_OLLAMA=1")
    unknown = set(args.cases or []) - {case["id"] for case in cases()}
    if unknown:
        parser.error("Unknown cases: " + ", ".join(sorted(unknown)))
    if args.context_chars < 1 or args.context_chars > 6000:
        parser.error("Context budget must be between 1 and 6000 bytes")
    if args.repetitions < 1:
        parser.error("Repetitions must be positive")
    print(
        json.dumps(
            {
                "metadata": api(args.endpoint, "/api/tags"),
                "cursortab": subprocess.check_output(
                    ["git", "-C", str(args.cursortab), "rev-parse", "HEAD"], text=True
                ).strip(),
                "options": {**vars(args), "cursortab": str(args.cursortab)},
            }
        ),
        flush=True,
    )
    capture = Capture(args.endpoint, buffer_stream=args.buffer_stream)
    try:
        for index, case in enumerate(cases()):
            if args.cases and case["id"] not in args.cases:
                continue
            # Alternate the first candidate by case; never run inference jobs in parallel.
            order = args.candidates if index % 2 == 0 else args.candidates[::-1]
            for candidate in order:
                with tempfile.TemporaryDirectory(prefix="maya-candidate-") as temp:
                    ext = {"python": "py", "lua": "lua", "typescript": "ts"}[
                        case["language"]
                    ]
                    source = Path(temp, "fixture." + ext)
                    source.write_text(case["source"])
                    for filename, content in case.get("files", {}).items():
                        Path(temp, filename).write_text(content)
                    if ext == "ts":
                        Path(temp, "tsconfig.json").write_text(
                            '{"compilerOptions":{"strict":true},"include":["*.ts"]}'
                        )
                    nvim = start(
                        candidate,
                        args.cursortab,
                        capture.url,
                        temp,
                        source,
                        case["language"],
                        context_chars=args.context_chars,
                    )
                    try:
                        if not args.no_lsp:
                            cmd = LSP[case["language"]].copy()
                            cmd[0] = str(
                                Path.home()
                                / ".local/share/maya-nvim/mason/bin"
                                / cmd[0]
                            )
                            nvim.exec_lua(
                                'local cmd,root=...; vim.lsp.start({name="candidate-context",cmd=cmd,root_dir=root,settings={Lua={workspace={checkThirdParty=false},diagnostics={enable=false}}}})',
                                cmd,
                                temp,
                            )
                            wait(nvim, "#vim.lsp.get_clients({bufnr=0})>0")
                            time.sleep(1.5)
                        for sample in range(args.repetitions + 1):
                            result = trial(nvim, case, capture, args.manual, candidate)
                            print(
                                json.dumps(
                                    dict(candidate=candidate, sample=sample, **result)
                                ),
                                flush=True,
                            )
                    finally:
                        close(nvim, candidate)
    finally:
        capture.close()


if __name__ == "__main__":
    main()
