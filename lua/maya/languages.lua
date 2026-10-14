-- One inventory drives first-use installs and installer bootstrap.
local M = { pending = {}, failed = {} }
M.specs = {
  python = { servers = { "ruff", "ty" }, packages = { "ruff", "ty" }, parser = "python" },
  javascript = {
    servers = { "ts_ls", "eslint" },
    packages = { "typescript-language-server", "eslint-lsp", "prettier" },
    parser = "javascript",
  },
  typescript = {
    servers = { "ts_ls", "eslint" },
    packages = { "typescript-language-server", "eslint-lsp", "prettier" },
    parser = "typescript",
  },
  typescriptreact = {
    servers = { "ts_ls", "eslint" },
    packages = { "typescript-language-server", "eslint-lsp", "prettier" },
    parser = "tsx",
  },
  javascriptreact = {
    servers = { "ts_ls", "eslint" },
    packages = { "typescript-language-server", "eslint-lsp", "prettier" },
    parser = "javascript",
  },
  json = { servers = { "jsonls" }, packages = { "json-lsp", "prettier" }, parser = "json" },
  jsonc = { servers = { "jsonls" }, packages = { "json-lsp", "prettier" }, parser = "json" },
  lua = { servers = { "lua_ls" }, packages = { "lua-language-server", "stylua" }, parser = "lua" },
  sh = {
    servers = { "bashls" },
    packages = { "bash-language-server", "shfmt", "shellcheck" },
    parser = "bash",
  },
  hyprlang = { servers = { "hyprls" }, packages = { "hyprls" }, parser = "hyprlang" },
  cpp = { servers = { "clangd" }, packages = { "clangd", "clang-format" }, parser = "cpp" },
  c = { servers = { "clangd" }, packages = { "clangd", "clang-format" }, parser = "c" },
  dockerfile = {
    servers = { "dockerls" },
    packages = { "dockerfile-language-server", "hadolint" },
    parser = "dockerfile",
  },
  yaml = {
    servers = { "yamlls" },
    packages = { "yaml-language-server", "prettier" },
    parser = "yaml",
  },
  html = { servers = { "html" }, packages = { "html-lsp", "prettier" }, parser = "html" },
  css = { servers = { "cssls" }, packages = { "css-lsp", "prettier" }, parser = "css" },
  markdown = {
    servers = { "marksman" },
    packages = { "marksman", "prettier" },
    parser = "markdown",
  },
  rust = { servers = { "rust_analyzer" }, packages = { "rust-analyzer" }, parser = "rust" },
}
M.specs.bash = M.specs.sh
M.specs.scss = { servers = { "cssls" }, packages = { "css-lsp", "prettier" }, parser = "scss" }
local function notify(msg, level)
  vim.schedule(function()
    vim.notify(msg, level)
  end)
