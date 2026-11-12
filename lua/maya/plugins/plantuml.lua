return {
  {
    "aklt/plantuml-syntax",
    ft = "plantuml",
    cmd = { "PlantumlPreview", "PlantumlStop", "PlantumlExport", "PlantumlSetup" },
    config = function()
      require("maya.plantuml").attach(vim.api.nvim_get_current_buf())
    end,
  },
}
