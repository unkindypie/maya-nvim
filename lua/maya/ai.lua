local M = { provider = "off", initialized = {} }
local function settings()
	local file = vim.fn.stdpath("state") .. "/ai.json"
	local ok, value = pcall(function()
		return vim.json.decode(table.concat(vim.fn.readfile(file), "\n"))
	end)
	return ok and value or { provider = "off", model = "qwen2.5-coder:7b", endpoint = "http://127.0.0.1:11434" }
end
function M.status()
	return M.provider == "ollama" and ("󰚩 " .. M.model) or (M.provider == "copilot" and " Copilot" or "")
end
function M.select(provider, persist)
	if not vim.tbl_contains({ "ollama", "copilot", "off" }, provider) then
		error("Choose ollama, copilot, or off")
	end
	if M.provider == "ollama" and M.initialized.ollama then
		vim.cmd("Minuet virtualtext disable")
		require("minuet.virtualtext").action.dismiss()
	end
	if M.provider == "copilot" and M.initialized.copilot then
		vim.cmd("Copilot disable")
	end
	M.provider = provider
	local opts = settings()
	M.model = opts.model or "qwen2.5-coder:7b"
	if provider == "ollama" then
		if not M.initialized.ollama then
			require("minuet").setup({
				provider = "openai_fim_compatible",
				n_completions = 1,
				context_window = 512,
				request_timeout = 30,
				debounce = 400,
				throttle = 1000,
				enable_predicates = {
					function()
						return M.provider == "ollama"
					end,
				},
				virtualtext = {
					show_on_completion_menu = true,
					auto_trigger_ft = { "*" },
					keymap = {
						accept = false,
						accept_line = false,
						accept_n_lines = false,
						next = false,
						prev = false,
						dismiss = false,
					},
				},
				provider_options = {
					openai_fim_compatible = {
						api_key = function()
							return "ollama"
						end,
						name = "Ollama",
						end_point = (opts.endpoint or "http://127.0.0.1:11434") .. "/v1/completions",
						model = M.model,
						optional = {
							max_tokens = 56,
							temperature = 0.2,
							stop = { "<|fim_suffix|>", "<|fim_middle|>", "<|endoftext|>", "<|im_end|>", "\n\n" },
						},
					},
				},
			})
			M.initialized.ollama = true
			vim.b.minuet_virtual_text_auto_trigger = true
		else
			vim.cmd("Minuet virtualtext enable")
		end
	elseif provider == "copilot" then
		if not M.initialized.copilot then
			require("copilot").setup({
				panel = { enabled = false },
				suggestion = {
					enabled = true,
					auto_trigger = true,
					hide_during_completion = false,
					keymap = {
						accept = false,
						accept_word = false,
						accept_line = false,
						next = false,
						prev = false,
						dismiss = false,
					},
				},
			})
			M.initialized.copilot = true
		else
			vim.cmd("Copilot enable")
		end
	end
	if persist ~= false then
		opts.provider = provider
		vim.fn.mkdir(vim.fn.stdpath("state"), "p")
		vim.fn.writefile({ vim.json.encode(opts) }, vim.fn.stdpath("state") .. "/ai.json")
		vim.notify("AI: " .. provider)
	end
end
function M.accept()
	if M.provider == "ollama" and M.initialized.ollama then
		local action = require("minuet.virtualtext").action
		if action.is_visible() then
			action.accept()
			return true
		end
	elseif M.provider == "copilot" and M.initialized.copilot then
		local s = require("copilot.suggestion")
		if s.is_visible() then
			s.accept()
			return true
		end
	end
	return false
end
function M.action(name)
	if M.provider == "ollama" and M.initialized.ollama then
		require("minuet.virtualtext").action[name]()
	elseif M.provider == "copilot" and M.initialized.copilot then
		require("copilot.suggestion")[name]()
	end
end
function M.setup()
	vim.api.nvim_create_user_command("MayaAI", function(cmd)
		M.select(cmd.args)
	end, {
		nargs = 1,
		complete = function()
			return { "ollama", "copilot", "off" }
		end,
	})
	for key, name in pairs({ ["<C-l>"] = "next", ["<M-[>"] = "prev", ["<C-]>"] = "dismiss" }) do
		vim.keymap.set("i", key, function()
			M.action(name)
		end, { desc = "AI " .. name })
	end
	if vim.env.MAYA_NVIM_NO_AI ~= "1" then
		vim.api.nvim_create_autocmd("InsertEnter", {
			once = true,
			callback = function()
				M.select(settings().provider or "off", false)
			end,
		})
	end
end
return M
