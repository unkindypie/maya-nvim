vim.g.mapleader = " "
vim.g.maplocalleader = " "
require("maya.options")
require("maya.reload").setup()
require("maya.user").load()
require("maya.lazy")
require("maya.swap").setup()
require("maya.html_preview").setup()
require("maya.keymaps")
require("maya.user").apply()
