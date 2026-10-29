"""Opt-in editor quality benchmark; JSONL goes to stdout, never saved preferences.

Run with MAYA_NVIM_TEST_OLLAMA=1 bin/mvim-compatible environment and pynvim.
Exact expected buffers deliberately penalize unrelated edits. This small synthetic
suite is a regression gate, not a general model ranking. Context fidelity is
validated separately by ai_shared_context.py and ai_annotations.py.
"""

import argparse
import ast
import json
import os
import random
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


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


def main():
    import pynvim
    from integration import stop, wait

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["dual", "single", "completion-only"],
        choices=["dual", "single", "completion-only"],
    )
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--no-extra-lsp", action="store_true")
    parser.add_argument(
        "--blink-qwen",
        action="store_true",
        help="Experimental generic-provider Qwen completion at end of buffer only",
    )
    parser.add_argument(
        "--single-insert-delay",
        type=int,
        default=None,
        help="Experimental Insert-only delay; saved preferences stay unchanged",
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    if args.blink_qwen and args.modes != ["single"]:
        parser.error("--blink-qwen requires --modes single")
    if os.environ.get("MAYA_NVIM_TEST_OLLAMA") != "1":
        parser.error("Set MAYA_NVIM_TEST_OLLAMA=1 to run local model requests")
    os.environ.update(
        NVIM_APPNAME="maya-nvim",
        MAYA_NVIM_NO_INSTALL="1",
        MAYA_NVIM_NO_AI="1",
        MAYA_NVIM_NO_SESSION="1",
    )
    print(
        json.dumps(
            {
                "metadata": api(args.endpoint, "/api/tags"),
                "options": vars(args),
                "commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "gpu": subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,memory.total,driver_version",
                        "--format=csv,noheader",
                    ],
                    text=True,
                ).strip(),
            }
        ),
        flush=True,
    )
    cases = fixtures()
    random.Random(17).shuffle(cases)
    with tempfile.TemporaryDirectory(prefix="maya-ai-benchmark-") as temp:
        for mode in args.modes:
            Path(temp, "ai.json").write_text(
                json.dumps(
                    {
                        "provider": "ollama",
                        "local_mode": mode,
                        "model": "qwen2.5-coder:1.5b-base-q8_0",
                        "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
                        "endpoint": args.endpoint,
                    }
                )
            )
            for case in cases:
                if (mode == "completion-only" or args.blink_qwen) and case[
                    "kind"
                ] != "insert":
                    continue
                # Fresh editor per case prevents cross-fixture edit history leakage.
                nvim = pynvim.attach(
                    "child",
                    argv=[
                        str(Path(__file__).resolve().parents[1] / "bin/mvim"),
                        "--embed",
                        "--headless",
                    ],
                )
                try:
                    nvim.ui_attach(110, 35, rgb=True)
                    nvim.command("enew")
                    nvim.exec_lua(
                        'local c=require("maya.user").config; c.ai_completion_debounce_ms=200; c.ai_next_edit_debounce_ms=650'
                    )
                    nvim.exec_lua(
                        'local p=...; local orig=vim.fn.stdpath; vim.fn.stdpath=function(k) return k=="state" and p or orig(k) end',
                        temp,
                    )
                    for sample in range(args.repetitions + 1):
                        nvim.input("<Esc>")
                        wait(nvim, 'vim.fn.mode()=="n"')
                        nvim.exec_lua(
                            'require("maya.ai").cancel(); vim.api.nvim_buf_set_lines(0,0,-1,false,...); vim.api.nvim_win_set_cursor(0,{1,0})',
                            case["source"].split("\n"),
                        )
                        nvim.exec_lua(
                            'vim.bo.filetype=...; require("maya.ai").select("ollama",false); require("maya.ai").cancel()',
                            case["language"],
                        )
                        if args.blink_qwen:
                            nvim.exec_lua("""
local edit=require("blink-edit")
local cfg=vim.deepcopy(require("blink-edit.config").get())
cfg.llm.provider="generic"
cfg.llm.model=require("maya.ai").model
cfg.llm.max_tokens=96
cfg.mode="completion"
cfg.providers.generic.prompt_template="<|fim_prefix|>{{current}}<|fim_suffix|><|fim_middle|>"
cfg.providers.generic.use_history=false
cfg.providers.generic.stop_tokens={"<|fim_suffix|>","<|fim_middle|>","<|endoftext|>","<|im_end|>"}
edit.reset()
edit.setup(cfg)
""")
                        if args.single_insert_delay is not None and mode == "single":
                            nvim.exec_lua(
                                'local delay=...; local user=require("maya.user"); if not user.benchmark_get then user.benchmark_get=user.get end; user.get=function(key) if key=="ai_next_edit_debounce_ms" and vim.api.nvim_get_mode().mode=="i" then return delay end; return user.benchmark_get(key) end',
                                args.single_insert_delay,
                            )
                        if args.no_extra_lsp and mode != "completion-only":
                            nvim.exec_lua(
                                'require("blink-edit.config").get().context.lsp.enabled=false'
                            )
                        nvim.current.window.cursor = (
                            len(case["source"].split("\n")),
                            max(0, len(case["source"].split("\n")[-1]) - 1),
                        )
                        if case["kind"] == "insert":
                            nvim.input("A")
                            wait(nvim, 'vim.fn.mode()=="i"')
                        nvim.exec_lua("""
_G.benchmark_requests={}
_G.benchmark_loads={}
local ai=require("maya.ai")
if ai.initialized.ollama then
 require("minuet.backends.openai_fim_compatible")
 local opts=require("minuet").config.provider_options.openai_fim_compatible
 if opts.get_text_fn and opts.get_text_fn.no_stream and not opts.benchmark_wrapped then
  opts.benchmark_wrapped=true
  local original=opts.get_text_fn.no_stream
  opts.get_text_fn.no_stream=function(body)
   table.insert(_G.benchmark_loads,{load_duration=body.load_duration,total_duration=body.total_duration})
   return original(body)
  end
 end
end
if ai.local_mode~="completion-only" then
 local transport=require("blink-edit.transport")
 if not transport.benchmark_wrapped then
  transport.benchmark_wrapped=true
  local original=transport.request
  transport.request=function(opts,cb)
   return original(opts,function(err,response)
    if response and response.body then
     local ok,body=true,response.body
     if type(body)=="string" then ok,body=pcall(vim.json.decode,body) end
     if ok then table.insert(_G.benchmark_loads,{load_duration=body.load_duration,total_duration=body.total_duration}) end
    end
    return cb(err,response)
   end)
  end
 end
end
for _,name in ipairs({"minuet.backends.openai_fim_compatible","blink-edit.backends"}) do
 local backend=package.loaded[name]
 if backend and not backend.benchmark_wrapped then
  backend.benchmark_wrapped=true
  local original=backend.complete
  backend.complete=function(opts,callback)
   local row={engine=name, started=vim.uv.hrtime()}
   table.insert(_G.benchmark_requests,row)
   return original(opts,function(...)
    row.finished=vim.uv.hrtime()
    if name=="blink-edit.backends" then
     row.error=select(1,...)
     local response=select(2,...)
     row.response=response and response.text
    else
     row.response=select(1,...)
    end
    return callback(...)
   end)
  end
 end
end
""")
                        t0 = time.monotonic()
                        nvim.exec_lua(
                            'require("maya.ai").cancel(); require("blink.cmp").hide(); require("maya.ai_coordinator").activity(true)'
                        )
                        visible = False
                        while time.monotonic() - t0 < 13:
                            state = nvim.exec_lua(
                                'local ai=require("maya.ai"); local m=ai.initialized.ollama and require("minuet.virtualtext").action; return {visible=require("maya.ai_next_edit").visible() or (m and m.is_visible()) or false,status=require("maya.ai_coordinator").status()}'
                            )
                            visible = state["visible"]
                            if (
                                visible
                                or state["status"] == "idle; no suggestion to show"
                            ):
                                break
                            time.sleep(0.02)
                        elapsed = (time.monotonic() - t0) * 1000
                        requests = nvim.exec_lua("return _G.benchmark_requests")
                        loads = nvim.exec_lua("return _G.benchmark_loads")
                        if visible:
                            nvim.exec_lua('require("maya.ai").accept()')
                            time.sleep(0.05)
                        nvim.exec_lua('require("maya.ai").cancel()')
                        actual = "\n".join(nvim.current.buffer[:])
                        print(
                            json.dumps(
                                {
                                    "mode": mode,
                                    "case": case["id"],
                                    "kind": case["kind"],
                                    "sample": sample,
                                    "observation": "first" if sample == 0 else "warm",
                                    "visible": visible,
                                    "preview_ms": round(elapsed, 1)
                                    if visible
                                    else None,
                                    "elapsed_ms": round(elapsed, 1),
                                    "exact": actual.strip() == case["expected"].strip(),
                                    "correct": elapsed < 13000
                                    and not any(q.get("error") for q in requests)
                                    and equivalent(
                                        actual, case["expected"], case["language"]
                                    ),
                                    "timed_out": elapsed >= 13000,
                                    "unchanged": actual == case["source"],
                                    "actual": actual,
                                    "source": case["source"],
                                    "expected": case["expected"],
                                    "requests": requests,
                                    "loads": loads,
                                    "residency": api(args.endpoint, "/api/ps"),
                                }
                            ),
                            flush=True,
                        )
                finally:
                    stop(nvim)


if __name__ == "__main__":
    main()
