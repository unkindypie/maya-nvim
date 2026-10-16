local M = {}
function M.format(model)
  if model:lower():find("mellum", 1, true) then
    return "mellum"
  end
  if model:lower():find("qwen", 1, true) then
    return "qwen"
  end
end
function M.prompt(format, before, after, hints, filename, ft)
  if format == "mellum" then
    local extra = hints ~= "" and ("<filename>lsp-context.txt\n" .. hints .. "\n") or ""
    return extra
      .. "<filename>"
      .. filename
      .. "\n<fim_suffix>"
      .. after
      .. "<fim_prefix>"
      .. before
      .. "<fim_middle>"
  end
  local comment = ({
    python = "# %s",
    lua = "-- %s",
    sh = "# %s",
    ruby = "# %s",
    yaml = "# %s",
    toml = "# %s",
    css = "/* %s */",
    html = "<!-- %s -->",
    markdown = "<!-- %s -->",
  })[ft] or "// %s"
  local extra = ""
  if hints ~= "" then
    local lines = { "LSP context:" }
    vim.list_extend(lines, vim.split(hints, "\n", { plain = true }))
    for i, line in ipairs(lines) do
      lines[i] = comment:gsub("%%s", function()
        return line
      end)
    end
    extra = table.concat(lines, "\n") .. "\n"
  end
  return "<|fim_prefix|>" .. extra .. before .. "<|fim_suffix|>" .. after .. "<|fim_middle|>"
end
function M.options(model, endpoint, format)
  return {
    api_key = function()
      return "ollama"
    end,
    name = "Ollama",
    end_point = endpoint .. "/api/generate",
    model = model,
    stream = false,
    template = {
      prompt = function(before, after)
        return M.prompt(
          format,
          before,
          after,
          require("maya.ai_context").get(),
          vim.fn.expand("%:t"),
          vim.bo.filetype
        )
      end,
      suffix = false,
    },
    get_text_fn = {
      no_stream = function(value)
        return value.response
      end,
    },
    transform = {
      function(request)
        request.body = {
          model = model,
          prompt = request.body.prompt,
          raw = true,
          stream = false,
          keep_alive = "5m",
          options = {
            num_ctx = 4096,
            num_predict = 96,
            temperature = 0.2,
            stop = format == "mellum" and {
              "<|endoftext|>",
              "<filename>",
              "<fim_suffix>",
              "<fim_prefix>",
              "<fim_middle>",
              "<fim_pad>",
            } or { "<|fim_suffix|>", "<|fim_middle|>", "<|endoftext|>", "<|im_end|>" },
          },
        }
        return request
      end,
    },
  }
end
return M
