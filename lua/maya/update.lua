local M = {}
local running = false
local title = "Update maya-nvim"

function M.log_path()
  return vim.fn.stdpath("state") .. "/maya-update.log"
end

local function log(message)
  message = message:gsub("\27%[[0-9;]*m", "")
  vim.fn.mkdir(vim.fn.stdpath("state"), "p")
  vim.fn.writefile(vim.split(message, "\n", { plain = true }), M.log_path(), "a")
end

local function report(message, level)
  M.message = message
  log(message)
  vim.notify(message, level or vim.log.levels.INFO, {
    title = title,
    id = "maya-update",
    timeout = not running and 15000 or false,
  })
  vim.cmd.redrawstatus()
end

function M.status()
  return running and ("Updating: " .. (M.phase or "checking")) or ""
end

function M.show_status()
  vim.notify(
    M.message or "No update has run in this session. Use :MayaUpdateLog for the saved log.",
    vim.log.levels.INFO,
    {
      title = title,
      timeout = false,
    }
  )
end

function M.run(directory)
  if running then
    return M.show_status()
  end
  local root = vim.uv.fs_realpath(directory or vim.fn.stdpath("config"))
  if not root then
    return report("Cannot find the maya-nvim checkout", vim.log.levels.ERROR)
  end
  running = true
  local old_head, new_head
  local result_file, lock_file = vim.fn.tempname(), vim.fn.tempname()
  local function cleanup()
    vim.fn.delete(result_file)
    vim.fn.delete(lock_file)
  end
  local function fail(message)
    running = false
    M.phase = nil
    cleanup()
    report(
      "Update failed: " .. message .. "\nSee :MayaUpdateLog. Local work was not reset or stashed.",
      vim.log.levels.ERROR
    )
  end
  local function complete()
    running = false
    M.phase = nil
    cleanup()
    local summary = old_head == new_head and ("Config already up to date at " .. new_head)
      or ("Config updated " .. old_head .. " → " .. new_head)
    report(summary .. ". Plugins synchronized. Restart mvim to load the updated configuration.")
  end
  local function sync(phase)
    M.phase = phase == "install" and "installing plugins" or "restoring plugin versions"
    report(
      "Config at " .. new_head .. "; " .. M.phase .. " from the freshly loaded configuration…"
    )
    vim.fn.delete(result_file)
    local args = {
      vim.v.progpath,
      "--headless",
      "-i",
      "NONE",
      "-u",
      root .. "/init.lua",
      "--cmd",
      "lua vim.opt.runtimepath:prepend(vim.env.MAYA_NVIM_UPDATE_ROOT)",
      "+lua dofile(vim.env.MAYA_NVIM_UPDATE_ROOT .. '/scripts/sync-plugins.lua')",
    }
    local ok, err = pcall(vim.system, args, {
      text = true,
      cwd = root,
      timeout = 300000,
      env = {
        NVIM_APPNAME = "maya-nvim",
        MAYA_NVIM_NO_AI = "1",
        MAYA_NVIM_NO_INSTALL = "1",
        MAYA_NVIM_NO_SESSION = "1",
        MAYA_NVIM_UPDATE_ROOT = root,
        MAYA_NVIM_UPDATE_PHASE = phase,
        MAYA_NVIM_UPDATE_RESULT = result_file,
        MAYA_NVIM_UPDATE_LOCKFILE = lock_file,
        GIT_TERMINAL_PROMPT = "0",
      },
    }, function(result)
      vim.schedule(function()
        log((result.stdout or "") .. (result.stderr or ""))
        local decoded, receipt = pcall(function()
          return vim.json.decode(table.concat(vim.fn.readfile(result_file), "\n"))
        end)
        if result.code ~= 0 or not decoded or not receipt.ok then
          return fail(
            "Plugin "
              .. phase
              .. " failed (exit "
              .. result.code
              .. "). "
              .. (decoded and receipt.error or vim.trim(result.stderr or "No completion receipt"))
          )
        end
        if phase == "install" then
          sync("restore")
        else
          complete()
        end
      end)
    end)
    if not ok then
      fail(tostring(err))
    end
  end
  local steps = {
    {
      args = { "rev-parse", "--show-toplevel" },
      check = function(output)
        return vim.uv.fs_realpath(output) == root,
          "The config directory must be a Git checkout root"
      end,
    },
    {
      args = { "config", "--get", "remote.origin.url" },
      check = function(output)
        return vim.tbl_contains({
          "https://github.com/unkindypie/maya-nvim.git",
          "https://github.com/unkindypie/maya-nvim",
          "git@github.com:unkindypie/maya-nvim.git",
          "git@github.com:unkindypie/maya-nvim",
        }, output),
          "Origin must point to unkindypie/maya-nvim"
      end,
    },
    {
      args = { "branch", "--show-current" },
      check = function(output)
        return output == "master", "Switch to master before updating"
      end,
    },
    {
      args = { "status", "--porcelain", "--untracked-files=normal" },
      check = function(output)
        return output == "",
          "Local changes are preserved. Commit or stash them before updating: "
            .. root
            .. "\n"
            .. output
      end,
    },
    {
      args = { "rev-parse", "--short", "HEAD" },
      check = function(output)
        old_head = output
        return true
      end,
    },
    {
      args = { "pull", "--ff-only", "--no-rebase", "--no-autostash", "origin", "master" },
      phase = "pulling master",
    },
    {
      args = { "rev-parse", "--short", "HEAD" },
      check = function(output)
        new_head = output
        return true
      end,
    },
  }
  local function next_step(index)
    local step = steps[index]
    if not step then
      return sync("install")
    end
    if step.phase then
      M.phase = step.phase
      report("Pulling origin/master…")
    end
    local args = vim.list_extend({ "git", "-C", root }, step.args)
    local ok, err = pcall(
      vim.system,
      args,
      { text = true, timeout = 60000, env = { GIT_TERMINAL_PROMPT = "0" } },
      function(result)
        vim.schedule(function()
          log(table.concat(args, " ") .. "\n" .. (result.stdout or "") .. (result.stderr or ""))
          if result.code ~= 0 then
            return fail(vim.trim(result.stderr or "") .. " (git exit " .. result.code .. ")")
          end
          if step.check then
            local valid, message = step.check(vim.trim(result.stdout or ""))
            if not valid then
              return fail(message)
            end
          end
          next_step(index + 1)
        end)
      end
    )
    if not ok then
      fail(tostring(err))
    end
  end
  M.phase = "checking checkout"
  report("Checking checkout before updating…")
  next_step(1)
end

return M
