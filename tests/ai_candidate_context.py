"""Deterministic HTTP/context contract checks against the disposable candidate."""

import argparse
import tempfile
import time
from pathlib import Path

from ai_candidate_support import Capture, close, start
from integration import wait


def markdown_check(candidate, checkout):
    source = "# Local AI\n\nUse local models for \n\nKeep this suffix."
    expected = source.replace("models for ", "models for both completion types.")

    def reply(row):
        prefix = (
            row["body"]["prompt"]
            .rsplit("<|file_sep|>updated/", 1)[-1]
            .partition("\n")[2]
        )
        assert expected.startswith(prefix), (candidate, prefix)
        text = expected[len(prefix) :]
        return {
            "response": text,
            "done": True,
            "choices": [{"text": text, "finish_reason": "stop"}],
        }

    capture = Capture(reply=reply)
    try:
        with tempfile.TemporaryDirectory(prefix="maya-candidate-markdown-") as temp:
            path = Path(temp, "README.md")
            path.write_text(source)
            nvim = start(candidate, checkout, capture.url, temp, path, "markdown")
            try:
                nvim.current.window.cursor = (3, 0)
                nvim.input("A")
                wait(nvim, 'vim.fn.mode()=="i"')
                nvim.exec_lua(
                    'require("maya.ai_context").refresh(); _G.eval_request(true)'
                )
                wait(nvim, "_G.eval_visible()")
                assert "Keep this suffix." in capture.rows[0]["body"]["prompt"]
                nvim.exec_lua("_G.eval_accept()")
                time.sleep(0.15)
                assert "\n".join(nvim.current.buffer[:]) == expected, candidate
                nvim.exec_lua("_G.eval_cancel()")
                print(
                    candidate,
                    "PASS: Markdown insertion preserves existing prefix and suffix",
                )
            finally:
                close(nvim, candidate)
    finally:
        capture.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cursortab", required=True, type=Path)
    args = parser.parse_args()
    for candidate in ("blink", "cursortab"):
        capture = Capture(
            reply=lambda row: {
                "response": "",
                "done": True,
                "choices": [{"text": "", "finish_reason": "stop"}],
            }
        )
        try:
            with tempfile.TemporaryDirectory(prefix="maya-candidate-context-") as temp:
                path = Path(temp, "fixture.py")
                path.write_text("value: int = 1\nresult = value + ")
                nvim = start(
                    candidate, args.cursortab, capture.url, temp, path, "python"
                )
                try:
                    nvim.current.window.cursor = (2, 0)
                    nvim.input("A")
                    wait(nvim, 'vim.fn.mode()=="i"')
                    nvim.exec_lua('require("maya.ai_context").refresh()')
                    time.sleep(0.1)
                    context = nvim.exec_lua('return require("maya.ai_context").get()')
                    assert context and "value: int" in context
                    nvim.exec_lua("_G.eval_request(true)")
                    deadline = time.monotonic() + 5
                    while not capture.rows and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert capture.rows, candidate
                    request = capture.rows[0]["body"]
                    assert context in request["prompt"], (candidate, request)
                    assert "<|file_sep|>lsp-context.txt" in request["prompt"]
                    assert capture.rows[0]["path"] == (
                        "/v1/completions"
                        if candidate == "cursortab"
                        else "/api/generate"
                    )
                    if candidate == "cursortab":
                        assert request["stream"] is True
                    nvim.exec_lua("_G.eval_cancel()")
                    nvim.current.buffer[0] = "value: int = 2"
                    assert (
                        nvim.exec_lua('return require("maya.ai_context").get()') == ""
                    )
                    nvim.exec_lua("_G.eval_reset()")
                    time.sleep(0.3)
                    count = len(capture.rows)
                    nvim.exec_lua("_G.eval_request(true)")
                    deadline = time.monotonic() + 5
                    while len(capture.rows) == count and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert len(capture.rows) > count, candidate
                    assert (
                        "lsp-context.txt" not in capture.rows[count]["body"]["prompt"]
                    )
                    assert "value: int = 2" in "\n".join(nvim.current.buffer[:])

                    if candidate == "cursortab":
                        # The extension bounds text and treats callback failure
                        # as missing context without preventing local inference.
                        for expression, expected_length in (
                            ('function() return string.rep("x",7000) end', 6000),
                            ('function() error("fixture callback failure") end', 0),
                        ):
                            nvim.exec_lua("_G.eval_cancel(); _G.eval_reset()")
                            time.sleep(0.3)
                            nvim.exec_lua(
                                'require("cursortab.config").get().source_context='
                                + expression
                            )
                            count = len(capture.rows)
                            nvim.exec_lua("_G.eval_request(true)")
                            deadline = time.monotonic() + 5
                            while (
                                len(capture.rows) == count
                                and time.monotonic() < deadline
                            ):
                                time.sleep(0.02)
                            assert len(capture.rows) > count
                            prompt = capture.rows[count]["body"]["prompt"]
                            assert ("x" * 6000 in prompt) == bool(expected_length)
                            assert "x" * 6001 not in prompt
                            if not expected_length:
                                assert "lsp-context.txt" not in prompt

                    # A late model reply must not revive a canceled preview or
                    # overwrite an edit made while inference was in flight.
                    def late_reply(row):
                        time.sleep(0.3)
                        return {
                            "response": "value: int = 2\nresult = value + 1",
                            "done": True,
                            "choices": [
                                {"text": "result = value + 1", "finish_reason": "stop"}
                            ],
                        }

                    capture.reply = late_reply
                    nvim.exec_lua("_G.eval_cancel(); _G.eval_reset()")
                    time.sleep(0.3)
                    count = len(capture.rows)
                    nvim.exec_lua("_G.eval_request(true)")
                    deadline = time.monotonic() + 5
                    while len(capture.rows) == count and time.monotonic() < deadline:
                        time.sleep(0.01)
                    assert len(capture.rows) > count
                    nvim.exec_lua("_G.eval_cancel()")
                    nvim.current.buffer[0] = "value: int = 99  # unsaved edit"
                    time.sleep(0.5)
                    assert not nvim.exec_lua("return _G.eval_visible()"), candidate
                    assert nvim.current.buffer[0] == "value: int = 99  # unsaved edit"
                    print(
                        candidate,
                        "PASS: cached context delivered; stale context omitted; late reply canceled; unsaved edit preserved",
                    )
                finally:
                    close(nvim, candidate)
        finally:
            capture.close()
        markdown_check(candidate, args.cursortab)


if __name__ == "__main__":
    main()
