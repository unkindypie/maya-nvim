"""Native scheduling smoke trials using real input, not synthetic TextChanged."""

import argparse
import json
import tempfile
import time
from pathlib import Path

from ai_candidate_cases import cases, correct
from ai_candidate_support import Capture, close, start
from integration import wait


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cursortab", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Deterministic native-event contract test; no model inference",
    )
    parser.add_argument(
        "--lsp", action="store_true", help="Attach real language servers before typing"
    )
    args = parser.parse_args()
    import os

    if not args.fake and os.environ.get("MAYA_NVIM_TEST_OLLAMA") != "1":
        parser.error("Set MAYA_NVIM_TEST_OLLAMA=1")
    corpus = cases()

    def fixture_reply(row):
        prompt = row["body"]["prompt"]
        current = (
            prompt.rsplit("<|file_sep|>current/", 1)[1]
            .partition("\n")[2]
            .split("<|file_sep|>updated/", 1)[0]
            .replace("<|cursor|>", "")
            .rstrip("\n")
        )
        prefix = prompt.rsplit("<|file_sep|>updated/", 1)[1].partition("\n")[2]
        expected = next(
            (c["expected"] for c in corpus if c["source"] == current), current
        )
        assert expected.startswith(prefix), (prefix, expected)
        answer = expected[len(prefix) :]
        return {
            "response": answer,
            "done": True,
            "choices": [{"text": answer, "finish_reason": "stop"}],
        }

    capture = Capture(reply=fixture_reply if args.fake else None)
    try:
        selected = [
            c
            for c in corpus
            if c["id"]
            in {
                f"{language}-{kind}-0"
                for language in ("lua", "python", "typescript")
                for kind in ("insert", "edit", "quiet")
            }
        ]
        for case in selected:
            for candidate in ("cursortab",):
                for sample in range(args.repetitions):
                    with tempfile.TemporaryDirectory(prefix="maya-native-") as temp:
                        ext = {"python": "py", "lua": "lua", "typescript": "ts"}[
                            case["language"]
                        ]
                        path = Path(temp, "fixture." + ext)
                        # Type a short suffix (including non-whitespace), then optionally leave Insert.
                        count = min(5, len(case["source"].rsplit("\n", 1)[-1]))
                        initial = case["source"][:-count]
                        path.write_text(initial + "\n")
                        nvim = start(
                            candidate,
                            args.cursortab,
                            capture.url,
                            temp,
                            path,
                            case["language"],
                        )
                        try:
                            if args.lsp:
                                from ai_candidates import LSP

                                cmd = LSP[case["language"]].copy()
                                cmd[0] = str(
                                    Path.home()
                                    / ".local/share/maya-nvim/mason/bin"
                                    / cmd[0]
                                )
                                nvim.exec_lua(
                                    'local cmd,root=...; vim.lsp.start({name="native-context",cmd=cmd,root_dir=root,settings={Lua={workspace={checkThirdParty=false},diagnostics={enable=false}}}})',
                                    cmd,
                                    temp,
                                )
                                wait(nvim, "#vim.lsp.get_clients({bufnr=0})>0")
                                time.sleep(1.5)
                            nvim.current.window.cursor = (len(initial.split("\n")), 0)
                            nvim.exec_lua(
                                'pcall(function() require("nvim-autopairs").disable() end); _G.eval_enable()'
                            )
                            if candidate == "cursortab":
                                # Establish the already-saved fixture before timing.
                                # Otherwise first-sync no-edit suppression treats
                                # the first typed change as its initial checkpoint.
                                nvim.exec_lua(
                                    'require("cursortab.daemon").send_event("file_saved")'
                                )
                                time.sleep(0.1)
                            nvim.input("A")
                            wait(nvim, 'vim.fn.mode()=="i"')
                            time.sleep(0.05)
                            offset = len(capture.rows)
                            t0 = time.monotonic()
                            nvim.input(case["source"][-count:])
                            if case["kind"] != "insert":
                                nvim.input("<Esc>")
                                wait(nvim, 'vim.fn.mode()=="n"')
                            nvim.exec_lua('require("maya.ai_context").refresh()')
                            first = None
                            while time.monotonic() - t0 < 4:
                                visible = nvim.exec_lua("return _G.eval_visible()")
                                if visible and first is None:
                                    first = (time.monotonic() - t0) * 1000
                                rows = capture.rows[offset:]
                                if (
                                    rows
                                    and all("finished" in r for r in rows)
                                    and not nvim.exec_lua("return _G.eval_pending()")
                                ) and (
                                    time.monotonic() - max(r["finished"] for r in rows)
                                    > 0.12
                                ):
                                    break
                                time.sleep(0.01)
                            before_accept = len(capture.rows)
                            if nvim.exec_lua("return _G.eval_visible()"):
                                nvim.exec_lua("_G.eval_accept()")
                                time.sleep(0.15)
                            actual = "\n".join(nvim.current.buffer[:])
                            log = Path(temp, "cursortab/cursortab.log")
                            diagnostics = (
                                log.read_text()[-4000:]
                                if not rows and log.exists()
                                else ""
                            )
                            nvim.exec_lua("_G.eval_cancel()")
                            if args.fake:
                                assert correct(actual, case) and (
                                    case["kind"] != "quiet" or first is None
                                ), (candidate, case["id"], actual, diagnostics)
                            print(
                                json.dumps(
                                    {
                                        "candidate": candidate,
                                        "case": case["id"],
                                        "sample": sample,
                                        "preview_ms": first,
                                        "correct": correct(actual, case)
                                        and (case["kind"] != "quiet" or first is None),
                                        "requests": before_accept - offset,
                                        "diagnostics": diagnostics,
                                        "actual": actual,
                                    }
                                ),
                                flush=True,
                            )
                        finally:
                            close(nvim, candidate)
    finally:
        capture.close()


if __name__ == "__main__":
    main()
