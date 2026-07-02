// Find Runway nodes by their type string.
// Returns id, position, and all handle ids for nodes matching the type query.
//
// Common type strings:
//   text                          (Text input node)
//   gemini-image-3-pro            (Nano Banana Pro image generator)
//   gen4_5-image-to-video         (Gen-4.5 Text+Image to Video)
//   gen4_5-text-to-video          (Gen-4.5 Text to Video)
//   stitch                        (Video stitching)
//   text-to-speech                (TTS)
//   add-audio                     (Mux audio onto video)

(function () {
  const TYPE_QUERY = "gen4_5-image-to-video"; // change me

  const matches = [];
  document.querySelectorAll(".react-flow__node").forEach((n) => {
    const cls = typeof n.className === "string" ? n.className : "";
    const type = cls.match(/react-flow__node-(\S+?)\s/)?.[1] || "";
    if (type.includes(TYPE_QUERY)) {
      const id = n.getAttribute("data-id");
      const rect = n.getBoundingClientRect();
      const handles = [];
      n.querySelectorAll(".react-flow__handle").forEach((h) => {
        handles.push(h.getAttribute("data-id") || h.id);
      });
      matches.push({
        id,
        type,
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        w: Math.round(rect.width),
        h: Math.round(rect.height),
        handles,
      });
    }
  });
  JSON.stringify({ query: TYPE_QUERY, matches }, null, 2);
})();
