local M = {}
local running = false

function M.run(directory)
  if running then
    return vim.notify("An update is already running", vim.log.levels.INFO)
  end
  local root = vim.uv.fs_realpath(directory or vim.fn.stdpath("config"))
  if not root then
    return vim.notify("Cannot find the maya-nvim checkout", vim.log.levels.ERROR)
  end
  running = true
  local function fail(message)
    running = false
    vim.notify(message, vim.log.levels.ERROR, { title = "Update maya-nvim" })
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
      args = { "remote", "get-url", "origin" },
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
          "Local changes are preserved. Commit or stash them before updating: " .. root
      end,
    },
    { args = { "pull", "--ff-only", "--no-rebase", "--no-autostash", "origin", "master" } },
  }
  local function next_step(index)
    local step = steps[index]
    if not step then
      running = false
      vim.notify(
        "Repository updated. Syncing plugins; restart mvim afterwards to load the new config.",
        vim.log.levels.INFO,
        { title = "Update maya-nvim" }
      )
      local ok, err = pcall(vim.cmd, "Lazy sync")
      if not ok then
        fail(tostring(err))
      end
      return
    end
    local args = vim.list_extend({ "git", "-C", root }, step.args)
    local ok, err = pcall(vim.system, args, { text = true }, function(result)
      vim.schedule(function()
        if result.code ~= 0 then
          fail(
            vim.trim(result.stderr or "")
              .. "\nUpdate stopped; no reset or automatic stash was performed."
          )
          return
        end
        if step.check then
          local valid, message = step.check(vim.trim(result.stdout or ""))
          if not valid then
            fail(message)
            return
          end
        end
        next_step(index + 1)
      end)
    end)
    if not ok then
      fail(tostring(err))
    end
  end
  vim.notify(
    "Checking checkout and pulling master…",
    vim.log.levels.INFO,
    { title = "Update maya-nvim" }
  )
  next_step(1)
end

return M
