local M = { provider = "off", initialized = {} }
local function settings()
  local ok, value = pcall(function()
    return vim.json.decode(
      table.concat(vim.fn.readfile(vim.fn.stdpath("state") .. "/ai.json"), "\n")
    )
  end)
  return require("maya.ai_settings").migrate(ok and type(value) == "table" and value or {})
end
function M.buffer_reason()
  local buf = vim.api.nvim_get_current_buf()
  if vim.bo[buf].buftype ~= "" then
    return "special buffer: " .. vim.bo[buf].buftype
  end
  if not vim.bo[buf].modifiable then
    return "buffer is not modifiable"
  end
  if vim.bo[buf].readonly then
    return "read-only buffer"
  end
  if vim.api.nvim_buf_line_count(buf) >= 10000 then
    return "buffer has 10,000 or more lines"
  end
  if vim.api.nvim_buf_get_offset(buf, vim.api.nvim_buf_line_count(buf)) >= 262144 then
    return "buffer is 256 KiB or larger"
  end
end
function M.eligible()
  return M.buffer_reason() == nil
end
function M.cancel()
  require("maya.ai_context").cancel()
  require("maya.ai_next_edit").cancel()
end
function M.status()
  if M.provider == "copilot" then
    return " Copilot"
  end
  if M.provider ~= "ollama" then
    return ""
  end
  local label = ({ sweep = "Sweep", ["zeta-2"] = "Zeta 2", ["zeta-2.1"] = "Zeta 2.1" })[M.engine]
  return "󰚩 " .. (label or "Local AI")
end
function M.notify_status()
  local lines = { "AI: " .. M.provider }
  if M.provider == "ollama" then
    vim.list_extend(lines, {
      "Cursortab · " .. M.model,
      "Server: " .. M.endpoint,
      "Buffer: " .. (M.buffer_reason() or "eligible"),
      "Now: " .. require("maya.ai_next_edit").status(),
      "Tab: accept · Ctrl-]: dismiss · Space an: request",
    })
  end
  vim.list_extend(
    lines,
    { "Space ao: local AI · Space ac: Copilot · Space ax: off", "Space am: local AI settings" }
  )
  vim.notify(table.concat(lines, "\n"), vim.log.levels.INFO, { title = "AI status" })
end
function M.select(provider, persist)
  assert(
    vim.tbl_contains({ "ollama", "copilot", "off" }, provider),
    "Choose ollama, copilot, or off"
  )
  local opts = settings()
  M.cancel()
  if M.initialized.copilot and M.provider == "copilot" and provider ~= "copilot" then
    vim.cmd("Copilot disable")
  end
  M.provider = provider
  M.model, M.endpoint = opts.model, opts.endpoint
  M.engine, M.context_size = opts.engine, opts.context_size
  if provider == "ollama" then
    require("maya.ai_next_edit").setup(M)
  elseif provider == "copilot" then
    if not M.initialized.copilot then
      require("copilot").setup({
        panel = { enabled = false },
        suggestion = {
          enabled = true,
          auto_trigger = true,
          hide_during_completion = true,
          keymap = {
            accept = false,
            accept_word = false,
            accept_line = false,
            next = false,
            prev = false,
            dismiss = false,
          },
        },
      })
      M.initialized.copilot = true
    else
      vim.cmd("Copilot enable")
    end
  end
  if persist ~= false then
    opts.provider = provider
    vim.fn.mkdir(vim.fn.stdpath("state"), "p")
    vim.fn.writefile({ vim.json.encode(opts) }, vim.fn.stdpath("state") .. "/ai.json")
    vim.notify("AI: " .. provider, vim.log.levels.INFO, { title = "AI suggestions" })
  end
end
function M.edit_settings()
  -- Space am edits the settings for the one local model.
  vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("state") .. "/ai.json"))
end
function M.accept()
  if M.provider == "ollama" then
    return require("maya.ai_next_edit").accept()
  end
  if M.provider == "copilot" and M.initialized.copilot then
    local suggestion = require("copilot.suggestion")
    if suggestion.is_visible() then
      suggestion.accept()
      return true
    end
  end
  return false
end
function M.action(name)
  if M.provider == "ollama" then
    if name == "dismiss" then
      require("maya.ai_next_edit").dismiss()
    else
      require("maya.ai_next_edit").trigger()
    end
  elseif M.provider == "copilot" and M.initialized.copilot then
    require("copilot.suggestion")[name]()
  end
end
function M.setup()
  require("maya.codex").setup()
  local group = vim.api.nvim_create_augroup("MayaAIHandover", { clear = true })
  require("maya.ai_next_edit").watch(M)
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "BlinkCmpListSelect",
    callback = function()
      local cmp = package.loaded["blink.cmp"]
      if cmp and cmp.get_selected_item() then
        M.action("dismiss")
      end
    end,
  })
  vim.keymap.set("n", "<Tab>", function()
    if M.provider == "ollama" and require("maya.ai_next_edit").visible() then
      vim.schedule(function()
        M.accept()
      end)
      return ""
    end
    return "<C-i>"
  end, { expr = true, desc = "Accept next-edit or jump forward" })
  vim.api.nvim_create_user_command("MayaAI", function(cmd)
    M.select(cmd.args)
  end, {
    nargs = 1,
    complete = function()
      return { "ollama", "copilot", "off" }
    end,
  })
  for key, name in pairs({ ["<C-l>"] = "next", ["<M-[>"] = "prev", ["<C-]>"] = "dismiss" }) do
    vim.keymap.set("i", key, function()
      M.action(name)
    end, { desc = "AI " .. name })
  end
  if vim.env.MAYA_NVIM_NO_AI ~= "1" then
    vim.api.nvim_create_autocmd("InsertEnter", {
      once = true,
      callback = function()
        M.select(settings().provider or "off", false)
      end,
    })
  end
end
return M
