local M = {}

-- Tab opens a file in the main window without dismissing the explorer.
-- Directories use the explorer's native expand/collapse action.
function M.open(picker, item, action)
  if not item then
    return
  end
  local close = picker.opts.jump.close
  picker.opts.jump.close = false
  local ok, err = pcall(require("snacks.explorer.actions").actions.confirm, picker, item, action)
  picker.opts.jump.close = close
  if not ok then
    error(err)
  end
  if not picker.closed then
    picker:focus("list")
  end
end

return M
