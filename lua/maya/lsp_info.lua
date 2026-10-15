local M = {}

function M.open()
  local buf = vim.api.nvim_get_current_buf()
  local lines = { "Buffer", "  " .. vim.fn.fnamemodify(vim.api.nvim_buf_get_name(buf), ":~:.") }
  lines[#lines + 1] = "  Filetype: "
    .. (vim.bo[buf].filetype ~= "" and vim.bo[buf].filetype or "none")
  lines[#lines + 1] = ""
  lines[#lines + 1] = "Tools"
  local tools = require("maya.statusline").tools()
  lines[#lines + 1] = "  " .. (tools ~= "" and tools or "No tools active for this buffer")
  lines[#lines + 1] = ""
  lines[#lines + 1] = "Attached language servers"
  local clients = vim.lsp.get_clients({ bufnr = buf })
  table.sort(clients, function(a, b)
    return a.name < b.name
  end)
  for _, client in ipairs(clients) do
    lines[#lines + 1] = "  ● " .. client.name
    local root = client.root_dir or client.config.root_dir
    lines[#lines + 1] = "    Root: "
      .. (type(root) == "string" and vim.fn.fnamemodify(root, ":~") or "single file")
    if type(client.config.cmd) == "table" then
      lines[#lines + 1] = "    Command: " .. table.concat(client.config.cmd, " ")
    end
  end
  if #clients == 0 then
    lines[#lines + 1] = "  No language server attached"
  end
  local win = Snacks.win({
    text = lines,
    title = " LSP Info ",
    title_pos = "center",
    border = "rounded",
    width = 0.8,
    max_width = 100,
    height = math.min(#lines, math.max(1, vim.o.lines - 6)),
    enter = true,
    backdrop = false,
    bo = { modifiable = false },
    wo = { wrap = true, cursorline = false },
    footer = " q close · h health · m Mason ",
    footer_pos = "center",
    keys = {
      q = "close",
      ["<Esc>"] = "close",
      h = function(self)
        self:close()
        vim.cmd("checkhealth vim.lsp")
      end,
      m = function(self)
        self:close()
        vim.cmd("Mason")
      end,
    },
  })
  local ns = vim.api.nvim_create_namespace("maya_lsp_info")
  for i, line in ipairs(lines) do
    if line ~= "" then
      local group = line:match("^  ●") and "DiagnosticOk"
        or (line:match("^%S") and "Title" or "Normal")
      vim.api.nvim_buf_set_extmark(win.buf, ns, i - 1, 0, { end_col = #line, hl_group = group })
    end
  end
end

return M
