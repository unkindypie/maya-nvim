"""Capture Markdown FIM prompts: exact cursor context, no source echo, real hints retained."""

import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
requests = []
previous = (
    "There are 2 modes for local AI use: Dual - uses Sweep for next edit suggestion and"
)
source = "\n".join(
    [
        "# Local AI setup",
        "",
        "| Estimated VRAM | Local preset |",
        "| --- | --- |",
        "| 2–4 GB | Sweep only |",
        "| 6 GB | Qwen + Sweep |",
        "",
        previous,
        "",
        "These are estimates, real use may be different.",
    ]
)


class Capture(BaseHTTPRequestHandler):
    def do_POST(self):
        requests.append(
            json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        )
        data = json.dumps(
            {
                "response": "Qwen for inline completion; Single uses Sweep only.",
                "done": True,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="maya-markdown-context-") as temp:
        path = Path(temp, "README.md")
        path.write_text(source)
        Path(temp, "ai.json").write_text(
            json.dumps(
                {
                    "provider": "ollama",
                    "local_mode": "dual",
                    "model": "qwen2.5-coder:1.5b-base-q8_0",
                    "endpoint": f"http://127.0.0.1:{server.server_port}",
                }
            )
        )
        nvim = start()
        try:
            nvim.ui_attach(110, 35, rgb=True)
            nvim.command("edit " + str(path))
            nvim.exec_lua(
                """local state=...;local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and state or original(k) end
require("maya.user").config.ai_completion_debounce_ms=60000
require("maya.user").config.ai_next_edit_debounce_ms=60000
require("maya.ai").select("ollama",false)
""",
                temp,
            )
            nvim.current.window.cursor = (9, 0)
            nvim.input("i")
            wait(nvim, 'vim.fn.mode()=="i"')
            nvim.exec_lua(
                'require("maya.ai_coordinator").cancel(); require("maya.ai_context").refresh()'
            )
            assert previous in nvim.exec_lua('return require("maya.ai_context").get()')
            nvim.exec_lua('require("minuet.virtualtext").action.trigger()')
            wait(nvim, 'require("minuet.virtualtext").action.is_visible()')
            prompt = requests[-1]["prompt"]
            prefix, suffix = prompt.removeprefix("<|fim_prefix|>").split(
                "<|fim_suffix|>"
            )
            assert prefix.endswith(previous + "\n"), prefix
            assert prefix.count(previous) == 1, (
                "nearby Markdown duplicated as fake LSP context"
            )
            assert prefix.count("| Estimated VRAM | Local preset |") == 1
            assert (
                "Enclosing source" not in prompt and "<!-- LSP context:" not in prompt
            )
            assert (
                suffix
                == "\nThese are estimates, real use may be different.<|fim_middle|>"
            )
            assert requests[-1]["options"]["num_ctx"] == 4096
            assert "\n".join(nvim.current.buffer[:]) == source
            nvim.exec_lua("""require("maya.ai").cancel()
local client={id=55444,offset_encoding="utf-16"}
function client:supports_method(method) return method=="textDocument/hover" end
function client:request(_,_,cb) cb(nil,{contents="Markdown semantic documentation"}); return true,1 end
function client:cancel_request(_) end
_G.original_clients=vim.lsp.get_clients
vim.lsp.get_clients=function() return {client} end
require("maya.ai_context").refresh()
require("minuet.virtualtext").action.trigger()
""")
            wait(nvim, 'require("minuet.virtualtext").action.is_visible()')
            assert "Markdown semantic documentation" in requests[-1]["prompt"]
            assert requests[-1]["prompt"].count(previous) == 1
            assert "Enclosing source" not in requests[-1]["prompt"]
            nvim.exec_lua(
                'vim.lsp.get_clients=original_clients; require("maya.ai").cancel()'
            )
            print(
                "PASS actual Markdown HTTP prompts preserve previous line/suffix once, omit source echo and retain semantic hints"
            )
        finally:
            stop(nvim)
finally:
    server.shutdown()
    server.server_close()
