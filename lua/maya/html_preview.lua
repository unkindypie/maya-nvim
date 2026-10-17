local M = {}

local function notify(message, level)
  vim.notify(message, level or vim.log.levels.INFO, { title = "HTML preview" })
end

local function is_html(path, filetype)
  local lower = path:lower()
  return lower:match("%.html?$") ~= nil
    or lower:match("%.xhtml$") ~= nil
    or filetype == "html"
    or filetype == "xhtml"
end

local function current_file()
  local name = vim.api.nvim_buf_get_name(0)
  if name == "" then
    return nil, "The current buffer has no file name."
  end
  if vim.bo.buftype ~= "" then
    return nil, "The current buffer is not a normal file."
  end
  if not is_html(name, vim.bo.filetype) then
    return nil, "The current buffer is not an HTML file."
  end
  if vim.fn.filereadable(name) ~= 1 then
    return nil, "Save the current buffer before previewing it."
  end
  return name
end

local function project_root()
  local ok, util = pcall(require, "maya.util")
  if ok and type(util.root) == "function" then
    local called, root = pcall(util.root)
    if called and type(root) == "string" and root ~= "" then
      return root
    end
  end
  return vim.uv.cwd()
end

local function find_index()
  local candidates = {}
  local seen = {}
  local function add(path)
    if path and not seen[path] then
      seen[path] = true
      candidates[#candidates + 1] = path
    end
  end
  local name = vim.api.nvim_buf_get_name(0)
  if name ~= "" then
    add(vim.fs.joinpath(vim.fs.dirname(name), "index.html"))
  end
  local root = project_root()
  if root then
    add(vim.fs.joinpath(root, "index.html"))
  end
  local cwd = vim.uv.cwd()
  if cwd then
    add(vim.fs.joinpath(cwd, "index.html"))
  end
  for _, path in ipairs(candidates) do
    if vim.fn.filereadable(path) == 1 then
      return path
    end
  end
  return nil
end

local function browser_command(uri)
  if vim.fn.has("mac") == 1 then
    return { "open", uri }
  end
  local desktop
  if vim.fn.executable("xdg-settings") == 1 then
    local output = vim.fn.systemlist({ "xdg-settings", "get", "default-web-browser" })
    if vim.v.shell_error == 0 then
      desktop = vim.trim(output[1] or "")
    end
  end
  if desktop == "vim.desktop" or desktop == "nvim.desktop" then
    return nil,
      "The default web browser is a text editor. Set a graphical browser with xdg-settings."
  end
  if desktop ~= "" and vim.fn.executable("gtk-launch") == 1 then
    return { "gtk-launch", (desktop:gsub("%.desktop$", "")), uri }
  end
  if vim.fn.executable("xdg-open") == 1 then
    return { "xdg-open", uri }
  end
  return nil, "Could not find gtk-launch or xdg-open to open the browser."
end

local function launch(uri)
  local command, reason = browser_command(uri)
  if not command then
    notify(reason, vim.log.levels.ERROR)
    return
  end
  local ok, failure = pcall(vim.system, command, { text = true, timeout = 10000 }, function(result)
    if result.code ~= 0 then
      vim.schedule(function()
        local detail = vim.trim(result.stderr or "")
        if detail == "" then
          detail = vim.trim(result.stdout or "")
        end
        if detail == "" then
          detail = "exit code " .. tostring(result.code)
        end
        notify("Browser could not be launched: " .. detail, vim.log.levels.ERROR)
      end)
    end
  end)
  if not ok then
    notify("Browser could not be launched: " .. tostring(failure), vim.log.levels.ERROR)
  end
end

local function preview(path)
  launch(vim.uri_from_fname(path))
end

function M.preview_current()
  local path, reason = current_file()
  if not path then
    local index = find_index()
    if not index then
      notify(reason .. " No index.html was found in the project root.", vim.log.levels.ERROR)
      return
    end
    notify(
      "Current buffer is not a saved HTML file; previewing " .. index .. ".",
      vim.log.levels.WARN
    )
    path = index
  elseif vim.bo.modified then
    notify("Previewing the saved file; unsaved changes are not included.", vim.log.levels.WARN)
  end
  preview(path)
end

function M.preview_index()
  local index = find_index()
  if not index then
    notify("No index.html was found in the project root.", vim.log.levels.ERROR)
    return
  end
  preview(index)
end

function M.setup()
  vim.api.nvim_create_user_command("MayaHtmlPreview", function(opts)
    local target = vim.trim(opts.args):lower()
    if target == "" then
      M.preview_current()
    elseif target == "index" then
      M.preview_index()
    else
      notify("Usage: :MayaHtmlPreview [index]", vim.log.levels.ERROR)
    end
  end, {
    nargs = "?",
    complete = function()
      return { "index" }
    end,
    desc = "Open the current HTML file, or index.html, in the default browser",
    force = true,
  })
  vim.api.nvim_create_user_command("MayaHtmlPreviewIndex", M.preview_index, {
    desc = "Open index.html in the default browser",
    force = true,
  })
end

return M
