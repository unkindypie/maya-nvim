local M = { provider = "off", initialized = {} }
local function settings()
  local file = vim.fn.stdpath("state") .. "/ai.json"
  local ok, value = pcall(function()
    return vim.json.decode(table.concat(vim.fn.readfile(file), "\n"))
  end)
  return ok and type(value) == "table" and value
    or { provider = "off", model = "qwen2.5-coder:3b-base", endpoint = "http://127.0.0.1:11434" }
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
  require("maya.ai_coordinator").cancel()
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
      "Automatic local AI: enabled",
      "Buffer: " .. (M.buffer_reason() or "eligible"),
      "Now: " .. require("maya.ai_coordinator").status(),
      M.local_mode == "dual" and "Insert: inline completion · idle: Sweep"
        or (
          M.local_mode == "single" and "Insert / Normal idle: Sweep" or "Insert: inline completion"
        ),
      "Tab: accept · Ctrl-]: dismiss until next edit",
      M.local_mode ~= "completion-only" and "Space an: request Sweep next-edit"
        or "Ctrl-L / Alt-[: request/cycle inline",
      "Space ao: enable/reload Ollama",
      "Space am: choose local mode and enable Ollama",
      "Space ax: disable all AI",
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
      "Space ao: enable Ollama · Space ac: enable Copilot",
      "Space am: choose local mode and enable Ollama",
    }
  end
  vim.notify(
    table.concat(lines, "\n"),
    vim.log.levels.INFO,
    { title = "AI status", timeout = 10000 }
  )
end

function M.select(provider, persist, local_mode)
  if not vim.tbl_contains({ "ollama", "copilot", "off" }, provider) then
    error("Choose ollama, copilot, or off")
  end
  local opts = settings()
  if local_mode ~= nil then
    if not vim.tbl_contains({ "single", "dual", "completion-only" }, local_mode) then
      error("Choose single, dual, or completion-only")
    end
    opts.local_mode = local_mode
  end
  local format = opts.fim_format
    or require("maya.ai_prompts").format(opts.model or "qwen2.5-coder:3b-base")
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
          debounce = 200,
          throttle = 0,
          enable_predicates = {
            function()
              local cmp = package.loaded["blink.cmp"]
              return M.provider == "ollama"
                and M.local_mode ~= "single"
                and M.eligible()
                and not (cmp and cmp.get_selected_item())
            end,
          },
          virtualtext = {
            show_on_completion_menu = true,
            external_scheduler = true,
            show_model = true,
            auto_trigger_ft = {},
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
        vim.b.minuet_virtual_text_auto_trigger = false
      else
        vim.b.minuet_virtual_text_auto_trigger = false
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
  require("maya.ai_coordinator").resume()
  if persist ~= false then
    opts.provider = provider
    vim.fn.mkdir(vim.fn.stdpath("state"), "p")
    vim.fn.writefile({ vim.json.encode(opts) }, vim.fn.stdpath("state") .. "/ai.json")
    local label = provider == "ollama"
        and ("Ollama · " .. M.local_mode .. " · " .. (M.local_mode == "single" and M.next_edit_model or M.model))
      or (provider == "copilot" and "GitHub Copilot" or "Off")
    vim.notify("AI: " .. label, vim.log.levels.INFO, { title = "AI suggestions" })
  end
end
function M.choose_local_mode()
  local current = settings().local_mode or "completion-only"
  vim.ui.select({
    { value = "dual", label = "Dual: inline completion + Sweep next edits" },
    { value = "single", label = "Single: Sweep only" },
    { value = "completion-only", label = "Completion-only: inline completion only" },
  }, {
    prompt = "Local AI mode (selecting enables Ollama)",
    format_item = function(item)
      return item.label .. (item.value == current and " (saved)" or "")
    end,
  }, function(item)
    if not item then
      return
    end
    local ok, err = pcall(M.select, "ollama", true, item.value)
    if not ok then
      vim.notify(tostring(err), vim.log.levels.ERROR, { title = "Local AI mode" })
    end
  end)
end
function M.accept()
  if M.provider == "ollama" and require("maya.ai_next_edit").accept() then
    return true
  end
  if M.provider == "ollama" and M.initialized.ollama then
    local action = require("minuet.virtualtext").action
    if action.is_visible() then
      action.accept()
      require("maya.ai_coordinator").accepted()
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
    require("maya.ai_coordinator").dismiss()
  end
  if M.provider == "ollama" and M.initialized.ollama and M.local_mode ~= "single" then
    if name ~= "dismiss" then
      require("maya.ai_coordinator").inline_action(name)
    end
  elseif M.provider == "copilot" and M.initialized.copilot then
    require("copilot.suggestion")[name]()
  end
end
function M.setup()
  require("maya.ai_context").setup(function()
    return M.provider == "ollama" and M.local_mode == "dual" and M.eligible()
  end)
  local group = vim.api.nvim_create_augroup("MayaAIHandover", { clear = true })
  require("maya.ai_coordinator").setup(M)
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
