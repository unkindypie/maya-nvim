local M = { provider = "off", initialized = {} }
local function settings()
  local file = vim.fn.stdpath("state") .. "/ai.json"
  local ok, value = pcall(function()
    return vim.json.decode(table.concat(vim.fn.readfile(file), "\n"))
  end)
  return ok and type(value) == "table" and value
    or { provider = "off", model = "qwen2.5-coder:3b-base", endpoint = "http://127.0.0.1:11434" }
end
function M.eligible()
  local buf = vim.api.nvim_get_current_buf()
  return vim.bo[buf].buftype == ""
    and vim.bo[buf].modifiable
    and not vim.bo[buf].readonly
    and vim.api.nvim_buf_line_count(buf) < 10000
    and vim.api.nvim_buf_get_offset(buf, vim.api.nvim_buf_line_count(buf)) < 262144
end
function M.cancel()
  require("maya.ai_context").cancel()
  require("maya.ai_next_edit").cancel()
  if M.initialized.ollama then
    local action = require("minuet.virtualtext").action
    action.cancel()
  end
end
function M.status()
  if M.provider == "copilot" then
    return " Copilot"
  end
  if M.provider ~= "ollama" then
    return ""
  end
  local label = M.model or "Ollama"
  local size = label:match("^qwen2.5%-coder:(%d+%.?%d*)b")
  if size then
    label = "Qwen " .. size .. "B"
  end
  if label:lower():find("mellum", 1, true) then
    label = "Mellum"
  end
  if M.local_mode == "single" then
    label = "Sweep"
  end
  return "󰚩 " .. label .. (M.local_mode == "dual" and " + Sweep" or "")
end
function M.notify_status()
  local lines
  if M.provider == "ollama" then
    lines = {
      "Provider: Ollama (local)",
      "Mode: " .. (M.local_mode or "completion-only"),
      "Inline: " .. (M.local_mode == "single" and "Sweep" or (M.model or "qwen2.5-coder:3b-base")),
      "Next-edit: " .. (M.local_mode ~= "completion-only" and M.next_edit_model or "off"),
      "Server: " .. (M.endpoint or "http://127.0.0.1:11434"),
      "Automatic suggestions in this buffer: " .. (M.eligible() and "on" or "off"),
      M.local_mode == "dual" and "Insert: Minuet · Normal idle: Sweep"
        or (M.local_mode == "single" and "Insert / Normal idle: Sweep" or "Insert: Minuet"),
      "Tab: accept · Ctrl-]: dismiss · Space an: request next-edit",
      "Ctrl-L / Alt-[: cycle inline suggestions only",
      "Space ao: reload saved local model · Space ax: turn AI off",
    }
  elseif M.provider == "copilot" then
    lines = {
      "Provider: GitHub Copilot (cloud)",
      "Authentication/status: :Copilot auth / :Copilot status",
      "Tab: accept · Ctrl-]: dismiss · Space ax: turn AI off",
    }
  else
    lines = {
      "AI suggestions: off",
      "Normal editor completion is still available.",
      "Space ao: Ollama · Space ac: GitHub Copilot",
    }
  end
  vim.notify(
    table.concat(lines, "\n"),
    vim.log.levels.INFO,
    { title = "AI status", timeout = 10000 }
  )
end

