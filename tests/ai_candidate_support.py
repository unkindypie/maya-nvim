"""Isolated editor and HTTP capture helpers for local AI candidate experiments."""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("MAYA_NVIM_BENCHMARK_MODEL", "maya-sweep-candidate-eval")


class Capture:
    def __init__(
        self, endpoint="http://127.0.0.1:11434", reply=None, buffer_stream=False
    ):
        self.endpoint = endpoint
        self.reply = reply
        self.buffer_stream = buffer_stream
        self.rows = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                row = {
                    "path": self.path,
                    "body": json.loads(body),
                    "started": time.monotonic(),
                    "chunks": [],
                }
                owner.rows.append(row)

                def forward(data):
                    try:
                        self.wfile.write(data)
                        self.wfile.flush()
                        return True
                    except (BrokenPipeError, ConnectionResetError) as error:
                        # Streaming consumers may stop after a useful edit or
                        # cancellation. This is not an upstream inference error.
                        row["client_disconnect"] = str(error)
                        return False

                try:
                    if owner.reply is not None:
                        content = owner.reply(row)
                        if row["body"].get("stream"):
                            data = (
                                "data: " + json.dumps(content) + "\n\ndata: [DONE]\n\n"
                            ).encode()
                        else:
                            data = json.dumps(content).encode()
                        self.send_response(200)
                        self.send_header(
                            "Content-Type",
                            "text/event-stream"
                            if row["body"].get("stream")
                            else "application/json",
                        )
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        forward(data)
                        row["chunks"].append(data.decode())
                        return
                    req = urllib.request.Request(
                        owner.endpoint + self.path,
                        data=body,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=20) as response:
                        self.send_response(response.status)
                        self.send_header(
                            "Content-Type",
                            response.headers.get("Content-Type", "application/json"),
                        )
                        if not row["body"].get("stream"):
                            data = response.read()
                            try:
                                payload = json.loads(data)
                                if payload.get("error"):
                                    row["error"] = str(payload["error"])
                            except (ValueError, AttributeError):
                                row["error"] = "Invalid nonstreaming JSON response"
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            row["chunks"].append(data.decode())
                            forward(data)
                            return
                        self.end_headers()
                        for line in (
                            response.readlines() if owner.buffer_stream else response
                        ):
                            row.setdefault("first_byte", time.monotonic())
                            row["chunks"].append(line.decode(errors="replace"))
                            if not forward(line):
                                break
                except (OSError, urllib.error.URLError) as error:
                    row["error"] = str(error)
                finally:
                    row["finished"] = time.monotonic()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


SETUP = r"""
local candidate, path, endpoint, state, delay, model, context_chars, engine = ...
_G.eval_enabled=false
_G.eval_status={state="Idle",pending=false}
pcall(vim.api.nvim_del_augroup_by_name,"MayaAIScheduler")
require("maya.ai").cancel()
do
 vim.opt.rtp:prepend(path)
 require("cursortab").setup({
  enabled=true, state_dir=state.."/cursortab", contribute_data=false,
  log_level="debug", debug={immediate_shutdown=true},
  keymaps={accept=false,partial_accept=false,trigger=false},
  source_context=function() return require("maya.ai_context").get({focused=vim.env.MAYA_AI_FOCUSED~="0"}):sub(1,context_chars) end,
  behavior={prefetch=false,normal_edit_only=true,text_change_debounce=delay,idle_completion_delay=650,
   cursor_prediction={enabled=false,auto_advance=false},
   ignore_gitignored=false,ignore_paths={},ignore_filetypes={},
   enabled_modes={"insert","normal"}},
  provider={type=engine,url=endpoint,model=model,
   context_size=tonumber(vim.env.MAYA_AI_TEST_CONTEXT) or 4096,max_tokens=512,temperature=0,completion_timeout=10000},
 })
 require("cursortab.daemon").set_enabled(false)
 vim.api.nvim_create_autocmd("User",{pattern="CursortabStateChanged",callback=function(e) _G.eval_status=e.data end})
 _G.eval_reset=function()
  require("cursortab.daemon").stop_daemon()
  _G.eval_status={state="Idle",pending=false}
  require("cursortab.daemon").force_start()
 end
 _G.eval_visible=function() return require("cursortab.ui").has_completion() end
 _G.eval_pending=function() return _G.eval_status.pending end
 _G.eval_accept=function() require("cursortab").accept() end
 _G.eval_cancel=function() require("cursortab.daemon").send_reject(); require("cursortab.daemon").set_enabled(false); require("cursortab.ui").close_all() end
 _G.eval_enable=function() require("cursortab.daemon").set_enabled(true) end
 _G.eval_request=function(manual)
  require("cursortab.daemon").set_enabled(true)
  require("cursortab.daemon").send_event(manual and "trigger_completion" or (vim.fn.mode()=="i" and "text_changed" or "cursor_moved"))
 end
end
"""


def start(
    candidate, path, endpoint, state, source, language, delay=200, context_chars=6000
):
    import pynvim

    os.environ.update(
        NVIM_APPNAME="maya-nvim",
        MAYA_NVIM_NO_INSTALL="1",
        MAYA_NVIM_NO_AI="1",
        MAYA_NVIM_NO_SESSION="1",
    )
    nvim = pynvim.attach(
        "child", argv=[str(ROOT / "bin/mvim"), "--embed", "--headless"]
    )
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("edit " + nvim.funcs.fnameescape(str(source)))
        nvim.exec_lua("vim.bo.filetype=...; vim.b.completion=false", language)
        nvim.exec_lua(
            SETUP,
            candidate,
            str(path),
            endpoint,
            str(state),
            delay,
            os.environ.get("MAYA_AI_TEST_MODEL", MODEL),
            context_chars,
            os.environ.get("MAYA_AI_TEST_ENGINE", "sweep"),
        )
        if candidate == "cursortab":
            deadline = time.monotonic() + 12
            while not Path(state, "cursortab/cursortab.sock").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError(nvim.command_output("messages"))
                time.sleep(0.05)
            time.sleep(0.15)
    except BaseException:
        close(nvim, candidate)
        raise
    return nvim


def close(nvim, candidate):
    from integration import stop

    try:
        if candidate == "cursortab":
            nvim.exec_lua('require("cursortab.daemon").stop_daemon()')
    finally:
        stop(nvim)
