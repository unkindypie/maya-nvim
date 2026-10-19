"""Real Lazy install/restore against local repos, with isolated plugin/state directories."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from integration import ROOT


def git(path, *args):
    return (
        subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.PIPE)
        .decode()
        .strip()
    )


with tempfile.TemporaryDirectory(prefix="maya plugin update ") as temp:
    root = Path(temp)
    source = root / "source"
    source.mkdir()
    git(source, "init", "-qb", "master")
    git(source, "config", "user.name", "Test")
    git(source, "config", "user.email", "test@example.invalid")
    (source / "README.md").write_text("old\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "old")
    old = git(source, "rev-parse", "HEAD")
    (source / "README.md").write_text("new\n")
    git(source, "commit", "-qam", "new")
    new = git(source, "rev-parse", "HEAD")
    remotes = root / "remotes"
    remotes.mkdir()
    for name in ("managed", "added", "personal", "broken"):
        subprocess.run(
            ["git", "clone", "--bare", "-q", str(source), str(remotes / name)],
            check=True,
        )
    (root / "lua/maya").mkdir(parents=True)
    shutil.copy(
        ROOT / "lua/maya/update_plugins.lua", root / "lua/maya/update_plugins.lua"
    )
    store = root / "plugins"
    store.mkdir()
    subprocess.run(
        ["git", "clone", "-q", str(remotes / "managed"), str(store / "managed")],
        check=True,
    )
    git(store / "managed", "checkout", "-q", old)
    managed = {
        "managed": {"branch": "master", "commit": new},
        "added": {"branch": "master", "commit": old},
    }
    base = root / "lazy-lock.json"
    base.write_text(json.dumps(managed))
    base_contents = base.read_bytes()
    personal = root / "personal.json"
    personal.write_text(
        json.dumps(
            {
                "managed": {"branch": "master", "commit": old},
                "personal": {"branch": "master", "commit": old},
            }
        )
    )
    (root / "init.lua").write_text("""vim.opt.rtp:prepend(vim.env.MAYA_TEST_LAZY)
local root = vim.env.MAYA_NVIM_UPDATE_ROOT
local lock = require("maya.update_plugins").lockfile(vim.env.MAYA_TEST_LOCK_TARGET)
local specs = {}
for _, name in ipairs({"managed", "added", "personal"}) do
 specs[#specs+1] = {name=name, url=vim.env.MAYA_TEST_PLUGIN_SOURCE.."/"..name, lazy=true}
end
if vim.env.MAYA_TEST_BUILD_FAIL == "1" then
 specs[#specs+1] = {name="broken", url=vim.env.MAYA_TEST_PLUGIN_SOURCE.."/broken", lazy=true,
   build=function() error("fixture build failed") end}
end
require("lazy").setup(specs, {
 root=root.."/plugins", lockfile=lock, install={missing=false}, rocks={enabled=false},
 checker={enabled=false}, change_detection={enabled=false},
})
""")
    env = dict(
        os.environ,
        NVIM_APPNAME="maya-nvim",
        XDG_STATE_HOME=str(root / "state"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"),
        MAYA_NVIM_UPDATE_ROOT=str(root),
        MAYA_TEST_LOCK_TARGET=str(personal),
        MAYA_NVIM_UPDATE_LOCKFILE=str(root / "runtime-lock.json"),
        MAYA_NVIM_UPDATE_RESULT=str(root / "result.json"),
        MAYA_TEST_LAZY=str(
            Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
            / "maya-nvim/lazy/lazy.nvim"
        ),
        MAYA_TEST_PLUGIN_SOURCE=str(remotes),
    )

    def phase(name):
        result = subprocess.run(
            [
                str(ROOT / "bin/mvim"),
                "--headless",
                "-i",
                "NONE",
                "-u",
                str(root / "init.lua"),
                "--cmd",
                "lua vim.opt.runtimepath:prepend(vim.env.MAYA_NVIM_UPDATE_ROOT)",
                "+lua dofile(" + repr(str(ROOT / "scripts/sync-plugins.lua")) + ")",
            ],
            env=dict(env, MAYA_NVIM_UPDATE_PHASE=name),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        receipt = json.loads((root / "result.json").read_text())
        return result, receipt

    for name in ("install", "restore"):
        result, receipt = phase(name)
        assert result.returncode == 0 and receipt["ok"], result.stdout + result.stderr
    assert git(store / "managed", "rev-parse", "HEAD") == new, (
        result.stdout
        + result.stderr
        + personal.read_text()
        + (root / "runtime-lock.json").read_text()
    )
    assert git(store / "added", "rev-parse", "HEAD") == old, (
        "missing plugin ignored the managed pin"
    )
    assert git(store / "personal", "rev-parse", "HEAD") == old, (
        "personal plugin pin was lost"
    )
    assert json.loads(personal.read_text())["managed"]["commit"] == new
    assert base.read_bytes() == base_contents
    # The normal configuration root is often a symlink: never publish into the tracked lockfile.
    alias = root / "config-link"
    alias.symlink_to(root, target_is_directory=True)
    env["MAYA_TEST_LOCK_TARGET"] = str(alias / "lazy-lock.json")
    result, receipt = phase("restore")
    assert result.returncode == 0 and receipt["ok"], result.stdout + result.stderr
    assert base.read_bytes() == base_contents, (
        "symlinked repository lockfile was overwritten"
    )
    env["MAYA_TEST_BUILD_FAIL"] = "1"
    result, receipt = phase("install")
    assert result.returncode != 0 and not receipt["ok"], (
        "Lazy task failure was reported as success"
    )
    assert "Plugin task failed: broken" in receipt["error"]
    print(
        "PASS real Lazy fresh install/restore uses managed/personal pins, preserves repository lockfiles and reports build failures"
    )