function M.select(provider, persist)
  if not vim.tbl_contains({ "ollama", "copilot", "off" }, provider) then
    error("Choose ollama, copilot, or off")
  end
  local opts = settings()
  local format = opts.fim_format or require("maya.ai_prompts").format(opts.model or "")
  if
    provider == "ollama"
    and opts.local_mode == "dual"
    and not vim.tbl_contains({ "qwen", "mellum" }, format)
  then
    error("Custom dual-mode models require fim_format = qwen or mellum in saved AI preferences")
  end
  M.cancel()
  vim.g.blink_edit_enabled = false
  if M.provider == "ollama" and M.initialized.ollama then
    vim.b.minuet_virtual_text_auto_trigger = false
    require("minuet.virtualtext").action.dismiss()
  end
  if M.provider == "copilot" and M.initialized.copilot and provider ~= "copilot" then
    vim.cmd("Copilot disable")
  end
  local previous_model, previous_endpoint, previous_mode = M.model, M.endpoint, M.local_mode
  local previous_format = M.fim_format
  M.fim_format = format
  M.provider = provider
  M.model = opts.model or "qwen2.5-coder:3b-base"
  M.endpoint = opts.endpoint or "http://127.0.0.1:11434"
  M.local_mode = opts.local_mode or "completion-only"
  M.next_edit_model = opts.next_edit_model or require("maya.ai_next_edit").default_model
  if not vim.tbl_contains({ "single", "dual", "completion-only" }, M.local_mode) then
    M.local_mode = "completion-only"
  end
  if provider == "ollama" then
    if M.local_mode ~= "completion-only" then
      require("maya.ai_next_edit").setup(M)
    end
    if M.local_mode ~= "single" then
      if
        not M.initialized.ollama
        or previous_model ~= M.model
        or previous_endpoint ~= M.endpoint
        or previous_mode ~= M.local_mode
        or previous_format ~= M.fim_format
      then
        require("minuet").setup({
          provider = "openai_fim_compatible",
          n_completions = 1,
          context_window = M.local_mode == "completion-only" and 512 or 6000,
          duet = { enabled = false },
          request_timeout = 10,
          debounce = 400,
          throttle = 1000,
          enable_predicates = {
            function()
              return M.provider == "ollama" and M.local_mode ~= "single" and M.eligible()
            end,
          },
          virtualtext = {
            show_on_completion_menu = false,
            auto_trigger_ft = { "*" },
            keymap = {
              accept = false,
              accept_line = false,
              accept_n_lines = false,
              next = false,
              prev = false,
              dismiss = false,
            },
          },
          provider_options = {
            openai_fim_compatible = M.local_mode ~= "completion-only" and require(
              "maya.ai_prompts"
            ).options(M.model, M.endpoint, M.fim_format) or {
              api_key = function()
                return "ollama"
              end,
              name = "Ollama",
              end_point = M.endpoint .. "/v1/completions",
              model = M.model,
              optional = {
                max_tokens = 56,
                temperature = 0.2,
                stop = {
                  "<|fim_suffix|>",
                  "<|fim_middle|>",
                  "<|endoftext|>",
                  "<|im_end|>",
                  "\n\n",
                },
              },
            },
          },
        })
        M.initialized.ollama = true
        vim.b.minuet_virtual_text_auto_trigger = true
      else
        vim.b.minuet_virtual_text_auto_trigger = true
      end
    else
      vim.b.minuet_virtual_text_auto_trigger = false
    end
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
    local label = provider == "ollama" and ("Ollama · " .. M.model)
      or (provider == "copilot" and "GitHub Copilot" or "Off")
    vim.notify("AI: " .. label, vim.log.levels.INFO, { title = "AI suggestions" })
  end
end
function M.accept()
  if M.provider == "ollama" and require("maya.ai_next_edit").accept() then
    return true
  end
  if M.provider == "ollama" and M.initialized.ollama then
    local action = require("minuet.virtualtext").action
    if action.is_visible() then
      action.accept()
      return true
    end
  elseif M.provider == "copilot" and M.initialized.copilot then
    local s = require("copilot.suggestion")
    if s.is_visible() then
      s.accept()
      return true
    end
  end
  return false
end
function M.action(name)
  if name == "dismiss" then
    M.cancel()
  end
  if M.provider == "ollama" and M.initialized.ollama and M.local_mode ~= "single" then
    require("minuet.virtualtext").action[name]()
  elseif M.provider == "copilot" and M.initialized.copilot then
    require("copilot.suggestion")[name]()
  end
end
function M.setup()
  require("maya.ai_context").setup(function()
    return M.provider == "ollama" and M.local_mode == "dual" and M.eligible()
  end)
  local group = vim.api.nvim_create_augroup("MayaAIHandover", { clear = true })
  vim.api.nvim_create_autocmd(
    { "InsertEnter", "BufLeave", "LspDetach" },
    { group = group, callback = M.cancel }
  )
  vim.api.nvim_create_autocmd("InsertLeave", {
    group = group,
    callback = function()
      require("maya.ai_context").cancel()
      if M.initialized.ollama then
        require("minuet.virtualtext").action.cancel()
      end
    end,
  })
  vim.api.nvim_create_autocmd(
    "User",
    { group = group, pattern = "BlinkCmpMenuOpen", callback = M.cancel }
  )
  vim.keymap.set("n", "<Tab>", function()
    if M.provider == "ollama" and require("maya.ai_next_edit").visible() then
      vim.schedule(function()
        require("maya.ai_next_edit").accept()
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
