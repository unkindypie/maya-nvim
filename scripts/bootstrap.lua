-- Invoked by install.sh after locked plugin restoration.
local languages = require("maya.languages")
local registry = require("mason-registry")
local finished, success = false, false
registry.refresh(function(ok)
  success = ok
  finished = true
end)
assert(
  vim.wait(120000, function()
    return finished
  end, 100),
  "Mason registry refresh timed out"
)
assert(success, "Mason registry refresh failed")
local packages, parsers = {}, { "vim", "vimdoc", "query", "markdown_inline", "regex" }
for ft, spec in pairs(languages.specs) do
  if ft ~= "rust" then
    for _, name in ipairs(spec.packages) do
      packages[name] = true
    end
    if not vim.tbl_contains(parsers, spec.parser) then
      table.insert(parsers, spec.parser)
    end
  end
end
for _, name in ipairs({ "debugpy", "js-debug-adapter" }) do
  packages[name] = true
end
for name in pairs(packages) do
  languages.install_package(name)
end
assert(
  vim.wait(600000, function()
    return next(languages.pending) == nil
  end, 200),
  "Mason installations timed out; see :MasonLog"
)
assert(next(languages.failed) == nil, "Some tools failed: " .. vim.inspect(languages.failed))
require("nvim-treesitter").install(parsers):wait(300000)
local missing = {}
for _, lang in ipairs(parsers) do
  if not pcall(vim.treesitter.get_string_parser, "", lang) then
    table.insert(missing, lang)
  end
end
assert(#missing == 0, "Missing parsers: " .. table.concat(missing, ", "))
print("MAYA_BOOTSTRAP_OK")
