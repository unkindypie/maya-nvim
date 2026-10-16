"""Delayed LSP responses are cached without waiting or leaking stale context."""

from integration import start, stop

nvim = start()
try:
    nvim.command("enew")
    nvim.exec_lua("""
local context=require("maya.ai_context")
vim.api.nvim_buf_set_lines(0,0,-1,false,{"object.value"})
vim.api.nvim_win_set_cursor(0,{1,12})
local original_clients=vim.lsp.get_clients
local original_sync=vim.lsp.buf_request_sync
vim.lsp.buf_request_sync=function() error("synchronous LSP request") end
_G.callbacks={}; _G.canceled={}
local client={id=55,offset_encoding="utf-16"}
function client:supports_method() return true end
function client:request(method,params,callback)
 callbacks[method]=callbacks[method] or {callback=callback,params=params}; return true,method
end
function client:cancel_request(id) canceled[id]=true end
vim.lsp.get_clients=function() return {client} end
context.refresh()
assert(context.get():find("Enclosing source",1,true))
assert(callbacks["textDocument/hover"].params.position.character==0, "hover should target receiver")
callbacks["textDocument/hover"].callback(nil,{contents={kind="markdown",value="Object: Example"}})
callbacks["textDocument/signatureHelp"].callback(nil,{signatures={{label="call(value: int)"}}})
assert(context.get():find("Object: Example",1,true))
assert(context.get():find("call(value: int)",1,true))
local old=callbacks["textDocument/definition"].callback
context.cancel()
old(nil,{uri="file:///does/not/exist",range={start={line=0,character=0},["end"]={line=0,character=0}}})
assert(context.get()=="")
assert(canceled["textDocument/definition"])
callbacks={}
context.refresh()
local delayed=callbacks["textDocument/hover"].callback
vim.api.nvim_buf_set_lines(0,0,-1,false,{"changed"})
delayed(nil,{contents="stale"})
assert(context.get()=="")
-- LocationLink snippets survive nearby edits but never changes in their source.
callbacks={}
local target=vim.api.nvim_create_buf(false,true)
vim.api.nvim_buf_set_name(target,"/tmp/maya-context-target-"..vim.fn.getpid()..".lua")
vim.api.nvim_buf_set_lines(target,0,-1,false,{"---@class SharedType", "---@field count integer Number of entries."})
context.refresh()
callbacks["textDocument/typeDefinition"].callback(nil,{{targetUri=vim.uri_from_bufnr(target),targetSelectionRange={start={line=0,character=0},["end"]={line=1,character=0}}}})
assert(context.get():find("SharedType",1,true))
vim.api.nvim_buf_set_lines(0,0,-1,false,{"changed again"})
callbacks={}; context.refresh()
assert(context.get():find("SharedType",1,true), "nearby edit discarded valid target")
vim.api.nvim_buf_set_lines(target,0,-1,false,{"---@class Replacement"})
assert(not context.get():find("SharedType",1,true), "stale target version")
vim.api.nvim_buf_delete(target,{force=true})
callbacks={}; context.refresh()
local expired=callbacks["textDocument/hover"].callback
vim.wait(1100, function() return false end)
expired(nil,{contents="EXPIRED_HINT"})
assert(not context.get():find("EXPIRED_HINT",1,true))
callbacks={}
vim.api.nvim_buf_set_lines(0,0,-1,false,{"é object.value"})
vim.api.nvim_win_set_cursor(0,{1,14})
context.refresh()
assert(callbacks["textDocument/hover"].params.position.character==2, "receiver needs UTF-16 column")
context.cancel(); callbacks={}
function client:supports_method() return false end
context.refresh()
assert(next(callbacks)==nil, "unsupported method requested")
vim.lsp.get_clients=original_clients
vim.lsp.buf_request_sync=original_sync
context.cancel()
""")
    print("PASS async LSP cache, receiver position, cancellation and stale changedtick")
finally:
    stop(nvim)
