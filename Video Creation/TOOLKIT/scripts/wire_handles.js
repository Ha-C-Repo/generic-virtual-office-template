// Programmatic wire creation via dispatched PointerEvents.
// Fallback when MCP drag is unreliable.
//
// USAGE: replace SOURCE_ID and TARGET_ID below, then paste into javascript_tool.
// Note: Runway uses React Flow which sometimes ignores dispatched events.
// If this script reports dispatched=true but no edge appears,
// fall back to MCP left_click_drag with coords from get_handle_coords.js.

(function () {
  const SOURCE_ID = "1-{sourceNodeId}-{paramName}-source";
  const TARGET_ID = "1-{targetNodeId}-{paramName}-target";

  function find(id) {
    return document.querySelector(`[data-id="${id}"]`) || document.getElementById(id);
  }

  const src = find(SOURCE_ID);
  const tgt = find(TARGET_ID);

  if (!src || !tgt) {
    JSON.stringify({ error: "handle not found", src: !!src, tgt: !!tgt });
  } else {
    const sr = src.getBoundingClientRect();
    const tr = tgt.getBoundingClientRect();
    const sx = sr.x + sr.width / 2;
    const sy = sr.y + sr.height / 2;
    const tx = tr.x + tr.width / 2;
    const ty = tr.y + tr.height / 2;

    function fire(elem, type, x, y) {
      const ev = new PointerEvent(type, {
        bubbles: true,
        cancelable: true,
        composed: true,
        pointerId: 1,
        pointerType: "mouse",
        isPrimary: true,
        button: 0,
        buttons: type === "pointerup" ? 0 : 1,
        clientX: x,
        clientY: y,
        screenX: x,
        screenY: y,
      });
      elem.dispatchEvent(ev);
    }

    fire(src, "pointerdown", sx, sy);
    for (let i = 1; i <= 5; i++) {
      const fx = sx + (tx - sx) * (i / 5);
      const fy = sy + (ty - sy) * (i / 5);
      fire(document, "pointermove", fx, fy);
    }
    fire(tgt, "pointermove", tx, ty);
    fire(tgt, "pointerup", tx, ty);

    JSON.stringify({
      source: { sx, sy },
      target: { tx, ty },
      dispatched: true,
      verify: "re-run inspect_canvas.js and look for the new edge id under 'edges'",
    });
  }
})();
