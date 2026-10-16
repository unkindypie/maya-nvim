"""Opt-in warm editor latency and alternating Ollama residency measurements."""

import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import urllib.request
from integration import start, stop, wait

if os.environ.get("MAYA_NVIM_TEST_OLLAMA") != "1":
    raise SystemExit("Set MAYA_NVIM_TEST_OLLAMA=1 to run real model requests")
os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
rows = []
with tempfile.TemporaryDirectory(prefix="maya-ai-latency-") as temp:
    Path(temp, "ai.json").write_text(
        json.dumps(
            {
                "provider": "ollama",
                "local_mode": "dual",
                "model": "qwen2.5-coder:1.5b-base-q8_0",
                "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
                "endpoint": "http://127.0.0.1:11434",
            }
        )
    )
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """local temp=...; local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and temp or original(k) end
require("maya.ai").select("ollama",false)
for _,name in ipairs({"minuet.backends.openai_fim_compatible","blink-edit.backends"}) do
 local backend=require(name); local original_complete=backend.complete
 backend.complete=function(opts,cb)
  _G.started=vim.uv.hrtime()
  return original_complete(opts,function(...)
   _G.finished=vim.uv.hrtime(); return cb(...)
  end)
 end
end""",
            temp,
        )
        for sample in range(11):
            for engine in ["qwen", "sweep"]:
                nvim.input("<Esc>")
                wait(nvim, 'vim.fn.mode()=="n"')
                nvim.exec_lua('require("maya.ai").cancel()')
                if engine == "qwen":
                    nvim.exec_lua(
                        'vim.api.nvim_buf_set_lines(0,0,-1,false,{"def add(a: int, b: int) -> int:","    "}); vim.api.nvim_win_set_cursor(0,{2,3})'
                    )
                    nvim.input("A")
                    wait(nvim, 'vim.fn.mode()=="i"')
                else:
                    nvim.exec_lua(
                        'vim.api.nvim_buf_set_lines(0,0,-1,false,{"def greet(person):","    return person.uper()"}); vim.api.nvim_win_set_cursor(0,{2,20})'
                    )
                t0 = time.monotonic()
                nvim.exec_lua(
                    'require("maya.ai").cancel(); _G.started=nil; _G.finished=nil; require("maya.ai_coordinator").activity(true)'
                )
                visible = False
                deadline = t0 + 13
                while time.monotonic() < deadline:
                    data = nvim.exec_lua("""return {started=_G.started,finished=_G.finished,
visible=require("minuet.virtualtext").action.is_visible() or require("maya.ai_next_edit").visible()}""")
                    if data.get("visible"):
                        visible = True
                        break
                    if data.get("finished"):
                        time.sleep(0.08)
                        visible = nvim.exec_lua(
                            'return require("minuet.virtualtext").action.is_visible() or require("maya.ai_next_edit").visible()'
                        )
                        break
                    time.sleep(0.02)
                elapsed = (time.monotonic() - t0) * 1000
                request_ms = (
                    ((data["finished"] - data["started"]) / 1e6)
                    if data.get("finished")
                    else None
                )
                with urllib.request.urlopen(
                    "http://127.0.0.1:11434/api/ps"
                ) as response:
                    residency = json.load(response)["models"]
                gpu = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    text=True,
                ).strip()
                row = {
                    "engine": engine,
                    "sample": sample,
                    "render_ms": round(elapsed, 1) if visible else None,
                    "request_ms": round(request_ms, 1) if request_ms else None,
                    "result": "rendered"
                    if visible
                    else (
                        "empty_or_rejected"
                        if data.get("finished")
                        else "failed_or_timeout"
                    ),
                    "gpu_mib": int(gpu),
                    "models": [
                        {"name": m["name"], "bytes": m["size"], "vram": m["size_vram"]}
                        for m in residency
                    ],
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
        for engine in ["qwen", "sweep"]:
            warm = [r for r in rows if r["engine"] == engine and r["sample"] > 0]
            rendered = sorted(
                r["render_ms"] for r in warm if r["render_ms"] is not None
            )
            durations = sorted(
                r["request_ms"] for r in warm if r["request_ms"] is not None
            )
            print(
                "SUMMARY",
                engine,
                json.dumps(
                    {
                        "samples": len(warm),
                        "rendered": len(rendered),
                        "median_ms": statistics.median(rendered) if rendered else None,
                        "p95_ms": rendered[-1] if rendered else None,
                        "request_median_ms": statistics.median(durations)
                        if durations
                        else None,
                        "request_p95_ms": durations[-1] if durations else None,
                        "empty_or_rejected": sum(
                            r["result"] == "empty_or_rejected" for r in warm
                        ),
                        "failed_or_timeout": sum(
                            r["result"] == "failed_or_timeout" for r in warm
                        ),
                    }
                ),
                flush=True,
            )
    finally:
        stop(nvim)
