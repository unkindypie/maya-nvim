"""Exercise the hotkey updater with local Git and real fresh Neovim workers."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from integration import ROOT, start, stop, wait


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.PIPE
    )


with tempfile.TemporaryDirectory(prefix="maya update ") as temp:
    root = Path(temp)
    remote, checkout = root / "remote", root / "checkout"
    personal = root / "personal-lock.json"
    trace = root / "phases"
    remote.mkdir()
    git(remote, "init", "-q", "-b", "master")
    git(remote, "config", "user.email", "test@example.invalid")
    git(remote, "config", "user.name", "Test")
    (remote / "scripts").mkdir()
    (remote / "lua/maya").mkdir(parents=True)
    for name in ("update_plugins.lua",):
        shutil.copy(ROOT / "lua/maya" / name, remote / "lua/maya" / name)
    shutil.copy(ROOT / "scripts/sync-plugins.lua", remote / "scripts/sync-plugins.lua")
    (remote / "version").write_text("old\n")
    (remote / "lazy-lock.json").write_text(json.dumps({"managed": {"commit": "old"}}))
    personal.write_text(
        json.dumps({"managed": {"commit": "stale"}, "personal": {"commit": "keep"}})
    )
    (remote / "init.lua").write_text("""local root = vim.env.MAYA_NVIM_UPDATE_ROOT
assert(vim.env.NVIM_APPNAME == "maya-nvim")
assert(vim.env.MAYA_NVIM_NO_AI == "1" and vim.env.MAYA_NVIM_NO_SESSION == "1")
local worker = require("maya.update_plugins")
local lock = worker.lockfile(vim.env.MAYA_TEST_PERSONAL_LOCK)
local pins = vim.json.decode(table.concat(vim.fn.readfile(lock), "\\n"))
assert(pins.managed.commit == "new" and pins.personal.commit == "keep")
assert(pins.added.commit == "fresh")
local function phase(name, opts)
 assert(opts.wait and opts.lockfile and opts.show == false)
 assert(vim.fn.readfile(root .. "/version")[1] == "new", "worker loaded stale configuration")
 vim.fn.writefile({name}, vim.env.MAYA_TEST_UPDATE_TRACE, "a")
 vim.wait(150)
end
package.loaded.lazy = {
 install = function(opts) phase("install", opts) end,
 restore = function(opts) phase("restore", opts) end,
 plugins = function() return {{name="fixture", _={tasks={{has_errors=function()
   return vim.env.MAYA_TEST_PLUGIN_ERROR == "1"
 end}}}}} end,
}
""")
    git(remote, "add", ".")
    git(remote, "commit", "-qm", "feat: fixture")
    subprocess.run(["git", "clone", "-q", str(remote), str(checkout)], check=True)
    canonical = "https://github.com/unkindypie/maya-nvim.git"
    git(checkout, "remote", "set-url", "origin", canonical)
    (remote / "version").write_text("new\n")
    (remote / "lazy-lock.json").write_text(
        json.dumps({"managed": {"commit": "new"}, "added": {"commit": "fresh"}})
    )
    git(remote, "commit", "-qam", "feat: new fixture")
    os.environ["XDG_STATE_HOME"] = str(root / "state")
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.exec_lua(
            """local remote, personal, trace = ...
