"""Exercise updater against a local Git remote, without network or plugin updates."""

from pathlib import Path
import subprocess
import tempfile
from integration import start, stop, wait


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.PIPE
    )


with tempfile.TemporaryDirectory(prefix="maya-update-") as temp:
    root = Path(temp)
    remote, checkout = root / "remote", root / "checkout"
    remote.mkdir()
    git(remote, "init", "-q", "-b", "master")
    git(remote, "config", "user.email", "test@example.invalid")
    git(remote, "config", "user.name", "Test")
    (remote / "version").write_text("old\n")
    git(remote, "add", ".")
    git(remote, "commit", "-qm", "feat: fixture")
    subprocess.run(["git", "clone", "-q", str(remote), str(checkout)], check=True)
    canonical = "https://github.com/unkindypie/maya-nvim.git"
    git(checkout, "remote", "set-url", "origin", canonical)
    git(checkout, "config", "url." + str(remote) + ".insteadOf", canonical)
    # get-url expands insteadOf, so use a push-only rewrite and command environment
    # for the actual fetch, while keeping the canonical origin check intact.
    git(checkout, "config", "--unset", "url." + str(remote) + ".insteadOf")
    (remote / "version").write_text("new\n")
    git(remote, "commit", "-qam", "feat: new fixture")
    nvim = start()
    try:
        nvim.exec_lua(
            """
vim.env.GIT_CONFIG_COUNT="1"
vim.env.GIT_CONFIG_KEY_0="url." .. ... .. ".insteadOf"
vim.env.GIT_CONFIG_VALUE_0="https://github.com/unkindypie/maya-nvim.git"
vim.notify=function(message, level) _G.update_message=message end
vim.api.nvim_create_user_command("Lazy", function() _G.synced=true end, {nargs="*",force=true})
-- Git get-url expands URL rewrites. Override only this read-only response in the fixture.
local system=vim.system
vim.system=function(args, opts, callback)
 if args[4]=="remote" and args[5]=="get-url" then
  vim.schedule(function() callback({code=0,stdout="https://github.com/unkindypie/maya-nvim.git\\n"}) end)
  return {}
 end
 return system(args,opts,callback)
end
""",
            str(remote),
        )
        nvim.exec_lua('require("maya.update").run(...)', str(checkout))
        wait(nvim, "synced == true")
        assert (checkout / "version").read_text() == "new\n"
        (checkout / "local.txt").write_text("keep\n")
        nvim.exec_lua(
            'synced=false; update_message=""; require("maya.update").run(...)',
            str(checkout),
        )
        wait(nvim, 'update_message:find("Local changes are preserved",1,true) ~= nil')
        assert not nvim.exec_lua("return synced")
        assert (checkout / "local.txt").read_text() == "keep\n"
        print(
            "PASS fast-forward update + Lazy sync; dirty checkout preserved and sync skipped"
        )
    finally:
        stop(nvim)
