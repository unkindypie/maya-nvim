local M = {}

function M.open()
  local rows = {
    { "Files" },
    { "Enter or Tab", "Open file / expand or collapse folder" },
    { "s", "Select item and move down" },
    { "a or n", "New file (end name with / for a folder)" },
    { "d", "Delete selected files" },
    { "r", "Rename file" },
    { "c / m", "Copy / move selected files" },
    { "y / p", "Yank paths / paste files" },
    { "" },
    { "Navigation" },
    { "j / k or arrows", "Move down / up" },
    { "h", "Collapse folder or its parent" },
    { "Backspace", "Go to parent directory" },
    { "i", "Search files" },
    { "Escape", "Leave typing mode in search" },
    { "H / I", "Toggle hidden / Git-ignored files" },
    { "P", "Toggle preview" },
    { "u", "Refresh files" },
    { "q", "Close Explorer" },
  }
  local lines = {}
  for _, row in ipairs(rows) do
    lines[#lines + 1] = row[2] and string.format("  %-19s %s", row[1], row[2]) or row[1]
  end
  local win = Snacks.win({
    title = " Explorer Help ",
    title_pos = "center",
    text = lines,
    border = "rounded",
    width = 0.9,
    max_width = 78,
    height = math.min(#lines, math.max(1, vim.o.lines - 6)),
    enter = true,
    backdrop = false,
    bo = { modifiable = false },
    wo = { wrap = true, cursorline = false },
    footer = " ? / q / Escape close ",
    footer_pos = "center",
    keys = { ["?"] = "close", q = "close", ["<Esc>"] = "close" },
  })
  local ns = vim.api.nvim_create_namespace("maya_explorer_help")
  for i, row in ipairs(rows) do
    if row[1] ~= "" then
      vim.api.nvim_buf_set_extmark(win.buf, ns, i - 1, row[2] and 2 or 0, {
        end_col = row[2] and 2 + #row[1] or #row[1],
        hl_group = row[2] and "Special" or "Title",
      })
    end
  end
end

return M
