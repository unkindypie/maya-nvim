-- On-demand Snacks image views. Raster buffers are display-only; SVG keeps its source.
local M = {}
local formats = {
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "bmp",
  "tif",
  "tiff",
  "avif",
  "heic",
  "ico",
  "PNG",
  "JPG",
  "JPEG",
}
local function image_setup()
  if not M.initialized then
    M.initialized = true
    Snacks.config.image.enabled = true
    Snacks.config.image.formats = formats
    Snacks.config.image.doc = { enabled = false }
    if vim.g.maya_image_handler then
      pcall(vim.api.nvim_del_autocmd, vim.g.maya_image_handler)
      vim.g.maya_image_handler = nil
    end
    Snacks.image.setup()
  end
end
function M.image(event)
  image_setup()
  Snacks.image.buf.attach(event.buf)
end
function M.pane(source, on_close)
  image_setup()
  local win = vim.fn.bufwinid(source)
  if win == -1 then
    return
  end
  local buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  local pane = { buf = buf, source = source }
  pane.win = vim.api.nvim_open_win(buf, false, { split = "right", win = win })
  vim.wo[pane.win].winbar = " Preview "
  vim.wo[pane.win].number = false
  vim.wo[pane.win].relativenumber = false
  vim.keymap.set("n", "q", function()
    pane:close()
  end, { buffer = buf, desc = "Close preview" })
  vim.api.nvim_create_autocmd("WinClosed", {
    pattern = tostring(pane.win),
    once = true,
    callback = function()
      if on_close then
        on_close()
      end
    end,
  })
  function pane:update(path)
    if vim.api.nvim_buf_is_valid(self.buf) and vim.api.nvim_win_is_valid(self.win) then
      self.path = path
      -- Each successful frame has a new filename, avoiding stale image caches.
      Snacks.image.buf.attach(self.buf, { src = path })
    end
  end
  function pane:close()
    if vim.api.nvim_win_is_valid(self.win) then
      pcall(vim.api.nvim_win_close, self.win, true)
    end
  end
  require("maya.image_view").attach(pane)
  return pane
end
local svgs = {}
function M.svg(buf)
  if
    not vim.api.nvim_buf_is_valid(buf)
    or vim.bo[buf].filetype ~= "svg"
    or svgs[buf]
    or vim.b[buf].maya_svg_preview_closed
  then
    return
  end
  if vim.fn.executable("magick") == 0 then
    vim.notify("SVG preview requires ImageMagick (magick)", vim.log.levels.WARN)
    return
  end
  local state = { directory = vim.fn.tempname(), version = 0 }
  svgs[buf] = state
  vim.fn.mkdir(state.directory, "p", 448)
  local function stop()
    if svgs[buf] ~= state then
      return
    end
    svgs[buf] = nil
    if vim.api.nvim_buf_is_valid(buf) then
      vim.b[buf].maya_svg_preview_closed = vim.fn.bufwinid(buf) ~= -1 and true or nil
    end
    if state.timer then
      state.timer:stop()
      state.timer:close()
    end
    if state.job then
      state.job:kill(15)
    end
    if state.group then
      vim.api.nvim_del_augroup_by_id(state.group)
    end
    if state.pane then
      state.pane:close()
    end
    vim.fn.delete(state.directory, "rf")
  end
  state.pane = M.pane(buf, stop)
  if not state.pane then
    stop()
    return
  end
  state.group = vim.api.nvim_create_augroup("MayaSVG" .. buf, { clear = true })
  state.timer = assert(vim.uv.new_timer())
  local refresh
  refresh = function()
    if svgs[buf] ~= state or state.job or not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    local tick = vim.api.nvim_buf_get_changedtick(buf)
    state.version = state.version + 1
    local output = state.directory .. "/" .. state.version .. ".png"
    local path = vim.api.nvim_buf_get_name(buf)
    state.job = vim.system(
      { "magick", "-background", "none", "svg:-", output },
      {
        stdin = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n"),
        cwd = path ~= "" and vim.fs.dirname(path) or vim.uv.cwd(),
        timeout = 15000,
      },
      vim.schedule_wrap(function(result)
        state.job = nil
        if svgs[buf] ~= state or not vim.api.nvim_buf_is_valid(buf) then
          return
        end
        if tick ~= vim.api.nvim_buf_get_changedtick(buf) then
          return refresh()
        end
        if result.code == 0 then
          state.pane:update(output)
        else
          vim.notify(
            "SVG preview: keeping the last valid image. " .. (result.stderr or ""),
            vim.log.levels.WARN
          )
        end
      end)
    )
  end
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI", "BufWritePost" }, {
    group = state.group,
    buffer = buf,
    callback = function()
      state.timer:start(500, 0, vim.schedule_wrap(refresh))
    end,
  })
  vim.api.nvim_create_autocmd(
    { "BufWipeout", "BufDelete" },
    { group = state.group, buffer = buf, callback = stop }
  )
  vim.api.nvim_create_autocmd("VimLeavePre", { group = state.group, callback = stop })
  vim.api.nvim_create_autocmd("BufWinLeave", {
    group = state.group,
    buffer = buf,
    callback = function()
      vim.schedule(function()
        if vim.fn.bufwinid(buf) == -1 then
          stop()
        end
      end)
    end,
  })
  refresh()
end
function M.status(buf)
  return svgs[buf]
end
return M
