return {
	{
		"folke/persistence.nvim",
		lazy = false,
		config = function()
			require("maya.session").setup()
		end,
	},
	{
		"catppuccin/nvim",
		name = "catppuccin",
		priority = 1000,
		lazy = false,
		config = function()
			require("catppuccin").setup({
				flavour = "frappe",
				transparent_background = true,
				integrations = { blink_cmp = true, snacks = true, gitsigns = true },
			})
			vim.cmd.colorscheme("catppuccin-frappe")
		end,
	},
	{ "nvim-tree/nvim-web-devicons", lazy = true },
	{
		"folke/snacks.nvim",
		priority = 1000,
		lazy = false,
		opts = {
			bigfile = { enabled = true },
			indent = { enabled = true },
			input = { enabled = true },
			notifier = { enabled = true },
			explorer = { enabled = true },
			quickfile = { enabled = true },
			statuscolumn = { enabled = true },
			picker = {
				enabled = true,
				layout = { preset = "telescope" },
				sources = { files = { hidden = true }, grep = { hidden = true } },
				win = {
					input = {
						keys = {
							["<C-n>"] = { "list_down", mode = { "i", "n" } },
							["<C-p>"] = { "list_up", mode = { "i", "n" } },
							["<C-j>"] = { "history_forward", mode = { "i", "n" } },
							["<C-k>"] = { "history_back", mode = { "i", "n" } },
							["<C-q>"] = { "qflist", mode = { "i", "n" } },
						},
					},
				},
			},
			dashboard = {
				enabled = true,
				preset = {
					header = "🌙  maya-nvim\n\nFamiliar keys. A fresh start.",
					keys = {
						{ icon = " ", key = "f", desc = "Find file", action = ":lua Snacks.picker.files()" },
						{ icon = " ", key = "n", desc = "New file", action = ":ene | startinsert" },
						{ icon = " ", key = "g", desc = "Find text", action = ":lua Snacks.picker.grep()" },
						{ icon = " ", key = "r", desc = "Recent files", action = ":lua Snacks.picker.recent()" },
						{
							icon = " ",
							key = "c",
							desc = "Configuration",
							action = ":lua require('maya.util').config_file('init.lua')",
						},
						{ icon = "󰒲 ", key = "l", desc = "Plugins", action = ":Lazy" },
						{ icon = " ", key = "q", desc = "Quit", action = ":qa" },
					},
				},
			},
		},
	},
	{
		"folke/which-key.nvim",
		event = "VeryLazy",
		opts = {
			preset = "classic",
			delay = 150,
			plugins = {
				marks = false,
				registers = false,
				presets = {
					operators = false,
					motions = false,
					text_objects = false,
					windows = false,
					nav = false,
					z = false,
					g = false,
				},
			},
			win = { border = "single" },
		},
		config = function(_, opts)
			local wk = require("which-key")
			wk.setup(opts)
			local groups = {
				b = "Buffers",
				d = "Debug",
				g = "Git",
				l = "LSP",
				L = "maya-nvim",
				p = "Plugins",
				s = "Search",
				T = "Treesitter",
				o = "Open",
				a = "AI",
			}
			for key, label in pairs(groups) do
				wk.add({ { "<leader>" .. key, group = label } })
			end
		end,
	},
	{
		"akinsho/bufferline.nvim",
		event = "VeryLazy",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		opts = {
			options = {
				diagnostics = "nvim_lsp",
				always_show_bufferline = true,
				close_command = function(buf)
					Snacks.bufdelete(buf)
				end,
				offsets = { { filetype = "snacks_picker_list", text = "Explorer" } },
			},
		},
	},
	{
		"nvim-lualine/lualine.nvim",
		event = "VeryLazy",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		opts = {
			options = { theme = "catppuccin", globalstatus = true },
			sections = {
				lualine_c = { { "filename", path = 1 } },
				lualine_x = {
					function()
						return require("maya.ai").status()
					end,
					"encoding",
					"filetype",
				},
			},
		},
	},
	{
		"lewis6991/gitsigns.nvim",
		event = { "BufReadPost", "BufNewFile" },
		opts = {
			current_line_blame = true,
			current_line_blame_opts = { delay = 350, virt_text_pos = "eol", virt_text_priority = 1 },
			current_line_blame_formatter = "<author>, <author_time:%Y-%m-%d> — <summary>",
		},
	},
}
