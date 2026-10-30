local M = { default_model = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0" }
function M.migrate(saved)
  local opts = vim.deepcopy(saved)
  if opts.schema ~= 2 then
    opts.legacy = { model = opts.model, local_mode = opts.local_mode, fim_format = opts.fim_format }
    opts.model = opts.next_edit_model
      or (opts.model and opts.model:lower():find("sweep", 1, true) and opts.model)
      or M.default_model
    opts.engine = nil
  end
  opts.schema = 2
  opts.local_mode, opts.next_edit_model, opts.fim_format = nil, nil, nil
  opts.model = opts.model or M.default_model
  opts.endpoint = (opts.endpoint or "http://127.0.0.1:11434"):gsub("/+$", "")
  opts.engine = opts.engine
    or (opts.model:lower():find("zeta%-2%.1") and "zeta-2.1")
    or (opts.model:lower():find("zeta%-2") and "zeta-2")
    or "sweep"
  opts.context_size = opts.context_size or (opts.engine == "sweep" and 4096 or 8192)
  assert(
    vim.tbl_contains({ "sweep", "zeta-2", "zeta-2.1" }, opts.engine),
    "Local AI engine must be sweep, zeta-2, or zeta-2.1"
  )
  return opts
end
return M
