// Runway Workflow canvas inspector.
// Paste into javascript_tool. Returns nodes, handles, edges, and the active scale factor.
// Use at the start of every session to orient.

(function () {
  const result = {
    scale: {
      browserWidth: window.innerWidth,
      browserHeight: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio,
      // Note: MCP screenshot scale = browserWidth / screenshotWidth.
      // Common screenshot widths: 1568 (1.224x), 1298 (1.479x). Recalibrate per session.
    },
    nodes: [],
    handles: [],
    edges: [],
  };

  document.querySelectorAll(".react-flow__node").forEach((n) => {
    const id = n.getAttribute("data-id");
    const cls = typeof n.className === "string" ? n.className : "";
    const type = cls.match(/react-flow__node-(\S+?)\s/)?.[1] || "unknown";
    const rect = n.getBoundingClientRect();
    result.nodes.push({
      id,
      type,
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    });
  });

  document.querySelectorAll(".react-flow__handle").forEach((h) => {
    const id = h.getAttribute("data-id") || h.id;
    const rect = h.getBoundingClientRect();
    result.handles.push({
      id,
      x: Math.round(rect.x + rect.width / 2),
      y: Math.round(rect.y + rect.height / 2),
      direction: id?.endsWith("-source") ? "out" : id?.endsWith("-target") ? "in" : "?",
    });
  });

  document.querySelectorAll(".react-flow__edge").forEach((e) => {
    result.edges.push(e.getAttribute("data-id") || e.id);
  });

  JSON.stringify(result, null, 2);
})();
