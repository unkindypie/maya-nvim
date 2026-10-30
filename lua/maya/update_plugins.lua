-- Runs in a fresh updater process, never reloads plugins in the user's editor.
local M = {}

local function read(path)
  return vim.json.decode(table.concat(vim.fn.readfile(path), "\n"))
end

function M.lockfile(target)
  M.target = target
  local managed = vim.env.MAYA_NVIM_UPDATE_ROOT .. "/lazy-lock.json"
  local pins = vim.tbl_extend("force", read(target), read(managed))
  vim.fn.writefile({ vim.json.encode(pins) }, vim.env.MAYA_NVIM_UPDATE_LOCKFILE)
  return vim.env.MAYA_NVIM_UPDATE_LOCKFILE
end

function M.run()
  local ok, err = xpcall(function()
    local lazy = require("lazy")
    local phase = vim.env.MAYA_NVIM_UPDATE_PHASE
    assert(phase == "install" or phase == "restore", "Unknown plugin update phase")
    lazy[phase]({ wait = true, show = false, lockfile = true })
    -- lazy.nvim commands can finish with failed tasks without raising an error.
    -- Inspect the task results exposed by its public plugins() inventory.
    for _, plugin in ipairs(lazy.plugins()) do
      for _, task in ipairs((plugin._ or {}).tasks or {}) do
        assert(not task:has_errors(), "Plugin task failed: " .. plugin.name .. "; see update log")
      end
      if plugin.name == "cursortab.nvim" and phase == "restore" then
        local build = vim
          .system(
            { "python3", vim.env.MAYA_NVIM_UPDATE_ROOT .. "/scripts/build_cursortab.py" },
            { text = true }
          )
          :wait()
        assert(build.code == 0, "Cursortab build failed: " .. (build.stderr or ""))
      end
      if plugin.url then
        assert(vim.fn.isdirectory(plugin.dir) == 1, "Plugin missing: " .. plugin.name)
      end
    end
    if
      phase == "restore"
      and M.target
      and vim.uv.fs_realpath(M.target)
        ~= vim.uv.fs_realpath(vim.env.MAYA_NVIM_UPDATE_ROOT .. "/lazy-lock.json")
    then
      vim.fn.writefile(vim.fn.readfile(vim.env.MAYA_NVIM_UPDATE_LOCKFILE), M.target)
    end
  end, debug.traceback)
  vim.fn.writefile(
    { vim.json.encode({ ok = ok, error = not ok and tostring(err) or nil }) },
    vim.env.MAYA_NVIM_UPDATE_RESULT
  )
  if not ok then
    io.stderr:write(tostring(err) .. "\n")
  end
  vim.cmd(ok and "qa!" or "cquit 1")
end

return M