vim.env.GIT_CONFIG_COUNT="1"
vim.env.GIT_CONFIG_KEY_0="url." .. remote .. ".insteadOf"
vim.env.GIT_CONFIG_VALUE_0="https://github.com/unkindypie/maya-nvim.git"
vim.env.MAYA_TEST_PERSONAL_LOCK=personal
vim.env.MAYA_TEST_UPDATE_TRACE=trace
update_messages = {}
vim.notify=function(message, level, opts)
 update_messages[#update_messages+1]={message=message, level=level, opts=opts}
end
-- The actual hotkey calls run() with the editor config directory.
local original = vim.fn.stdpath
vim.fn.stdpath = function(k) return k == "config" and vim.env.MAYA_TEST_CHECKOUT or original(k) end
""",
            str(remote),
            str(personal),
            str(trace),
        )
        nvim.exec_lua("vim.env.MAYA_TEST_CHECKOUT = ...", str(checkout))
        nvim.command("enew")
        nvim.current.buffer[:] = ["unsaved user edits"]
        nvim.exec_lua('vim.fn.maparg(" Mu", "n", false, true).callback()')
        assert nvim.exec_lua('return require("maya.update").status() ~= ""')
        nvim.exec_lua("""require("lazy").load({plugins={"lualine.nvim"}})
require("lualine").refresh({place={"statusline"}, force=true})
local rendered=vim.api.nvim_eval_statusline(vim.o.statusline,{maxwidth=200}).str
assert(rendered:find("Updating:",1,true), "update progress missing from statusline: "..rendered)""")
        # A second hotkey press must report progress without launching another job.
        nvim.exec_lua('vim.fn.maparg(" Mu", "n", false, true).callback()')
        wait(
            nvim,
            'require("maya.update").message:find("Plugins synchronized",1,true) ~= nil',
        )
        assert trace.read_text().splitlines() == ["install", "restore"]
        assert (checkout / "version").read_text() == "new\n"
        assert git(checkout, "status", "--porcelain") == b"", (
            "update dirtied the checkout"
        )
        assert json.loads(personal.read_text()) == {
            "managed": {"commit": "new"},
            "added": {"commit": "fresh"},
            "personal": {"commit": "keep"},
        }
        assert (
            nvim.current.buffer[:] == ["unsaved user edits"]
            and nvim.current.buffer.options["modified"]
        )
        assert nvim.exec_lua("return update_messages[1].opts.timeout == false")
        nvim.command("MayaUpdate")
        wait(
            nvim,
            'require("maya.update").message:find("Config already up to date",1,true) ~= nil',
        )
        nvim.exec_lua(
            'vim.env.MAYA_TEST_PLUGIN_ERROR="1"; require("maya.update").run()'
        )
        wait(
            nvim,
            'require("maya.update").message:find("Plugin task failed",1,true) ~= nil',
        )
        assert nvim.exec_lua('return require("maya.update").status() == ""')
        nvim.exec_lua("vim.env.MAYA_TEST_PLUGIN_ERROR=nil")
        trace_before = trace.read_text()
        (checkout / "local.txt").write_text("keep\n")
        nvim.command("MayaUpdate")
        wait(
            nvim,
            'require("maya.update").message:find("Local changes are preserved",1,true) ~= nil',
        )
        assert trace.read_text() == trace_before
        assert (checkout / "local.txt").read_text() == "keep\n"
        (checkout / "local.txt").unlink()
        git(checkout, "checkout", "-qb", "other")
        nvim.command("MayaUpdate")
        wait(
            nvim,
            'require("maya.update").message:find("Switch to master",1,true) ~= nil',
        )
        git(checkout, "checkout", "master")
        git(checkout, "remote", "set-url", "origin", str(root / "wrong"))
        nvim.command("MayaUpdate")
        wait(
            nvim,
            'require("maya.update").message:find("Origin must point",1,true) ~= nil',
        )
        git(checkout, "remote", "set-url", "origin", canonical)
        (checkout / "local.txt").write_text("committed local work\n")
        git(checkout, "config", "user.email", "test@example.invalid")
        git(checkout, "config", "user.name", "Test")
        git(checkout, "add", "local.txt")
        git(checkout, "commit", "-qm", "local work")
        local_head = git(checkout, "rev-parse", "HEAD")
        (remote / "version").write_text("later\n")
        git(remote, "commit", "-qam", "remote advance")
        nvim.command("MayaUpdate")
        wait(nvim, 'require("maya.update").message:find("git exit",1,true) ~= nil')
        assert git(checkout, "rev-parse", "HEAD") == local_head
        assert (checkout / "local.txt").read_text() == "committed local work\n"
        assert trace.read_text() == trace_before
        # A real fetch failure must surface and never proceed to plugins.
        nvim.exec_lua(
            'vim.env.GIT_CONFIG_KEY_0="url." .. ... .. ".insteadOf"',
            str(root / "missing"),
        )
        nvim.command("MayaUpdate")
        wait(nvim, 'require("maya.update").message:find("git exit",1,true) ~= nil')
        assert trace.read_text() == trace_before
        nvim.command("MayaUpdateStatus")
        log_path = nvim.exec_lua('return require("maya.update").log_path()')
        assert "Plugins synchronized" in Path(log_path).read_text()
        assert "Update failed" in Path(log_path).read_text()
        print(
            "PASS update hotkey, fresh plugin specs/pins, progress/completion, already-current, task/network failures, duplicate presses and local/unsaved edits preserved"
        )
    finally:
        stop(nvim)
