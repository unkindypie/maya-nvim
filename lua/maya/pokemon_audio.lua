local M = {}
local started = false

local function player(volume)
  local commands = {
    { "mpv", "--no-config", "--no-video", "--really-quiet", "--volume=" .. volume },
    { "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", tostring(volume) },
    { "pw-play", "--volume=" .. volume / 100 },
    { "paplay", "--volume=" .. math.floor(65536 * volume / 100 + 0.5) },
  }
  for _, command in ipairs(commands) do
    if vim.fn.executable(command[1]) == 1 then
      return command
    end
  end
end

function M.play(quote)
  if
    started
    or not require("maya.user").get("pokemon_sound_on_start")
    or require("maya.user").get("pokemon_sound_on_start_volume_percentage") == 0
    or vim.g.maya_pokemon_sound == false
    or vim.env.MAYA_NVIM_NO_SOUND == "1"
  then
    return
  end
  -- Headless checks should never access the network or speakers.
  if #vim.api.nvim_list_uis() == 0 then
    return
  end
  started = true
  local name = quote:match("%- ([%a]+) %(c%)$")
  local command = player(require("maya.user").get("pokemon_sound_on_start_volume_percentage"))
  if not name or not command then
    return
  end
  name = name:lower()
  local directory = vim.fn.stdpath("cache") .. "/pokemon-cries"
  local file = directory .. "/" .. name .. ".ogg"
  local jobs = {}
  local closing = false
  local deadline = vim.uv.hrtime() + 15e9
  vim.api.nvim_create_autocmd("VimLeavePre", {
    once = true,
    callback = function()
      closing = true
      for _, job in ipairs(jobs) do
        pcall(job.kill, job, 15)
      end
    end,
  })
  local function run(args, callback)
    if closing then
      return
    end
    local ok, job = pcall(vim.system, args, { text = true, timeout = 10000 }, function(result)
      vim.schedule(function()
        if not closing then
          callback(result)
        end
      end)
    end)
    if ok then
      jobs[#jobs + 1] = job
    end
  end
  local function playback()
    if vim.uv.hrtime() > deadline or vim.g.maya_pokemon_sound == false then
      return
    end
    local args = vim.list_extend(vim.deepcopy(command), { file })
    run(args, function() end)
  end
  local stat = vim.uv.fs_stat(file)
  if stat and stat.size > 0 then
    playback()
    return
  end
  if vim.fn.executable("curl") ~= 1 then
    return
  end
  vim.fn.mkdir(directory, "p")
  local curl = {
    "curl",
    "--fail",
    "--silent",
    "--show-error",
    "--location",
    "--proto",
    "=https",
    "--proto-redir",
    "=https",
    "--connect-timeout",
    "3",
    "--max-time",
    "6",
  }
  run(
    vim.list_extend(vim.deepcopy(curl), { "https://pokeapi.co/api/v2/pokemon/" .. name .. "/" }),
    function(result)
      if result.code ~= 0 then
        return
      end
      local ok, data = pcall(vim.json.decode, result.stdout)
      local url = ok
        and type(data) == "table"
        and type(data.cries) == "table"
        and (data.cries.latest or data.cries.legacy)
      if
        type(url) ~= "string"
        or not url:match("^https://raw%.githubusercontent%.com/PokeAPI/cries/")
      then
        return
      end
      local temp = file .. "." .. vim.fn.getpid() .. ".tmp"
      run(vim.list_extend(vim.deepcopy(curl), { "--output", temp, url }), function(download)
        local downloaded = vim.uv.fs_stat(temp)
        if download.code == 0 and downloaded and downloaded.size > 0 then
          if vim.uv.fs_rename(temp, file) then
            playback()
            return
          end
        end
        vim.fn.delete(temp)
      end)
    end
  )
end

return M
