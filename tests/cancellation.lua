-- Run with nvim --headless -u NONE, this repository on runtimepath.
local minuet = require 'minuet'
minuet.setup {
    provider = 'openai_fim_compatible',
    throttle = 0,
    virtualtext = { auto_trigger_ft = {} },
    provider_options = {
        openai_fim_compatible = {
            model = 'test',
            api_key = function()
                return 'test'
            end,
        },
    },
}
local callbacks, killed = {}, 0
package.loaded['minuet.backends.openai_fim_compatible'] = {
    complete = function(_, callback)
        callbacks[#callbacks + 1] = callback
    end,
}
local utils = require 'minuet.utils'
utils.get_context = function()
    return {}
end
utils.make_cmp_context = function()
    return {}
end
local mode = 'i'
vim.fn.mode = function()
    return mode
end
local text = require 'minuet.virtualtext'
local action = text.action
local common = require 'minuet.backends.common'
local function request()
    action.cancel()
    action.next()
    return callbacks[#callbacks]
end
local late = request()
common.register_job {
    pid = 1,
    kill = function()
        killed = killed + 1
    end,
}
action.cancel()
late { 'stale' }
assert(killed == 1 and not action.is_visible(), 'cancel must kill and invalidate')
local old = request()
action.cancel()
local new = request()
new { 'new' }
old { 'old' }
assert(action.is_visible(), 'old callback must not erase newer prediction')
action.accept()
vim.wait(20)
assert(vim.api.nvim_get_current_line() == 'new', 'accepted wrong generation')
for _, mutate in ipairs {
    function()
        minuet.config.provider_options.openai_fim_compatible.model = 'different'
    end,
    function()
        vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'changed' })
    end,
    function()
        vim.api.nvim_win_set_cursor(0, { 1, 0 })
    end,
    function()
        mode = 'n'
    end,
    function()
        vim.cmd 'enew'
    end,
    function()
        minuet.config.enable_predicates = {
            function()
                return false
            end,
        }
    end,
} do
    minuet.config.provider_options.openai_fim_compatible.model = 'test'
    minuet.config.enable_predicates = {}
    mode = 'i'
    vim.bo.modified = false
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'abcdef' })
    vim.api.nvim_win_set_cursor(0, { 1, 3 })
    local callback = request()
    mutate()
    callback { 'invalid' }
    assert(not action.is_visible(), 'stale identity displayed')
end
mode = 'i'
minuet.config.enable_predicates = {}
vim.bo.modified = false
vim.api.nvim_buf_set_lines(0, 0, -1, false, { '' })
local callback = request()
callback { 'must not be inserted' }
action.accept()
action.cancel()
vim.wait(20)
assert(vim.api.nvim_get_current_line() == '', 'scheduled acceptance survived cancellation')
print 'PASS Minuet cancellation, transport kill, late callbacks, identity changes, scheduled acceptance'
