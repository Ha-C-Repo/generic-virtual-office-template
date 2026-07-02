// Get exact pixel coordinates for a SOURCE handle and a TARGET handle.
// Returns the actual browser pixels and the MCP-scaled coords for left_click_drag.
//
// USAGE: replace SOURCE_ID and TARGET_ID below, then paste into javascript_tool.
// Drag REVERSE: from TARGET to SOURCE (this direction is more reliable over MCP).

(function () {
  const SOURCE_ID = "1-{sourceNodeId}-{paramName}-source"; // e.g. "1-b469f38f-...-image-source"
  const TARGET_ID = "1-{targetNodeId}-{paramName}-target"; // e.g. "1-ea4b0bab-...-start_frame-target"

  function find(id) {
    return (
      document.querySelector(`[data-id="${id}"]`) ||
      document.getElementById(id)
    );
  }

  const src = find(SOURCE_ID);
  const tgt = find(TARGET_ID);
  if (!src || !tgt) {
    JSON.stringify({ error: "handle not found", src: !!src, tgt: !!tgt });
  } else {
    const sr = src.getBoundingClientRect();
    const tr = tgt.getBoundingClientRect();
    const browserWidth = window.innerWidth;
    // Most MCP screenshots arrive at 1568px wide for a 1920px browser. Scale = 1920/1568 = 1.224.
    // Recalibrate by taking a screenshot and dividing browserWidth by the screenshot width.
    const scale = 1.224;
    const src_x = Math.round(sr.x + sr.width / 2);
    const src_y = Math.round(sr.y + sr.height / 2);
    const tgt_x = Math.round(tr.x + tr.width / 2);
    const tgt_y = Math.round(tr.y + tr.height / 2);
    const out = {
      source_browser_pixel: { x: src_x, y: src_y },
      target_browser_pixel: { x: tgt_x, y: tgt_y },
      mcp_drag_reverse: {
        start_coordinate: [Math.round(tgt_x / scale), Math.round(tgt_y / scale)],
        coordinate: [Math.round(src_x / scale), Math.round(src_y / scale)],
        note: "Use these in mcp__Claude_in_Chrome__computer left_click_drag",
      },
    };
    JSON.stringify(out, null, 2);
  }
})();
