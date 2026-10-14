local M = {}
function M.root()
	return vim.fs.root(0, { ".git", "pyproject.toml", "Cargo.toml", "CMakeLists.txt", "package.json" }) or vim.uv.cwd()
end
function M.pick(name, opts)
	return function()
		Snacks.picker[name](opts or {})
	end
end
function M.open_directory()
	local file = vim.api.nvim_buf_get_name(0)
	local dir = file ~= "" and vim.fs.dirname(file) or vim.uv.cwd()
	for _, app in ipairs({ "thunar", "xdg-open", "gio", "open" }) do
		if vim.fn.executable(app) == 1 then
			local args = app == "gio" and { app, "open", dir } or { app, dir }
			vim.system(args, { detach = true }, function(result)
				if result.code ~= 0 then
					vim.schedule(function()
						vim.notify(result.stderr, vim.log.levels.ERROR)
					end)
				end
			end)
			return
		end
	end
	vim.notify("Install a desktop file manager or xdg-open", vim.log.levels.WARN)
end
function M.config_file(name)
	vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("config") .. "/" .. name))
end
return M
