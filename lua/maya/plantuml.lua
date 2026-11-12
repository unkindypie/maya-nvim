-- Loaded only by PlantUML filetype/commands. No server or renderer at startup.
local M = {}
local root = vim.fn.stdpath("data") .. "/tools/plantuml"
local waiting, installing = {}, false
local preview
local generation = 0
local function notify(text, level)
  vim.notify(text, level or vim.log.levels.INFO, { title = "PlantUML" })
end
local function write(path, data)
  local fd = assert(vim.uv.fs_open(path, "w", 384))
  assert(vim.uv.fs_write(fd, data))
  vim.uv.fs_close(fd)
end
local function ready()
  return vim.fn.filereadable(root .. "/plantuml.jar") == 1
    and vim.fn.executable(root .. "/bin/plantuml-lsp") == 1
end
function M.install(done, explicit)
  if vim.fn.executable("java") == 0 then
    return notify("Install Java (a JRE), then retry :PlantumlSetup", vim.log.levels.ERROR)
  end
  if ready() and not explicit then
    return done()
  end
  if vim.env.MAYA_NVIM_NO_INSTALL == "1" and not explicit then
    return
  end
  waiting[#waiting + 1] = done
  if installing then
    return
  end
  installing = true
  notify("Setting up local renderer and language server in the background…")
  vim.system(
    { "python3", vim.fn.stdpath("config") .. "/scripts/setup_plantuml.py", root },
    { text = true },
    vim.schedule_wrap(function(result)
      installing = false
      local callbacks = waiting
      waiting = {}
      if result.code ~= 0 then
        return notify(
          "Setup failed; retry :PlantumlSetup\n" .. (result.stderr or ""),
          vim.log.levels.ERROR
        )
      end
      for _, callback in ipairs(callbacks) do
        callback()
      end
    end)
  )
end
local function command(format)
  if vim.fn.executable("java") == 0 then
    notify("Install Java (a JRE) to render diagrams and run diagnostics", vim.log.levels.ERROR)
    return
  end
  local args = {
    "java",
    "-Djava.awt.headless=true",
    "-jar",
    root .. "/plantuml.jar",
    "-t" .. format,
    "-pipe",
    "-nometadata",
  }
  -- The bundled Java layout engine avoids requiring a system Graphviz install.
  if vim.fn.executable("dot") == 0 then
    args[#args + 1] = "-Playout=smetana"
  end
  return args
end
local function render(buf, format, callback)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  local args = command(format)
  if not args then
    return
  end
  local name = vim.api.nvim_buf_get_name(buf)
  return vim.system(args, {
    stdin = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n") .. "\n",
    cwd = name ~= "" and vim.fs.dirname(name) or vim.uv.cwd(),
    timeout = 20000,
  }, vim.schedule_wrap(callback))
end
function M.stop()
  generation = generation + 1
  local state = preview
  preview = nil
  if not state then
    return
  end
  if state.timer then
    state.timer:stop()
    state.timer:close()
  end
  if state.job then
    state.job:kill(15)
  end
  vim.api.nvim_del_augroup_by_id(state.group)
  vim.fn.delete(state.directory, "rf")
end
local function refresh(state)
  if preview ~= state or not vim.api.nvim_buf_is_valid(state.buf) then
    return
  end
  if state.job then
    return -- Completion checks the latest changedtick and renders again if needed.
  end
  local tick = vim.api.nvim_buf_get_changedtick(state.buf)
  state.job = render(state.buf, "svg", function(result)
    state.job = nil
    if preview ~= state or not vim.api.nvim_buf_is_valid(state.buf) then
      return
    end
    if tick ~= vim.api.nvim_buf_get_changedtick(state.buf) then
      return refresh(state)
    end
    if result.code == 0 and result.stdout:find("<svg", 1, true) then
      write(state.directory .. "/next.svg", result.stdout)
      assert(vim.uv.fs_rename(state.directory .. "/next.svg", state.directory .. "/diagram.svg"))
      state.error = nil
    else
      state.error = (result.stderr or ""):sub(1, 1500)
      notify(
        "Diagram has errors; keeping the last valid preview.\n" .. state.error,
        vim.log.levels.WARN
      )
    end
  end)
end
function M.open()
  local buf = vim.api.nvim_get_current_buf()
  if vim.bo[buf].filetype ~= "plantuml" then
    return notify("Open a PlantUML buffer first", vim.log.levels.WARN)
  end
  if preview and preview.buf == buf then
    return M.stop()
  end
  M.stop()
  local expected = generation
  M.install(function()
    if expected ~= generation or not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    M.stop()
    local directory = vim.fn.tempname()
    vim.fn.mkdir(directory, "p", 448)
    local state = {
      buf = buf,
      directory = directory,
      group = vim.api.nvim_create_augroup("MayaPlantumlPreview", { clear = true }),
    }
    preview = state
    write(
      directory .. "/index.html",
      [[<!doctype html><meta charset="utf-8"><title>PlantUML preview</title>
<style>body{margin:1rem;background:#eee;color:#222;font:16px system-ui}header{position:sticky;top:0}img{display:block;max-width:none}button{margin:.3rem;padding:.3rem}</style>
<header>PlantUML · live local preview <button onclick="zoom/=1.2;update()">−</button><button onclick="zoom*=1.2;update()">+</button><button onclick="zoom=1;update()">Reset</button></header><img id="diagram" alt="Waiting for the first valid diagram">
<script>let zoom=1;const img=document.getElementById('diagram');function update(){img.style.width=img.naturalWidth*zoom+'px'}
function reload(){const next=new Image();next.onload=()=>{img.src=next.src;img.onload=update};next.src='diagram.svg?'+Date.now()};setInterval(reload,1000);reload()</script>]]
    )
    state.timer = assert(vim.uv.new_timer())
    vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI", "BufWritePost" }, {
      group = state.group,
      buffer = buf,
      callback = function()
        state.timer:start(
          500,
          0,
          vim.schedule_wrap(function()
            refresh(state)
          end)
        )
      end,
    })
    vim.api.nvim_create_autocmd(
      "BufWipeout",
      { group = state.group, buffer = buf, callback = M.stop }
    )
    refresh(state)
    vim.ui.open(vim.uri_from_fname(directory .. "/index.html"))
  end)
end
function M.export(opts)
  local buf = vim.api.nvim_get_current_buf()
  local path = vim.fn.fnamemodify(opts.args, ":p")
  local format = path:match("%.(svg)$") or path:match("%.(png)$")
  if vim.bo[buf].filetype ~= "plantuml" or not format then
    return notify(
      "Use :PlantumlExport path.svg (or path.png) in a PlantUML buffer",
      vim.log.levels.ERROR
    )
  end
  if vim.uv.fs_stat(path) and not opts.bang then
    return notify("File exists; use :PlantumlExport! to overwrite", vim.log.levels.WARN)
  end
  M.install(function()
    render(buf, format, function(result)
      if result.code ~= 0 then
        return notify("Export failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
      end
      -- Exclusive creation protects files created while rendering was in progress.
      local fd, err = vim.uv.fs_open(path, opts.bang and "w" or "wx", 420)
      if not fd then
        return notify(tostring(err), vim.log.levels.ERROR)
      end
      vim.uv.fs_write(fd, result.stdout)
      vim.uv.fs_close(fd)
      notify("Exported " .. path)
    end)
  end)
end
function M.attach(buf)
  if not M.initialized then
    M.initialized = true
    vim.api.nvim_create_user_command("PlantumlPreview", M.open, {})
    vim.api.nvim_create_user_command("PlantumlStop", M.stop, {})
    vim.api.nvim_create_user_command(
      "PlantumlExport",
      M.export,
      { nargs = 1, bang = true, complete = "file" }
    )
    vim.api.nvim_create_user_command("PlantumlSetup", function()
      M.install(function()
        M.attach(vim.api.nvim_get_current_buf())
      end, true)
    end, {})
    vim.api.nvim_create_autocmd("VimLeavePre", { callback = M.stop })
    vim.api.nvim_create_autocmd("FileType", {
      callback = function(event)
        if vim.bo[event.buf].filetype ~= "plantuml" and vim.b[event.buf].maya_uml_preview_key then
          pcall(vim.keymap.del, "n", "<leader><CR>", { buffer = event.buf })
          vim.b[event.buf].maya_uml_preview_key = nil
        end
      end,
    })
  end
  if vim.bo[buf].filetype ~= "plantuml" then
    return
  end
  vim.bo[buf].commentstring = "' %s"
  vim.keymap.set(
    "n",
    "<localleader>up",
    M.open,
    { buffer = buf, desc = "Toggle PlantUML live preview" }
  )
  vim.b[buf].maya_uml_preview_key = true
  vim.keymap.set("n", "<leader><CR>", M.open, { buffer = buf, desc = "Preview UML Diagram" })
  -- Which-key sorts buffer-local actions first; hide only the older alias.
  require("which-key").add({ { "<localleader>up", buffer = buf, hidden = true } })
  M.install(function()
    if not vim.api.nvim_buf_is_valid(buf) or vim.bo[buf].filetype ~= "plantuml" then
      return
    end
    vim.lsp.config("plantuml_lsp", {
      cmd = {
        root .. "/bin/plantuml-lsp",
        "--jar-path=" .. root .. "/plantuml.jar",
        "--stdlib-path=" .. root .. "/stdlib",
      },
      filetypes = { "plantuml" },
      root_markers = { ".git" },
    })
    vim.lsp.enable("plantuml_lsp")
  end)
end
function M.status()
  return preview
end
return M
