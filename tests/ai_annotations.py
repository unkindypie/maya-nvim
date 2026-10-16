"""Annotation scope, capability fallback, and temporary LSP document lifecycle."""

from integration import start, stop

nvim = start()
try:
    nvim.command("enew")
    nvim.exec_lua("""
local positions=require("maya.ai_context_positions")
for _,case in ipairs({
 {"lua", {"---@type ProjectConfig", "return {", "  theme = "}},
 {"typescript", {"const config: ProjectConfig = {", "  theme: "}},
 {"python", {"config: ProjectConfig = {", '    "theme": '}}
}) do
 vim.bo.filetype=case[1]
 vim.api.nvim_buf_set_lines(0,0,-1,false,case[2])
 local anchors=positions.get(0,{#case[2],#case[2][#case[2]]})
 local found=false
 for _,p in ipairs(anchors) do
  local line=case[2][p[1]+1]
  if p.annotation and line:sub(p[2]+1):match("^ProjectConfig") then found=true end
 end
 assert(found,"incomplete annotation anchor missing: "..case[1])
end
vim.bo.filetype="lua"
vim.api.nvim_buf_set_lines(0,0,-1,false,{"---@type Unrelated", "local old = {}", "return {", "  theme = "})
for _,p in ipairs(positions.get(0,{4,10})) do
 assert(not p.annotation,"annotation from completed declaration leaked")
end

local context=require("maya.ai_context")
local original=vim.lsp.get_clients
local source=vim.api.nvim_get_current_buf()
local schema=vim.api.nvim_create_buf(false,true)
vim.api.nvim_buf_set_name(schema,"/tmp/maya-annotation-schema-"..vim.fn.getpid()..".lua")
vim.api.nvim_buf_set_lines(schema,0,-1,false,{
 "---@class ProjectConfig", "---@field child Child Related type.", "",
 "---@class Child", "---@field value string Nested documentation."
})
local requests,notifications={},{}
local client={id=55555,offset_encoding="utf-16"}
function client:supports_method(method) return method=="textDocument/typeDefinition" end
function client:request(method,params,callback)
 requests[#requests+1]={method=method,params=params,callback=callback}; return true,#requests
end
function client:cancel_request(_) end
function client:notify(method,params)
 notifications[#notifications+1]={method=method,params=params}; return true
end
vim.lsp.get_clients=function(opts) return opts.bufnr==source and {client} or {} end
vim.api.nvim_buf_set_lines(source,0,-1,false,{"---@type ProjectConfig", "return {", "  child = "})
vim.api.nvim_win_set_cursor(0,{3,9})
context.refresh()
assert(requests[1].params.position.line==0,"annotation must be requested first")
local function location(row)
 return {uri=vim.uri_from_bufnr(schema),range={start={line=row,character=0},["end"]={line=row,character=10}}}
end
requests[1].callback(nil,location(0))
assert(notifications[1],"referenced document was not synchronized")
assert(notifications[1].method=="textDocument/didOpen")
assert(notifications[1].params.textDocument.text:find("Nested documentation",1,true))
local nested=requests[#requests]
assert(nested.params.textDocument.uri==vim.uri_from_bufnr(schema))
assert(nested.method=="textDocument/typeDefinition","must fall back to supported capability")
nested.callback(nil,location(3))
local text=context.get()
assert(text:find("---@class ProjectConfig",1,true) and text:find("Nested documentation",1,true))
assert(#text<=6000)
assert(vim.api.nvim_get_current_buf()==source,"collector changed user buffer")
context.cancel()
assert(notifications[#notifications].method=="textDocument/didClose")
vim.api.nvim_buf_set_lines(source,0,1,false,{"---@type OtherConfig"})
context.refresh()
assert(not context.get():find("---@class ProjectConfig",1,true),"old annotation scope reused")
context.cancel()
vim.lsp.get_clients=original
vim.api.nvim_buf_delete(schema,{force=true})
""")
    print(
        "PASS incomplete annotations, enclosing scope, nested capability fallback, document lifecycle and 6000-character bound"
    )
finally:
    stop(nvim)
