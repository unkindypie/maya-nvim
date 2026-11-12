-- A cropped viewport keeps diagram text readable; Snacks owns terminal graphics.
local M = {}
local views = {}
local dragging
local mouse_keys =
  { "<ScrollWheelUp>", "<ScrollWheelDown>", "<LeftMouse>", "<LeftDrag>", "<LeftRelease>" }
local actions = { "in", "out", "fit", "actual" }
function _G.MayaMediaControl(id)
  local view = views[math.floor(id / 10)]
  if view then
    view:control(actions[id % 10])
  end
end
function M.attach(pane)
  if vim.fn.executable("magick") == 0 then
    return
  end
  local display = pane.update
  local view = { zoom = 1.25, x = 0, y = 0, version = 0, pane = pane }
  views[pane.win] = view
  pane.view = view
  local directory = vim.fn.tempname()
  vim.fn.mkdir(directory, "p", 448)
  local timer = assert(vim.uv.new_timer())
  local group = vim.api.nvim_create_augroup("MayaImageView" .. pane.buf, { clear = true })
  local function geometry()
    local term = Snacks.image.terminal.size()
    local width = math.max(1, math.floor(vim.api.nvim_win_get_width(pane.win) * term.cell_width))
    local height = math.max(1, math.floor(vim.api.nvim_win_get_height(pane.win) * term.cell_height))
    return width, height, term
  end
  local function header()
    local parts = { " Preview ", tostring(math.floor(view.zoom * 100 + 0.5)) .. "%% " }
    for i, label in ipairs({ "+", "−", "Fit", "1:1" }) do
      parts[#parts + 1] = "%"
        .. (pane.win * 10 + i)
        .. "@v:lua.MayaMediaControl@ ["
        .. label
        .. "] %X"
    end
    parts[#parts + 1] = " ? Help"
    vim.wo[pane.win].winbar = "%<" .. table.concat(parts)
  end
  local render
  local function request()
    if view.closed then
      return
    end
    view.version = view.version + 1
    header()
    timer:start(
      35,
      0,
      vim.schedule_wrap(function()
        render()
      end)
    )
  end
  render = function()
    if view.closed or not view.path or view.job or not vim.api.nvim_win_is_valid(pane.win) then
      return
    end
    local width, height, term = geometry()
    if view.fit then
      view.zoom = math.min(width / view.size.width, height / view.size.height) / term.scale
    end
    local scale = math.max(0.01, view.zoom * term.scale)
    local cw = math.min(view.size.width, math.ceil(width / scale))
    local ch = math.min(view.size.height, math.ceil(height / scale))
    view.x = math.floor(math.max(0, math.min(view.x, view.size.width - cw)))
    view.y = math.floor(math.max(0, math.min(view.y, view.size.height - ch)))
    view.viewport =
      { width = width, height = height, crop_width = cw, crop_height = ch, scale = scale }
    header()
    local version = view.version
    local output = directory .. "/" .. version .. ".png"
    view.job = vim.system(
      {
        "magick",
        view.path,
        "-crop",
        ("%dx%d+%d+%d"):format(cw, ch, view.x, view.y),
        "+repage",
        "-resize",
        tostring(scale * 100) .. "%",
        "-background",
        "none",
        "-gravity",
        "northwest",
        "-extent",
        width .. "x" .. height,
        output,
      },
      { timeout = 10000 },
      vim.schedule_wrap(function(result)
        view.job = nil
        if view.closed then
          return
        end
        if version ~= view.version then
          return render()
        end
        if result.code == 0 then
          pane.view_path = output
          display(pane, output)
          pane.path = view.path -- retain the full-resolution source for refresh/export
        else
          vim.notify("Image viewport: " .. (result.stderr or ""), vim.log.levels.WARN)
        end
      end)
    )
  end
  function view:control(action, x, y)
    if not self.path or self.closed then
      return
    end
    local width, height, term = geometry()
    if action == "fit" then
      self.fit, self.x, self.y = true, 0, 0
    elseif action == "pan" then
      self.x, self.y = self.x + x, self.y + y
    else
      local previous = self.zoom * term.scale
      local zoom = action == "actual" and 1 or self.zoom * (action == "in" and 1.2 or 1 / 1.2)
      self.zoom = math.max(0.05, math.min(8, zoom))
      self.fit = false
      x, y = x or width / 2, y or height / 2
      self.x = self.x + x / previous - x / (self.zoom * term.scale)
      self.y = self.y + y / previous - y / (self.zoom * term.scale)
    end
    request()
  end
  function pane:update(path)
    if view.closed then
      return
    end
    view.path, self.path = path, path
    view.size = Snacks.image.util.dim(path)
    request()
  end
  local function mouse()
    local pos = vim.fn.getmousepos()
    if pos.winid ~= pane.win or pos.winrow <= 1 then
      return
    end
    local _, _, term = geometry()
    return (pos.wincol - 1) * term.cell_width, (pos.winrow - 2) * term.cell_height
  end
  for key, action in pairs({
    ["+"] = "in",
    ["="] = "in",
    ["-"] = "out",
    f = "fit",
    ["0"] = "actual",
  }) do
    vim.keymap.set("n", key, function()
      view:control(action)
    end, { buffer = pane.buf, desc = "Preview " .. action })
  end
  for key, delta in pairs({
    h = { -60, 0 },
    l = { 60, 0 },
    j = { 0, 60 },
    k = { 0, -60 },
    ["<Left>"] = { -60, 0 },
    ["<Right>"] = { 60, 0 },
    ["<Down>"] = { 0, 60 },
    ["<Up>"] = { 0, -60 },
  }) do
    vim.keymap.set("n", key, function()
      view:control("pan", delta[1] / view.zoom, delta[2] / view.zoom)
    end, { buffer = pane.buf, desc = "Pan preview" })
  end
  function view:mouse(key)
    local x, y = mouse()
    if key == "<LeftRelease>" then
      self.drag, dragging = nil, nil
      return
    end
    if not x then
      return
    end
    if key == "<ScrollWheelUp>" or key == "<ScrollWheelDown>" then
      self:control(key == "<ScrollWheelUp>" and "in" or "out", x, y)
    elseif key == "<LeftMouse>" then
      self.drag = { x = x, y = y, left = self.x, top = self.y }
      dragging = self
      vim.api.nvim_set_current_win(pane.win)
    elseif key == "<LeftDrag>" then
      self.drag = self.drag or { x = x, y = y, left = self.x, top = self.y }
      local _, _, term = geometry()
      self.x = self.drag.left + (self.drag.x - x) / (self.zoom * term.scale)
      self.y = self.drag.top + (self.drag.y - y) / (self.zoom * term.scale)
      request()
    end
  end
  for _, key in ipairs(mouse_keys) do
    vim.keymap.set("n", key, function()
      if vim.fn.getmousepos().winrow <= 1 then
        return key
      end
      vim.schedule(function()
        if not view.closed then
          view:mouse(key)
        end
      end)
      return ""
    end, { buffer = pane.buf, expr = true, desc = "Preview mouse control" })
  end
  if not M.mouse_installed then
    M.mouse_installed = true
    local existing = {}
    for _, map in ipairs(vim.api.nvim_get_keymap("n")) do
      existing[map.lhs] = true
    end
    for _, key in ipairs(mouse_keys) do
      -- Mouse input resolves mappings in the focused buffer, not the hovered pane.
      -- Preserve existing personal mappings; otherwise route only preview events.
      if not existing[key] then
        vim.keymap.set("n", key, function()
          local pos = vim.fn.getmousepos()
          if pos.winrow <= 1 then
            return key
          end
          local target = views[pos.winid]
          if key == "<LeftRelease>" and dragging then
            target = dragging
          end
          if not target or target.closed then
            return key
          end
          vim.schedule(function()
            if not target.closed then
              target:mouse(key)
            end
          end)
          return ""
        end, { expr = true, desc = "Preview mouse control or native mouse action" })
      end
    end
  end
  vim.keymap.set("n", "?", function()
    vim.notify(
      "Preview: wheel or +/− zoom · drag or hjkl/arrows pan · f fit · 0 actual size · q close",
      vim.log.levels.INFO
    )
  end, { buffer = pane.buf, desc = "Preview help" })
  vim.api.nvim_create_autocmd("WinResized", { group = group, callback = request })
  local function close()
    if view.closed then
      return
    end
    view.closed = true
    if dragging == view then
      dragging = nil
    end
    views[pane.win] = nil
    timer:stop()
    timer:close()
    if view.job then
      view.job:kill(15)
    end
    vim.api.nvim_del_augroup_by_id(group)
    vim.fn.delete(directory, "rf")
  end
  vim.api.nvim_create_autocmd(
    "WinClosed",
    { group = group, pattern = tostring(pane.win), callback = close }
  )
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = close })
  header()
end
return M
