local ok, err = pcall(dofile, vim.fn.stdpath("config") .. "/scripts/bootstrap.lua")
if not ok then
  io.stderr:write(tostring(err) .. "\n")
  vim.cmd("cquit 1")
else
  vim.cmd("qa")
end
