local M = {}
function M.check()
  if vim.fn.getcmdwintype() ~= "" or vim.fn.mode():match("^[cr!t]") then
    return
  end
  -- Native checktime retains modified buffers and provides the conflict prompt.
  vim.cmd("checktime")
end
function M.diff_disk()
  local source = vim.api.nvim_get_current_buf()
  local filename = vim.api.nvim_buf_get_name(source)
  if filename == "" or vim.fn.filereadable(filename) == 0 then
    return vim.notify("No readable disk file to compare", vim.log.levels.WARN)
  end
  local disk = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(disk, 0, -1, false, vim.fn.readfile(filename))
  vim.bo[disk].filetype = vim.bo[source].filetype
  vim.bo[disk].bufhidden = "wipe"
  vim.bo[disk].modifiable = false
  vim.api.nvim_buf_set_name(disk, filename .. " [disk snapshot]")
  vim.cmd("diffthis")
  vim.cmd("vsplit")
  vim.api.nvim_win_set_buf(0, disk)
  vim.cmd("diffthis")
end
function M.setup()
  local group = vim.api.nvim_create_augroup("MayaReload", { clear = true })
  vim.api.nvim_create_autocmd(
    { "FocusGained", "BufEnter", "InsertLeave" },
    { group = group, callback = M.check }
  )
  vim.api.nvim_create_autocmd("FileChangedShellPost", {
    group = group,
    callback = function(ev)
      if not vim.bo[ev.buf].modified then
        vim.notify("Reloaded " .. vim.fn.fnamemodify(ev.file, ":t"))
      end
    end,
  })
  vim.api.nvim_create_user_command("MayaDiffDisk", M.diff_disk, {})
  if M.timer then
    M.timer:stop()
    M.timer:close()
  end
  M.timer = vim.uv.new_timer()
  M.timer:start(1000, 1000, vim.schedule_wrap(M.check))
  vim.api.nvim_create_autocmd("VimLeavePre", {
    group = group,
    callback = function()
      if M.timer and not M.timer:is_closing() then
        M.timer:stop()
        M.timer:close()
      end
    end,
  })
end
return M
