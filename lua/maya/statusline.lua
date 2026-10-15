local M = {}

-- Read buffer-local providers, without loading plugins during dashboard redraws.
function M.tools()
  local buf = vim.api.nvim_get_current_buf()
  if vim.bo[buf].buftype ~= "" or vim.bo[buf].filetype == "" then
    return ""
  end
  local parts = {}
  local function add(label, names)
    names = vim.fn.uniq(vim.fn.sort(names))
    if #names > 0 then
      parts[#parts + 1] = label .. ": " .. table.concat(names, ",")
    end
  end

  local servers = {}
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
    servers[#servers + 1] = client.name
  end
  add("LSP", servers)

  local lint = package.loaded.lint
  if lint then
    local names = {}
    local ft = vim.bo[buf].filetype
    local filetypes = vim.split(ft, ".", { plain = true })
    filetypes[#filetypes + 1] = ft
    for _, filetype in ipairs(filetypes) do
      for _, name in ipairs(lint.linters_by_ft[filetype] or {}) do
        names[#names + 1] = name
      end
    end
    add("Lint", names)
  end

  local conform = package.loaded.conform
  if conform and not vim.b[buf].maya_noformat then
    local names = {}
    for _, formatter in ipairs(conform.list_formatters_to_run(buf)) do
      names[#names + 1] = formatter.name
    end
    add("Fmt", names)
  end
  return table.concat(parts, " | ")
end

return M
