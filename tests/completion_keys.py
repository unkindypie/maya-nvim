"""Exercise real completion menu navigation and AI dismissal via key presses."""

from integration import start, stop, wait

nvim = start()
try:
    nvim.ui_attach(110, 35, rgb=True)
    nvim.command("enew")
    nvim.current.buffer[:] = ["alphaOne alphaTwo", "alp"]
    nvim.current.window.cursor = (2, 3)
    nvim.input("A")
    wait(nvim, 'vim.fn.mode() == "i"')
    nvim.exec_lua("""
local ai=require("maya.ai")
ai.provider="copilot"; ai.initialized.copilot=true
_G.ai_visible=true; _G.dismissed=0; _G.ai_accepted=0
package.loaded["copilot.suggestion"]={
 dismiss=function() ai_visible=false; dismissed=dismissed+1 end,
 is_visible=function() return ai_visible end,
 accept=function() ai_accepted=ai_accepted+1 end,
}
require("blink.cmp").show({providers={"buffer"}})
""")
    wait(nvim, 'require("blink.cmp").is_visible()')
    nvim.input("<Down>")
    wait(nvim, 'require("blink.cmp").get_selected_item_idx() == 1')
    assert nvim.exec_lua("return dismissed > 0 and not ai_visible")
    nvim.input("<Down>")
    wait(nvim, 'require("blink.cmp").get_selected_item_idx() == 2')
    nvim.input("<Up>")
    wait(nvim, 'require("blink.cmp").get_selected_item_idx() == 1')
    selected = nvim.exec_lua('return require("blink.cmp").get_selected_item().label')
    nvim.exec_lua("ai_visible=true")
    nvim.input("\t")
    wait(nvim, 'not require("blink.cmp").is_visible()')
    assert nvim.current.buffer[1] == selected, nvim.current.buffer[:]
    assert nvim.exec_lua("return ai_accepted") == 0
    nvim.input("<Esc>")
    nvim.current.buffer[1] = "alp"
    nvim.current.window.cursor = (2, 2)
    nvim.input("A")
    wait(nvim, 'vim.fn.mode() == "i"')
    nvim.exec_lua('require("blink.cmp").show({providers={"buffer"}})')
    wait(nvim, 'require("blink.cmp").is_visible()')
    nvim.input("<Down>")
    wait(nvim, 'require("blink.cmp").get_selected_item() ~= nil')
    selected = nvim.exec_lua('return require("blink.cmp").get_selected_item().label')
    nvim.input("<CR>")
    wait(nvim, 'not require("blink.cmp").is_visible()')
    assert nvim.current.buffer[1] == selected, nvim.current.buffer[:]
    assert (
        nvim.exec_lua('return vim.fn.maparg(" Mc", "n", false, true).desc')
        == "Edit personal configuration"
    )
    assert (
        nvim.exec_lua('return vim.fn.maparg(" Mu", "n", false, true).desc')
        == "Update maya-nvim"
    )
    assert nvim.exec_lua('return vim.fn.maparg(" Lc", "n")') == ""
    print(
        "PASS Down/Up completion selection, AI dismissal, and Tab accepts selected item"
    )
finally:
    stop(nvim)
