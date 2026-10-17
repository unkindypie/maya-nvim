local M = {}

-- Sweep predicts a replacement window, so a partial response can erase its tail.
-- Prefer abstention over large or unrelated edits; these bounds are not confidence scores.
function M.accept(snapshot, predicted, metadata)
  local original = snapshot.lines
  local before = table.concat(original, "\n") .. "\n"
  local after = table.concat(predicted, "\n") .. "\n"
  if not after:find("%S") or #after - #before > 1200 then
    return false
  end
  local hunks = vim.diff(before, after, { result_type = "indices", algorithm = "histogram" })
  local cursor = snapshot.cursor[1] - metadata.window_start + 1
  local affected, added = 0, 0
  for _, hunk in ipairs(hunks) do
    local old_start, old_count, new_start, new_count = unpack(hunk)
    -- For insertions vim.diff points at the preceding line (possibly zero).
    local start = old_count == 0 and old_start + 1 or old_start
    local finish = start + math.max(old_count - 1, 0)
    if cursor < start - 3 or cursor > finish + 3 then
      return false
    end
    local old_content, new_content = 0, 0
    for i = old_start, old_start + old_count - 1 do
      if original[i]:find("%S") then
        old_content = old_content + 1
      end
    end
    for i = new_start, new_start + new_count - 1 do
      if predicted[i]:find("%S") then
        new_content = new_content + 1
      end
    end
    if old_content > new_content then
      return false
    end
    affected = affected + old_content
    added = added + math.max(new_count - old_count, 0)
  end
  return affected <= 3 and added <= 8
end

return M
