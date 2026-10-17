"""Sweep abstains on destructive/unrelated windows but retains nearby typed edits."""

import json
import tempfile
import time
from pathlib import Path

from integration import start, stop, wait

with tempfile.TemporaryDirectory(prefix="maya-edit-filter-") as temp:
    Path(temp, "ai.json").write_text(
        json.dumps({"provider": "ollama", "local_mode": "single"})
    )
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """local temp = ...
local original = vim.fn.stdpath
vim.fn.stdpath = function(k) return k == "state" and temp or original(k) end
responses = {}
package.loaded["blink-edit.backends"] = {complete = function(_, cb)
  responses[#responses + 1] = cb; return #responses
end}
require("maya.user").config.ai_next_edit_debounce_ms = 60000
require("maya.ai").select("ollama", false)
local accept = require("maya.ai_edit_filter").accept
local lines = {"---@type MayaConfig", "return {", '  theme = "everforest",', "}"}
assert(accept({lines=lines, cursor={3, 0}}, {lines[1], lines[2], '  theme = { name = "everforest" },', lines[4]}, {window_start=1}))
assert(accept({lines=lines, cursor={3, 0}}, lines, {window_start=1}))
assert(not accept({lines=lines, cursor={3, 0}}, {""}, {window_start=1}))
assert(not accept({lines=lines, cursor={3, 0}}, {"return {}"}, {window_start=1}))
local source = {"# Coding-agent access", "", "Use the existing service account.", "",
  "1. Open the service account.", "2. Save the key locally.", "3. Give the agent the path.", "",
  "Reading GA4 events requires separate access.", "", "This JSON key is separate from the API secret."}
vim.bo.filetype = "markdown"
vim.api.nvim_buf_set_lines(0, 0, -1, false, source)
vim.api.nvim_win_set_cursor(0, {3, 0})
source_lines = source
""",
            temp,
        )

        def respond(lines, visible):
            count = nvim.exec_lua("""require("maya.ai").cancel()
require("maya.ai_next_edit").request()
return #responses""")
            assert count > 0
            nvim.exec_lua(
                'responses[#responses](nil, {text=table.concat(..., "\\n")})', lines
            )
            wait(nvim, 'not require("maya.ai_next_edit").pending()')
            assert (
                nvim.exec_lua('return require("maya.ai_next_edit").visible()')
                == visible
            )
            time.sleep(0.2)
            assert nvim.exec_lua("return #responses") == count, (
                "rejected prediction triggered a retry"
            )

        source = nvim.exec_lua("return source_lines")
        respond(source, False)  # unchanged is an intentional no-op
        respond(
            [source[0], "", "Use the existing"], False
        )  # screenshot-style truncated window
        respond([""], False)
        rewritten = source.copy()
        for index in (0, 2, 4, 5):
            rewritten[index] += " rewritten"
        respond(rewritten, False)
        unrelated = source.copy()
        unrelated[-1] = "An unrelated rewritten paragraph."
        respond(unrelated, False)
        nearby = source.copy()
        nearby[2] += " in the GCP project."
        respond(nearby, True)
        assert nvim.current.buffer[:] == source, (
            "filter or preview modified the document"
        )
        print(
            "PASS no-op, truncated/deleted/distant edits abstain without retries; nearby and typed edits retained"
        )
    finally:
        stop(nvim)
