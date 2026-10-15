-- Defer swap choices until startup/session restoration has finished.
local M = {}
local pending, queue, busy = {}, {}, false
local choice

local function show_next()
  if busy or #queue == 0 then
    return
  end
  busy = true
  local item = table.remove(queue, 1)
  local options = {
    { label = "Recover unsaved edits", choice = "r" },
    { label = "Open disk version read-only", choice = "o" },
    { label = "Skip for now (keep recovery file)" },
  }
  vim.ui.select(options, {
    prompt = "Recovery · " .. vim.fn.fnamemodify(item.file, ":~:."),
    format_item = function(option)
      return option.label
    end,
  }, function(option)
    if option and option.choice then
      -- Reopen using Neovim's own recovery/read-only handling, without deleting swaps.
      choice = { file = item.file, value = option.choice }
      if vim.api.nvim_win_is_valid(item.win) then
        vim.api.nvim_set_current_win(item.win)
      end
      local ok, err = pcall(vim.cmd, "silent edit " .. vim.fn.fnameescape(item.file))
      choice = nil
      if not ok then
        vim.notify(tostring(err), vim.log.levels.ERROR, { title = "File recovery" })
      elseif option.choice == "r" then
        vim.notify(
          "Recovered edits. Review the buffer, then save when ready. The original swap is kept.",
          vim.log.levels.INFO,
          { title = "File recovery" }
        )
      end
    end
    pending[item.file] = nil
    busy = false
    vim.schedule(show_next)
  end)
end

function M.setup()
  vim.api.nvim_create_autocmd("SwapExists", {
    group = vim.api.nvim_create_augroup("MayaSwapRecovery", { clear = true }),
    callback = function(ev)
      local file = vim.fn.fnamemodify(ev.file, ":p")
      if choice and choice.file == file then
        vim.v.swapchoice = choice.value
        return
      end
      if #vim.api.nvim_list_uis() == 0 then
        return -- Keep native handling in headless invocations.
      end
      vim.v.swapchoice = "q"
      if not pending[file] then
        pending[file] = true
        queue[#queue + 1] = { file = file, win = vim.api.nvim_get_current_win() }
        vim.schedule(show_next)
      end
    end,
  })
end

return M
