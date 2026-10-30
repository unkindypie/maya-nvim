"""Capture actual HTTP prompts with real LSPs and deterministic model replies."""

import argparse
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
parser = argparse.ArgumentParser(description=__doc__)
options = parser.parse_args()
requests = []


class Capture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(body)
        data = json.dumps({"response": "", "done": True}).encode()
        if body.get("stream"):
            data = b'data: {"choices":[{"text":"","finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream" if body.get("stream") else "application/json",
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


fixtures = [
    (
        "ts",
        "ts_ls",
        "typescript-language-server",
        ["--stdio"],
        'import type * as Schema from "./schema";\nconst config: Schema.Settings = {\n  theme: ',
        "interface Settings",
        "Theme repository formatting",
        {
            "schema.ts": 'import type { Theme } from "./theme_types";\nexport interface Settings {\n  /** Selected theme configuration. */\n  theme: Theme;\n}\n',
            "theme_types.ts": '/** Theme repository formatting: use "owner/repository". */\nexport interface Theme {\n  /** Repository identifier. */\n  plugin: string;\n  /** Already-installed colorscheme name. */\n  name?: string;\n}\n',
            "tsconfig.json": '{"compilerOptions":{"strict":true},"include":["*.ts"]}',
        },
        ["interface Theme", "plugin: string", "name?: string", '"owner/repository"'],
    ),
    (
        "py",
        "ty",
        "ty",
        ["server"],
        'import schema\nconfig: schema.Settings = {\n    "theme": ',
        "class Settings(TypedDict)",
        "Theme repository formatting",
        {
            "schema.py": 'from typing import TypedDict\nfrom theme_types import Theme\nclass Settings(TypedDict):\n    """Selected theme configuration."""\n    theme: Theme\n',
            "theme_types.py": 'from typing import TypedDict, NotRequired\nclass Theme(TypedDict):\n    """Theme repository formatting: use "owner/repository"."""\n    plugin: str\n    name: NotRequired[str]\n',
        },
        [
            "class Theme(TypedDict)",
            "plugin: str",
            "name: NotRequired[str]",
            '"owner/repository"',
        ],
    ),
    (
        "lua",
        "lua_ls",
        "lua-language-server",
        [],
        """-- Personal configuration: schema is in a separate workspace library.
---@type MayaConfig
return {
  pokemon_sound_on_start_volume_percentage = 50,
  reopen_tabs = true,
  pokemon_sound_on_start = true,
  theme =\x20
""",
        "---@class MayaConfig",
        '"owner/repository"',
    ),
    (
        "lua",
        "lua_ls",
        "lua-language-server",
        [],
        """---@class MayaConfig
---@field ai_completion_debounce_ms number Completion delay in milliseconds.
---@type MayaConfig
local config = {}
config.
""",
        "ai_completion_debounce_ms",
        "Completion delay",
    ),
    (
        "ts",
        "ts_ls",
        "typescript-language-server",
        ["--stdio"],
        """interface Settings {
  /** Completion delay in milliseconds. */
  completionDelay: number;
}
const config: Settings = { completionDelay: 200 };
config.
""",
        "completionDelay",
        "Completion delay",
    ),
    (
        "py",
        "ty",
        "ty",
        ["server"],
        '''from typing import TypedDict
class Settings(TypedDict):
    """Completion delay in milliseconds."""
    completion_delay: int
config: Settings = {"completion_delay": 200}
config.
''',
        "completion_delay",
        "Completion delay",
    ),
]
server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    for fixture in fixtures:
        ext, name, binary, args, source, field, doc = fixture[:7]
        files = fixture[7] if len(fixture) > 7 else {}
        additional = fixture[8] if len(fixture) > 8 else []
        with tempfile.TemporaryDirectory(prefix="maya-shared-context-") as temp:
            path = Path(temp, "fixture." + ext)
            path.write_text(source)
            for filename, content in files.items():
                Path(temp, filename).write_text(content)
            Path(temp, "ai.json").write_text(
                json.dumps(
                    {
                        "provider": "ollama",
                        "schema": 2,
                        "engine": "sweep",
                        "model": "test-sweep",
                        "endpoint": f"http://127.0.0.1:{server.server_port}",
                    }
                )
            )
            nvim = start()
            try:
                nvim.ui_attach(110, 35, rgb=True)
                nvim.command("edit " + str(path))
                cmd = [
                    str(Path.home() / ".local/share/maya-nvim/mason/bin" / binary),
                    *args,
                ]
                nvim.exec_lua(
                    """
local temp, cmd, name, library = ...
local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and temp or original(k) end
vim.lsp.start({name="context-test-"..name,cmd=cmd,root_dir=temp,
 settings={Lua={workspace={checkThirdParty=false,library=library},diagnostics={enable=false}}}})
require("maya.user").config.ai_completion_debounce_ms=60000
require("maya.user").config.ai_next_edit_debounce_ms=60000
require("maya.ai").select("ollama",false)
""",
                    temp,
                    cmd,
                    name,
                    [str(Path(__file__).resolve().parents[1] / "lua")]
                    if "return {" in source
                    else [],
                )
                wait(nvim, "#vim.lsp.get_clients({bufnr=0})>0")
                time.sleep(2)
                nvim.current.window.cursor = (len(source.splitlines()), 0)
                nvim.input("A")
                wait(nvim, 'vim.fn.mode()=="i"')
                nvim.exec_lua('require("maya.ai_context").refresh()')
                time.sleep(1.3)
                context = nvim.exec_lua('return require("maya.ai_context").get()')
                required = [field, doc, *additional]
                if "return {" in source:
                    schema = (
                        Path(__file__).resolve().parents[1] / "lua/maya/types.lua"
                    ).read_text()
                    required += [
                        line
                        for line in schema.splitlines()
                        if line.startswith(("---@field", "---@class"))
                    ]
                    required += [
                        "---@class MayaTheme",
                        "---@field plugins?",
                        "---@field setup?",
                        "already-installed colorscheme",
                        "does not install a plugin",
                    ]
                assert all(token in context for token in required), (
                    name,
                    required,
                    context,
                )
                caps = nvim.exec_lua("""local out={}; for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do
local methods={}; for _,m in ipairs({"hover","signatureHelp","definition","typeDefinition"}) do
methods[m]=c:supports_method("textDocument/"..m,0) end
out[c.name]=methods end; return out""")
                before = len(requests)
                nvim.exec_lua('require("maya.ai_next_edit").trigger()')
                deadline = time.monotonic() + 5
                while len(requests) < before + 1 and time.monotonic() < deadline:
                    time.sleep(0.05)
                assert len(requests) >= before + 1, "No Cursortab HTTP request"
                assert all(token in requests[-1]["prompt"] for token in required)
                assert "<|file_sep|>lsp-context.txt" in requests[-1]["prompt"]
                print(
                    "PASS",
                    name,
                    "HTTP prompts contain field/type documentation; mode",
                    "cursortab",
                    "capabilities",
                    caps,
                    flush=True,
                )
                print(
                    "Semantic context:", context[:350].replace("\n", " | "), flush=True
                )
            finally:
                try:
                    nvim.exec_lua('require("cursortab.daemon").stop_daemon()')
                finally:
                    stop(nvim)
finally:
    server.shutdown()
    server.server_close()
