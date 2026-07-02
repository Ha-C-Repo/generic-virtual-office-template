// Click the Run button on a node of a given type, identified by its data-id.
// Bypasses the MCP coordinate-scaling problem by clicking via DOM lookup.
//
// USAGE: replace NODE_ID with the actual node uuid, paste into javascript_tool.

(function () {
  const NODE_ID = "ea4b0bab-7bdf-4beb-b20b-fb43c9197415"; // change me

  const node = document.querySelector(`[data-id="${NODE_ID}"]`);
  if (!node) {
    JSON.stringify({ error: "node not found" });
  } else {
    // Find the Run button inside this node
    const buttons = node.querySelectorAll("button");
    let runBtn = null;
    buttons.forEach((b) => {
      if (b.textContent.trim().toLowerCase() === "run") runBtn = b;
    });
    if (!runBtn) {
      JSON.stringify({ error: "Run button not found", buttonCount: buttons.length });
    } else {
      runBtn.click();
      JSON.stringify({ clicked: "Run", nodeId: NODE_ID });
    }
  }
})();
