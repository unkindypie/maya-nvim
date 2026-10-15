-- Optional personal configuration, separate from the managed repository.
local M = { config = {} }
local defaults = {
  pokemon_sound_on_start = true,
  pokemon_sound_on_start_volume_percentage = 50,
  reopen_tabs = true,
}
function M.get(key)
  if M.config[key] ~= nil then
    return M.config[key]
  end
  return defaults[key]
end
local home = vim.env.XDG_CONFIG_HOME
M.path = (home and home ~= "" and home or vim.fn.expand("~/.config")) .. "/mvim"

local function report(stage, err)
  vim.schedule(function()
    vim.notify("mvim personal config (" .. stage .. "): " .. tostring(err), vim.log.levels.ERROR)
  end)
end

function M.load()
  if vim.fn.isdirectory(M.path) == 0 then
    return
  end
  vim.opt.runtimepath:append(M.path)
  package.path = M.path .. "/lua/?.lua;" .. M.path .. "/lua/?/init.lua;" .. package.path
  local file = M.path .. "/init.lua"
  if vim.fn.filereadable(file) == 0 then
    return
  end
  local ok, config = pcall(dofile, file)
  if not ok then
    report(file, config)
    return
  end
  if config == nil then
    return
  end
  if type(config) ~= "table" then
    report(file, "expected a configuration table")
    return
  end
  for key, kind in pairs({
    options = "table",
    plugins = "table",
    setup = "function",
    pokemon_sound_on_start = "boolean",
    pokemon_sound_on_start_volume_percentage = "number",
    reopen_tabs = "boolean",
  }) do
    if config[key] ~= nil and type(config[key]) ~= kind then
      report(file, key .. " must be a " .. kind)
      return
    end
  end
  local volume = config.pokemon_sound_on_start_volume_percentage
  if volume ~= nil and (volume ~= volume or volume < 0 or volume > 100) then
    report(file, "pokemon_sound_on_start_volume_percentage must be between 0 and 100")
    return
  end
  M.config = config
end

function M.plugins()
  return M.config.plugins or {}
end

function M.lockfile()
  local base = vim.fn.stdpath("config") .. "/lazy-lock.json"
  if #M.plugins() == 0 then
    return base
  end
  local local_lock = M.path .. "/lazy-lock.json"
  if vim.fn.filereadable(local_lock) == 0 then
    local ok, err = pcall(function()
      vim.fn.writefile(vim.fn.readfile(base), local_lock)
    end)
    if not ok then
      report("plugin lockfile", err)
      -- Avoid writing personal plugins into the repository even if the config is read-only.
      local_lock = vim.fn.stdpath("state") .. "/personal-lazy-lock.json"
      vim.fn.mkdir(vim.fn.stdpath("state"), "p")
      if vim.fn.filereadable(local_lock) == 0 then
        vim.fn.writefile(vim.fn.readfile(base), local_lock)
      end
    end
  end
  return local_lock
end

function M.apply()
  if vim.fn.isdirectory(M.path) == 1 then
    if not vim.tbl_contains(vim.opt.runtimepath:get(), M.path) then
      vim.opt.runtimepath:append(M.path)
    end
    if vim.fn.isdirectory(M.path .. "/after") == 1 then
      vim.opt.runtimepath:append(M.path .. "/after")
    end
  end
  for key, value in pairs(M.config.options or {}) do
    local ok, err = pcall(function()
      vim.opt[key] = value
    end)
    if not ok then
      report("option " .. key, err)
    end
  end
  if M.config.setup then
    local ok, err = pcall(M.config.setup)
    if not ok then
      report("setup", err)
    end
  end
end
return M
