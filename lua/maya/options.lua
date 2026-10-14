local opts = {
	termguicolors = true,
	number = true,
	relativenumber = false,
	expandtab = true,
	shiftwidth = 2,
	tabstop = 2,
	smartindent = true,
	ignorecase = true,
	smartcase = true,
	hlsearch = true,
	splitbelow = true,
	splitright = true,
	mouse = "a",
	wrap = false,
	clipboard = "unnamedplus",
	undofile = true,
	swapfile = true,
	backup = false,
	writebackup = false,
	scrolloff = 8,
	sidescrolloff = 8,
	signcolumn = "yes",
	cursorline = true,
	laststatus = 3,
	showmode = false,
	timeoutlen = 150,
	ttimeoutlen = 10,
	updatetime = 150,
	completeopt = { "menu", "menuone", "noselect" },
	autoread = true,
	title = true,
	pumheight = 10,
	foldmethod = "manual",
}
for name, value in pairs(opts) do
	vim.opt[name] = value
end
vim.diagnostic.config({
	virtual_text = true,
	severity_sort = true,
	update_in_insert = false,
	float = { border = "rounded", source = true },
	signs = { text = { [1] = "", [2] = "", [3] = "", [4] = "󰌵" } },
})
vim.filetype.add({
	extension = { hypr = "hyprlang" },
	pattern = { [".*/hypr/.*%.conf"] = "hyprlang", ["[jt]sconfig.*%.json"] = "jsonc" },
})
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "hyprlang", "conf", "config" },
	callback = function(ev)
		vim.bo[ev.buf].indentexpr = ""
		vim.bo[ev.buf].smartindent = false
		vim.b[ev.buf].snacks_indent = false
	end,
})