end
function M.install_package(name, done)
  local registry = require("mason-registry")
  if M.pending[name] then
    M.pending[name][#M.pending[name] + 1] = done or function() end
    return
  end
  if M.failed[name] then
    return
  end
  if not registry.has_package(name) then
    M.failed[name] = true
    notify("Mason package unavailable: " .. name, vim.log.levels.WARN)
    return
  end
  local pkg = registry.get_package(name)
  if pkg:is_installed() then
    if done then
      done()
    end
    return
  end
  M.pending[name] = { done or function() end }
  notify("Installing " .. name)
  pkg:once(
    "install:success",
    vim.schedule_wrap(function()
      local callbacks = M.pending[name] or {}
      M.pending[name] = nil
      notify("Installed " .. name)
      for _, cb in ipairs(callbacks) do
        cb()
      end
    end)
  )
  pkg:once(
    "install:failed",
    vim.schedule_wrap(function()
      M.pending[name] = nil
      M.failed[name] = true
      notify(
        "Install failed: " .. name .. "; see :MasonLog, retry with :MayaTools",
        vim.log.levels.ERROR
      )
    end)
  )
  if not pkg:is_installing() then
    pkg:install()
  end
end
function M.highlight(buf, lang)
  if not vim.api.nvim_buf_is_valid(buf) or vim.b[buf].snacks_bigfile then
    return
  end
  pcall(vim.treesitter.start, buf, lang)
end
function M.parser(buf, lang)
  if not lang then
    return
  end
  local ok = pcall(vim.treesitter.get_string_parser, "", lang)
  if ok then
    M.highlight(buf, lang)
    return
  end
  M.parser_waiters = M.parser_waiters or {}
  if M.parser_waiters[lang] then
    table.insert(M.parser_waiters[lang], buf)
    return
  end
  M.parser_waiters[lang] = { buf }
  local ts = require("nvim-treesitter")
  if not vim.tbl_contains(ts.get_available(), lang) then
    M.parser_waiters[lang] = nil
    return
  end
  local task = ts.install({ lang })
  -- Installation is asynchronous; poll its observable parser result, never block editing.
  local attempts = 0
  local function ready()
    attempts = attempts + 1
    if pcall(vim.treesitter.get_string_parser, "", lang) then
      for _, b in ipairs(M.parser_waiters[lang] or {}) do
        M.highlight(b, lang)
      end
      M.parser_waiters[lang] = nil
    elseif attempts < 300 then
      vim.defer_fn(ready, 1000)
    else
      M.parser_waiters[lang] = nil
      notify("Parser install timed out: " .. lang .. "; retry :MayaTools", vim.log.levels.WARN)
    end
  end
  vim.defer_fn(ready, 300)
  return task
end
function M.ensure(buf)
  if
    vim.env.MAYA_NVIM_NO_INSTALL == "1"
    or not vim.api.nvim_buf_is_valid(buf)
    or vim.bo[buf].buftype ~= ""
  then
    return
  end
  local spec = M.specs[vim.bo[buf].filetype]
  if not spec then
    return
  end
  M.parser(buf, spec.parser)
  local registry = require("mason-registry")
  local function packages()
    for _, name in ipairs(spec.packages) do
      M.install_package(name, function()
        for _, server in ipairs(spec.servers) do
          vim.lsp.enable(server)
        end
      end)
    end
  end
  if #registry.get_all_package_names() == 0 then
    registry.refresh(vim.schedule_wrap(packages))
  else
    packages()
  end
end
function M.setup()
  local caps = require("blink.cmp").get_lsp_capabilities()
  vim.lsp.config("*", { capabilities = caps })
  vim.lsp.config("lua_ls", {
    settings = {
      Lua = { diagnostics = { globals = { "vim", "Snacks" } }, telemetry = { enable = false } },
    },
  })
  vim.lsp.config("jsonls", {
    settings = {
      json = { schemas = require("schemastore").json.schemas(), validate = { enable = true } },
    },
  })
  vim.lsp.config("yamlls", {
    settings = {
      yaml = {
        schemaStore = { enable = false, url = "" },
        schemas = require("schemastore").yaml.schemas(),
      },
    },
  })
  vim.lsp.config("ruff", {
    on_attach = function(client)
      client.server_capabilities.hoverProvider = false
    end,
  })
  vim.lsp.config("clangd", {
    cmd = function(dispatchers, config)
      local root = config.root_dir or vim.uv.cwd()
      local args = { "clangd", "--background-index", "--clang-tidy", "--header-insertion=never" }
      for _, rel in ipairs({ "build/mvim", "build", "build/linux", "." }) do
        if vim.uv.fs_stat(root .. "/" .. rel .. "/compile_commands.json") then
          table.insert(args, "--compile-commands-dir=" .. root .. "/" .. rel)
          break
        end
      end
      return vim.lsp.rpc.start(args, dispatchers)
    end,
  })
  local group = vim.api.nvim_create_augroup("MayaLanguages", { clear = true })
  vim.api.nvim_create_autocmd("FileType", {
    group = group,
    callback = function(ev)
      M.ensure(ev.buf)
    end,
  })
  vim.api.nvim_create_autocmd("LspAttach", {
    group = group,
    callback = function(ev)
      local b = ev.buf
      local client = vim.lsp.get_client_by_id(ev.data.client_id)
      if client and client:supports_method("textDocument/documentHighlight") then
        local highlights = vim.api.nvim_create_augroup("MayaHighlight" .. b, { clear = true })
        vim.api.nvim_create_autocmd(
          { "CursorHold", "CursorHoldI" },
          { group = highlights, buffer = b, callback = vim.lsp.buf.document_highlight }
        )
        vim.api.nvim_create_autocmd(
          { "CursorMoved", "CursorMovedI", "BufLeave" },
          { group = highlights, buffer = b, callback = vim.lsp.buf.clear_references }
        )
      end
      local maps = {
        K = { vim.lsp.buf.hover, "Hover" },
        gd = { vim.lsp.buf.definition, "Definition" },
        gD = { vim.lsp.buf.declaration, "Declaration" },
        gr = { vim.lsp.buf.references, "References" },
        gI = { vim.lsp.buf.implementation, "Implementation" },
        gs = { vim.lsp.buf.signature_help, "Signature help" },
        gl = { vim.diagnostic.open_float, "Line diagnostics" },
      }
      for key, action in pairs(maps) do
        vim.keymap.set("n", key, action[1], { buffer = b, desc = action[2] })
      end
    end,
  })
  vim.api.nvim_create_user_command("MayaTools", function()
    M.failed = {}
    M.ensure(vim.api.nvim_get_current_buf())
  end, {})
end
return M
