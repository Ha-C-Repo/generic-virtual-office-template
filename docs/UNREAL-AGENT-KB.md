# Unreal Engine + Claude Code Agent - Knowledge Base

Source video: https://www.youtube.com/watch?v=uPmy2ERmkVU ("Claude Just Became A CRACKED Video Game Designer", channel "AI for Mortals" / Pat Simmons, uploaded 2026-06-24, runtime 20:25)
Agent harness repo: https://github.com/per-simmons/unreal-agent-harness
Epic official plugin: https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin
Watched and reconciled: 2026-06-24

## Provenance and confidence note

This KB was first drafted from the two source repositories (read live from GitHub on 2026-06-24). It was then reconciled against the actual video, which was machine-watched on 2026-06-24 using the bundled `/watch` pipeline (yt-dlp download, ffmpeg frame extraction at 1024px, native YouTube captions). The 20:25 video was watched in three focused passes - 0:00 to 7:00, 7:00 to 14:00, and 14:00 to 20:25 - at roughly one frame every 4 to 6 seconds, with the full caption transcript (236, 212, and 208 segments per pass). Every claim below that carries a timestamp was confirmed from an on-screen frame or the spoken caption at that time. Items read directly off on-screen text (terminal output, the Unreal Output Log, plugin browser, `.mcp.json`, doc pages) are HIGH confidence. Items heard in narration but not shown as text are MEDIUM. Where the earlier repo-only draft disagreed with what aired, the on-camera value wins and the change is called out. The video was watched, so former Open Question 1 is closed.

Key corrections the watch produced versus the repo-only draft: the in-editor MCP plugin is authored by Anthropic, not Epic; the demo ran on port 8001, not 8123; the Epic official Claude Code plugin is a real companion repo but is NOT the thing used on camera; capture was viewport stills plus live Play-In-Editor only, with no Sequencer and no Movie Render Queue shown; and FBX is the demonstrated import format.

---

## Video Notes

### What Was Demonstrated

Pat Simmons, who states on camera he had never opened Unreal Engine before that day (02:11, 20:05), points Claude Code at a running Unreal Engine 5.8 editor and builds real 3D scenes almost entirely by typing natural-language prompts. The repo frames the agent as having four capabilities: hands (drive the editor over MCP), eyes (capture and decode the viewport so it can see its own work), knowledge (local harness docs), and a QA loop (see, act, check, fix). The video bears this out.

The on-camera arc, by window:

1. Setup and first cube (roughly 02:31 to 07:18). He reads Epic's "Unreal MCP" docs, has Claude write `.mcp.json`, installs UE 5.8, enables the plugin, hits a port conflict, fixes it, connects with `/mcp`, discovers only one toolset is exposed, enables AllToolsets, and proves the chain by spawning a test cube ("ClaudeHelloCube") through `SceneTools.add_to_scene_from_asset`.

2. A "Dubai-style" futuristic city (roughly 09:32 to 13:41). Working inside Epic's free City Sample project, he prompts Claude to build a realistic Dubai-like city: supertall hero towers, a safe water plane, golden-hour lighting, scattered trees, and a droppable playable character. Claude plans in plan mode, reads the harness docs, fans out read-only QA subagents to critique each phase, builds across about 45 minutes, then he hits Play and walks the city (fixing motion blur and frame rate live via console variables).

3. Real New York City via Cesium (roughly 14:00 to 17:30). He installs Cesium for Unreal from GitHub source (the marketplace build did not support 5.8), generates a Cesium ion token, enables Google's Map Tiles API in Google Cloud, and streams Google Photorealistic 3D Tiles to reconstruct NYC, fixing render and rebase issues as they appear.

4. A custom Neo-Gothic cathedral-skyscraper via headless Blender (roughly 17:30 to 20:00). Claude spawns a research subagent to gather Neo-Gothic references, builds a facade kit in headless Blender, exports FBX, wires it into the PCG building generator, places one massive Nanite cathedral into the City Sample city, then QAs and refines it against the references.

The intro reel (00:30 to 02:26) previews finished results: an NYC skyline (Cesium), a Paris / Beaux-Arts block, an Art Deco block with a Chrysler-style spire, the futuristic glass city, and a playable third-person character walking a street.

A recurring teaching point matches the repo: the agent cannot see unless you build it eyes, cannot click dialogs it cannot see (sign-in and marketplace steps still need a human), and heavy 3D work is fragile (GPU and config crashes, port conflicts, scale and rebase bugs), so the real skill is diagnostics, logging, and small reversible steps. The chase-cam aircraft (Boeing 787 on Cesium's DynamicPawn) and the stage-by-stage self-building PCG city described in the earlier draft are repo-documented builds from `BUILD-LOG.md`; they were NOT the on-camera demos in this video and should not be cited as "shown in the video."

### Agent Harness Setup

The harness drives Unreal through the official in-editor Unreal MCP plugin that ships experimental in UE 5.8. The on-screen Plugin Browser (frames at 08:00 to 08:20) shows two relevant plugins, both Version 1.0 and both tagged Experimental:

- "Unreal MCP" - by Anthropic. Description: "(Model Context Protocol) server implementation for Unreal Engine." This is the in-editor MCP server. The plugin's source-tree and console identifier is `ModelContextProtocol`; "Unreal MCP" is the friendly name in the browser.
- "MCP Client Toolset" - by Epic Games, Inc. Description: an adapter that lets toolset-registry clients connect to local or private MCP servers.

The Epic docs page shown on camera (02:32) is https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor and states: "Unreal MCP embeds an MCP server inside the Unreal Editor process so that any MCP-compatible AI agent, such as Claude Code, Cursor, or the MCP Inspector, can drive the editor over a local HTTP connection."

Setup as performed on camera, on macOS (presenter is `patsimmons` on an Apple M4 Max, 64 GB RAM, 1 TB):

1. Install Unreal Engine 5.8 via the Epic Games Launcher. On macOS the Metal toolchain is downloaded separately. UE plus a sample needs a couple hundred GB free (03:24).
2. Open a project. The MCP plugin is enabled per-project, not globally (03:50, restated 09:14 when he re-runs setup for the City Sample project). The agent drives whatever project is currently open.
3. Enable the plugin. Edit, Plugins, search "Unreal MCP", enable it, restart the editor. By default this exposes only a minimal toolset, so also enable AllToolsets and PythonScriptPlugin to get the building toolsets (see MCP Tools Available).
4. Have Claude write the client config. On camera he simply told a fresh Claude session to "set up MCP server Unreal Engine, read docs" and Claude created `.mcp.json` itself (02:37 to 02:49). The exact file shown:
   ```json
   {
     "mcpServers": {
       "unreal-mcp": {
         "type": "http",
         "url": "http://127.0.0.1:8000/mcp"
       }
     }
   }
   ```
   The console command `ModelContextProtocol.GenerateClientConfig ClaudeCode` writes the same file; the docs name it on screen but he did not run it in the watched footage.
5. Start the server. Either set Auto Start Server in Editor Preferences, or run `ModelContextProtocol.StartServer <port>` in the editor console. Auto Start Server only takes effect at editor launch; the StartServer console command and its port argument override the preference immediately.
6. Connect. Launch Claude Code from the project root and run `/mcp` (and `/mcp reconnect` after any editor relaunch). The server is registered to Claude Code under the name `unreal-mcp`. Verify with `SceneTools.get_current_level`, which returns the current level path when connected.
7. Clone the harness: `git clone --depth 1 https://github.com/per-simmons/unreal-agent-harness.git`. On camera it is cloned into `/tmp/unreal-agent-harness` and the agent is told to read its docs ("we documented this somewhere in this harness, find the solution").

Protocol and transport: streamable HTTP MCP server bound to 127.0.0.1, default port 8000, URL path `/mcp`. The MCP protocol version negotiated on camera is `2025-11-25` (Output Log: "Client requested protocol version '2025-11-25', negotiated '2025-11-25'", with a session id and "Listing tools (3)"). The connection drops on every editor relaunch and needs a `/mcp` reconnect, so the workflow avoids unnecessary relaunches.

Port, corrected. The default is 8000. On camera the demo ran on 8001, not the 8123 the repo-only draft cited. Port 8000 was already taken by the presenter's own local Python app (a self-built Whisper-Flow-style dictation tool on `python main.py`), which produced an HTTP 404 at `http://127.0.0.1:8000/mcp` on the first `/mcp`. He diagnosed it with `lsof -nP -iTCP@8000 -sTCP:LISTEN`, then changed Server Port Number to 8001 under Edit, Editor Preferences, General, Model Context Protocol (that pane also exposes Server Url Path `/mcp`, Auto Start Server, and Enable Tool Search), ran `ModelContextProtocol.StartServer 8001`, got an HTTP 200 handshake, and reconnected. Lesson: pick a free port and set it consistently in the Editor Preference and the generated `.mcp.json`. The 8123 figure from the draft did not appear on camera; treat 8001 (this demo) and 8000 (default) as the real values.

The harness also ships a separate Python remote-execution path (`ue_remote/`) over UE's PythonScriptPlugin remote-execution endpoint, used as a secondary QA and inspection path and to call live UFUNCTIONs the MCP sandbox cannot reach. On camera the harness notes reference this remote on port 30010 (UE's default remote-execution port) and use it for the Cesium georeference rebase (a UFUNCTION). On macOS this path can hang the editor on boot, so the harness keeps it off by default.

### MCP Tools Available

The Unreal MCP server uses tool search by default. The Output Log shows only three tools listed at the protocol level ("Listing tools (3)"); the documented trio is `list_toolsets`, `describe_toolset`, and `call_tool`. Individual tools are dispatched server-side through `call_tool`. The Output Log makes the dispatch shape explicit: "Running tool: 'call_tool'" then "Dispatching toolset tool: '<full.path>'", where the path is either lowercase `editor_toolset.toolsets.<group>.<GroupTools>.<method>` or PascalCase `EditorToolset.EditorAppToolset.<Method>`. In Claude Code these surface as collapsed "Called unreal-mcp" lines.

The default-state gotcha, confirmed on camera and corroborated by a Reddit post he opens (r/unrealengine, "Unreal MCP (official 5.8) only showing one toolset, what am I missing?"): a freshly enabled plugin exposes only `ToolsetRegistry.AgentSkillToolset`, whose four tools (`ListSkills`, `GetSkills`, `CreateSkill`, `UpdateSkill`) only manage AgentSkill assets and cannot spawn actors or touch the level. To get the building palette you must enable the AllToolsets plugin plus PythonScriptPlugin, restart, and run `ModelContextProtocol.RefreshTools` in the editor console (or `list_toolsets` from the agent to re-scan). Once AllToolsets is live, Claude reports "the full palette (under 60 toolsets): SceneTools, StaticMeshTools, MaterialTools, ActorTools, Niagara, Sequencer, the works."

Console commands seen: `ModelContextProtocol.StartServer <port>`, `ModelContextProtocol.RefreshTools`, `ModelContextProtocol.GenerateClientConfig ClaudeCode`.

Exact tool dispatch strings observed in the Output Log and terminal:

- `SceneTools` - scene and actors. Confirmed: `editor_toolset.toolsets.scene.SceneTools.get_current_level`, `...SceneTools.add_to_scene_from_asset`.
- `AssetTools` - asset and content browser. Confirmed: `...asset.AssetTools.list_folders`, `...AssetTools.get_plugin_content_paths`, `...AssetTools.find_assets`, `...AssetTools.save_assets`.
- `ObjectTools` - generic UObject property access. Confirmed: `...object.ObjectTools.get_properties`, `...ObjectTools.set_properties`. Property set only, no method invocation.
- `ActorTools` - actor transforms. Confirmed in harness QA docs: `...actor.ActorTools.get_actor_transform`.
- `EditorAppToolset` - camera and capture and PIE. Confirmed: `EditorToolset.EditorAppToolset.SetCameraTransform`, `EditorToolset.EditorAppToolset.CaptureViewport`, `EditorAppToolset.StartPIE`.
- `StaticMeshTools`, `MaterialTools`, `Niagara`, `Sequencer`, and "PCG" appear by name in the AllToolsets palette listing but were not individually dispatched on screen in the watched windows.

The Epic official plugin documents a much larger domain surface (Blueprints, full Sequencer, Niagara, Control Rigs, State Trees, Behavior Trees, UMG, GAS, C++ automation testing); see Epic Official Plugin Notes. Note that surface comes from the Epic plugin's README, not from this video.

### Workflow: Prompt to Scene

The core loop the harness calls "how the agent sees and builds", confirmed on camera:

1. Act. Build via `call_tool` dispatching a toolset method, for example `SceneTools.add_to_scene_from_asset` to place a mesh.
2. Capture. Position the editor camera with `EditorAppToolset.SetCameraTransform`, then call `EditorAppToolset.CaptureViewport`. CaptureViewport returns a 3 to 5 MB base64 PNG. The harness rule, shown on screen, is to always decode big captures to a file, never inline ("Big captures: CaptureViewport returns 3-5 MB base64 - always decode to a file, never inline").
3. Decode. Run a small Python decoder on the saved capture blob. On camera the script is `python3 /tmp/ue_decode.py /tmp/ue_<name>.png`, which reads the MCP capture file `mcp-unreal-mcp-call_tool-<epoch>.txt` and writes a viewable PNG. The harness repo also carries `ue_qa.py` and `decode_capture.py` for the same job; the on-screen invocation was `ue_decode.py`.
4. Read. Claude reads the decoded PNG to reason about the scene.
5. Correct. Fix and repeat.

QA is done by fanning out read-only subagents. On camera the prompt explicitly says to "fan out a bunch of agents" and "have agents QA the work", and the harness plan lists a three-angle sweep (aerial / layout, street / aesthetics, facade or player-eye / gameplay feel), comparing captures against reference images and refining. Two hard constraints, both shown: one editor and one game thread, so the main agent is the only MCP writer and all mutations are serialized while QA agents stay read-only; and UFUNCTIONs are not callable via MCP, so things like editing a Blueprint-driven sun mean editing the raw DirectionalLight actor instead. The harness also exposes the Python remote (port 30010) as a secondary inspection path when MCP alone is not enough.

### Asset Import Capability

FBX is the demonstrated import format. The Neo-Gothic build writes `neo_gothic_cathedral.fbx` (and detailed variants) from headless Blender and imports it into Unreal as a Nanite static mesh `SM_NeoGothicCathedral`. No OBJ, glTF, GLB, or IFC import was shown on camera. The repo states the MCP `StaticMeshTools.import_file` path accepts FBX and OBJ only and that GLB must be converted to FBX in headless Blender first; the video is consistent with that (Blender to FBX to Unreal).

For real-world city geometry the video uses streaming, not file import: Cesium for Unreal streams Google Photorealistic 3D Tiles (the 3D Tiles format) for NYC. A free Path B uses Cesium ion assets (Cesium World Terrain plus Cesium OSM Buildings plus Bing aerial imagery) instead of the Google tiles.

Headless Blender, as shown: the agent writes a Blender Python script and runs Blender with no UI ("I don't even have Blender downloaded... Claude just writes a script"). Separately, the video shows a Claude Desktop plus BlenderMCP setup (BlenderMCP server on port 9876, Blender 4.3.2, tools `get_scene_info`, `create_object`, `execute_blender_code`) as an illustration of interactive Blender-over-MCP; the actual cathedral build used headless Blender driven by the harness, not that interactive BlenderMCP.

Realistic ready-made assets come from Fab (Epic's marketplace), for example the City Sample pack and a free palm-tree pack. Fab requires an Epic login and the user's clicks to add to a project, so it is a manual gate; on camera Claude states plainly it cannot do the Fab download itself.

### Footage Capture Capability

In this video, all stills and footage are captured by `EditorAppToolset.CaptureViewport` (viewport screenshots from a posed editor camera), decoded by the Python decoder, plus live Play-In-Editor walkthroughs. No Sequencer and no Movie Render Queue were used or shown. Sequencer appears only as a name in the AllToolsets palette list, never invoked. PIE is started via `EditorAppToolset.StartPIE`, and the playable character is `BP_CitySamplePlayerCharacter`; the gameplay QA gate is "PIE possession equals walkable."

Performance for capture and play was tuned live with console variables, shown on screen: `r.MotionBlurQuality 0`, `r.ScreenPercentage 60`, `r.MaxFPS 60` (City Sample leans on TSR and renders at a reduced screen percentage then upscales), and the motion-blur fix was baked permanently into the scene's PostProcessVolume via `ObjectTools.set_properties` because console variables reset when PIE stops. Deeper render fixes were written into `DefaultEngine.ini` because some startup cvars cannot be overridden from the console: `r.RayTracing=False`, `r.Lumen.HardwareRayTracing=0`, `r.DynamicGlobalIlluminationMethod=0`, `r.ReflectionMethod=0`, and crucially `r.Shadow.Virtual.Enable=0` (the real frame-rate fix on the Cesium NYC scene was disabling the sun's dynamic shadows, since the streamed tiles already carry baked shadows).

The Epic official plugin DOES document a full Sequencer toolset (Level Sequences, keyframe animation, camera management, Control Rig integration, FBX import and export), which would be the supported path for true cinematic capture, but that is from the Epic plugin README, not this video. Movie Render Queue is not called out as an MCP tool in either repo and remains an Open Question. The video confirms that for the work it showed, viewport capture plus PIE was the only capture method used.

### Limitations and Failure Modes

All confirmed on camera unless noted:

- The agent cannot click dialogs it cannot see. Epic login (to add City Sample), Fab add-to-project (palm pack), Cesium ion sign-in, and Google Cloud billing all required the human. Claude says so explicitly.
- One editor, one game thread. The main agent is the only MCP writer; QA agents are read-only. Mutations are serialized.
- Default exposes only one toolset (AgentSkillToolset). Until AllToolsets plus PythonScriptPlugin are enabled and `RefreshTools` is run, the agent literally cannot place actors. Independently reported by a Windows 11 user on Reddit.
- Port conflict. Default 8000 collided with the presenter's own Python app and returned HTTP 404. Fixed by moving to 8001 in Editor Preferences and `StartServer 8001`. CrashReporter can also squat the port after a crash (repo note).
- MCP must be set up per project, not once globally.
- UFUNCTIONs are not callable via MCP. The Cesium georeference rebase is a UFUNCTION; setting the origin via MCP property-write bypasses Cesium's rebase setter, leaving tiles at earth-center (about 6,000 km from origin) where float precision breaks rendering. The shown fix is to fire BeginPlay via Simulate so the real rebase runs, with a `cesium_rebase.py` remote-exec calling `set_origin_longitude_latitude_height` as the backstop.
- Version incompatibility. Cesium for Unreal's marketplace build did not support 5.8, so it was built from GitHub source (Cesium for Unreal v2.27.0) with EngineVersion bumped 5.5.0 to 5.8.0. An older City Sample build targets 5.4 and "won't work with the Unreal MCP server"; use the 5.8-compatible assets.
- Render-budget warnings. City Sample ships with ray tracing and hardware Lumen on; the editor warned that ray-tracing geometry exceeded 20 percent of the always-resident budget and that cached Lumen and real-time sky-capture lighting would clip. Fixed in `DefaultEngine.ini` (cvars above) plus one restart.
- Scale and exposure traps. The Blender cathedral first rendered bleached white; fixed as an exposure issue (sun dropped to about 1100 lux, exposure pulled to roughly -1.3 EV, plain pale limestone material, low normal strength). Always sanity-check meters versus centimeters on imports (the repo's 100x scale trap).
- Build latency. The Dubai city took about 45 minutes to generate; the 91 GB City Sample download took over an hour. These are real time costs.
- Honest output gaps. Claude self-reported that the Dubai result read "more American downtown than Dubai" and that lighting and tree placement glitched, then iterated. The tool produces drafts that need review, not finished art on the first pass.
- macOS boot hang (repo note). Enabling UE Python Remote Execution can hang the editor on boot on macOS; keep it off on Mac.

### Requirements

- Unreal Engine 5.8 with the experimental Unreal MCP plugin (Anthropic, v1.0), plus AllToolsets and PythonScriptPlugin enabled.
- Claude Code as the driving agent. On camera: Claude Code v2.13.165, model Opus 4.8 (1M context), a Claude Max plan.
- OS shown: macOS Apple Silicon (Apple M4 Max, 64 GB RAM, 1 TB SSD). Windows or DX12 is supported by UE; several harness hazards (remote-exec boot hang, some Metal GPU crashes) are macOS-only and should be revalidated on Windows.
- Storage: City Sample is about 91 GB (on-screen cache size 91.05 GB); a couple hundred GB free for UE plus samples; fast SSD strongly recommended.
- Python 3 for the capture decoder (`ue_decode.py` / `ue_qa.py`). Headless Blender (4.3.x shown) for modeling jobs. imagemagick only for the optional refdiff tool.
- Cost. Software floor is effectively zero (free engine plus FOSS), but real paid items appeared: Google Photorealistic 3D Tiles now require your own Google Maps Platform API key with the Map Tiles API enabled and a billing account attached (Google Cloud project `nyc-unreal-demo`, service `tile.googleapis.com`, tileset URL `https://tile.googleapis.com/v1/3dtiles/root.json?key=YOUR_KEY`). A Cesium ion free account (5 GB tier, scopes `assets:read, geocode`) is the non-commercial Path B alternative. Fab assets need an Epic login. No paid Claude tier beyond the Claude Max plan shown was called out.

---

## Epic Official Plugin Notes
(from EpicGames/unreal-engine-skills-for-claude-code-plugin, version 3.0.2, author Thomas Mansencal at Epic Games, MIT license)

Important: this Epic plugin is a confirmed companion repo, but it was NOT the thing used in the video. On camera the presenter used (a) the in-editor Unreal MCP plugin authored by Anthropic and (b) the per-simmons community harness of markdown docs and Python scripts. He browsed skills.sh and saw other community Unreal skills (quodsoler, dstn2000, icn33), not this Epic plugin. The notes below are repo-sourced reference, useful for the application designs that follow, and should be labeled as such rather than as "shown in the video."

### What It Provides

A Claude Code plugin that controls the Unreal Editor via the same in-editor MCP server. It contributes:

- A `unreal-mcp` skill: instructions and workflows for driving the editor via MCP, including the discover-then-dispatch flow (`list_toolsets`, `describe_toolset`, `call_tool`), safety rules, and reference docs (`setup.md`, `operations.md`).
- A `create-toolset` companion skill: how to author or extend a C++ or Python toolset registered with `ToolsetRegistry` and exposed as AI-callable tools (`UFUNCTION(meta = (AICallable))`), including conventions, error handling, and automation tests.
- An `unreal-skill` companion skill: how to author, update, or review an Agent Skill a project registers (reached at runtime through `AgentSkillToolset.ListSkills` and `GetSkills`).
- A SessionStart hook (`hooks/unreal-context.sh`, bash) that walks up from the working directory to detect an Unreal project (`.uproject` or `GenerateProjectFiles`) and injects a note so Claude defaults to UE conventions and prefers the `unreal-mcp` skill. Requires bash on PATH (Git Bash or WSL on Windows).

### Setup vs Agent Harness

These are two compatible tracks targeting the SAME in-editor MCP server, not competitors.

- The Epic plugin is the official, supported skill-and-workflow layer for Claude Code. It packages the usage contract, safety rules, setup and recovery docs, and the SessionStart hook, and installs via `/plugin marketplace add` then `/plugin install`. It ships no static `.mcp.json`; you generate one with `ModelContextProtocol.GenerateClientConfig ClaudeCode`. Default port 8000, path `/mcp`.
- The per-simmons harness is the community "batteries plus glue" layer built for the video. It adds the things the official plugin does not: the vision loop (`ue_qa.py` / `ue_decode.py` capture and decode), launch and crash-log scripts (`ue_launch.sh`, `ue_crashlog.sh`), the Python remote-execution path (port 30010) for UFUNCTIONs the MCP sandbox cannot reach, Cesium and PCG recipes, Blender headless modeling jobs, and Gaussian-splat tooling (the `splat/` folder). The video ran it on port 8001 by local choice after the 8000 conflict.

Compatibility verdict: same in-editor plugin, same protocol, same toolsets. You can install the Epic plugin for the supported skill and hook layer and still use the harness scripts alongside it. The collision to watch is the port number; pick one and set it consistently.

### Toolsets Available

The Epic README lists hundreds of tools across 30-plus toolsets, auto-discovered via MCP, covering Actors and Scene, Blueprints, Assets and Content, Materials, Meshes and Textures, Animation (Control Rigs, State Trees, Behavior Trees), Sequencer (Level Sequences, keyframes, cameras, Control Rig, FBX import and export), VFX (Niagara, Dataflow), UI (UMG, Slate), Gameplay (tags, GAS, Game Feature Plugins, physics), Testing (C++ automation tests), Editor (screenshots, camera, selection, content browser, log inspection), Scripting (the ProgrammaticToolset Python sandbox), and Live Coding (`LiveCodingToolset.CompileLiveCoding`).

Security note from Epic: installing the plugin gives Claude broad live access to the running editor. localhost is not a trust boundary. `execute_tool_script` runs arbitrary Python in the editor process. Avoid `--dangerously-skip-permissions` while loaded. Save and commit before long MCP-driven sessions because tools mutate, move, or delete VCS-tracked assets in a single call. The video reinforces this: the harness rule is to save only after each phase verifies so a bad step can be reverted with `load_level`.

---

## Application Map - All Projects

The following are forward-looking implementation designs for Your Company and the other businesses. They are syntheses built on the verified capabilities above. Where a capability does not yet exist or is unproven, it is flagged as a GAP. Per Your Company governance, none of this changes validated tonnage, AISC weights, or rates; the 3D pipeline is visualization and QC only.

### Your Company: Bid Estimating Pipeline

Goal: build every project in Unreal before a bid ships, capture renders and a flythrough, and embed that footage into the bid package so the client sees the finished structure before steel is cut.

Proposed pipeline, with the MCP tool that handles each step:

1. Source geometry from Tekla. Tekla Structures exports the detailing model. The proven import into UE is FBX (the video imports a Blender-built FBX as a Nanite static mesh; the repo confirms `StaticMeshTools.import_file` accepts FBX and OBJ only). GAP: IFC is not directly importable through MCP. Tekla can export IFC, but UE has no native IFC import in either repo. Recommended path: export FBX directly from Tekla, or Tekla to IFC to FBX via a converter, or Tekla to Datasmith via Twinmotion Direct Link where the Tekla version supports it. Confirm the Tekla export route first. See Open Question 2.
2. Import into UE. For a single combined FBX, drive `StaticMeshTools.import_file`. Always check bounds first and sanity-check meters versus centimeters (the 100x scale trap), and correct axis if the source was Y-up.
3. Assemble the scene. Place the structure with `SceneTools.add_to_scene_from_asset`, set transforms with `ActorTools.set_actor_transform`, and add a ground plane, sky, and a neutral daylight DirectionalLight via `ObjectTools.set_properties`. Claude reasons about placement using the capture-decode loop: place, `EditorAppToolset.SetCameraTransform`, `CaptureViewport` from three angles, decode, read, correct.
4. Materials. Apply a steel material via `MaterialTools` so the frame reads as structural steel. The video's lesson on plain materials plus measured exposure (low normal strength, watch for blown-out highlights) applies directly.
5. Capture stills and a flythrough. For stills, pose the editor camera and `CaptureViewport`, exactly as the video does. GAP: the video did NOT use Sequencer or Movie Render Queue. For a true cinematic flythrough the Epic Sequencer toolset is the documented path, but it is unproven in either repo's footage; the proven fallback is a numbered viewport-frame sequence flown along a camera path and assembled by FFmpeg or OpenMontage. See Open Question 3.
6. Embed in the bid package. The page-1 cover already takes a `render_path` and the pricing page takes a `frame_image_path` (per CLAUDE.md bid document rules). The Unreal still becomes a new render artifact under `<bid>/renders/`, labeled as a visualization, never a member-accuracy claim. The Tekla-based `_TEKLA.png` remains the member-accurate source.

Visual deliverable format, by feasibility:
- Most feasible now: still renders captured from the editor viewport, embedded as page-1 cover and pricing-page frame image. This is exactly what the video proved.
- Feasible but unproven: a short cinematic flythrough via Sequencer, or a viewport-frame sequence to OpenMontage. Useful for emailed follow-ups and the website, not the static PDF.
- Aspirational: an interactive Pixel Streaming embed. Highest effort, see Web 3D Graphics.

Ivan's takeoff integration: the BOM maps to Unreal scene objects. Each member type becomes a static mesh actor class or an instanced static mesh; member quantities drive instancing counts; column grid intersections set placement. Reuse the existing `<bid>/model/<bid>_coordinate_members.json` (member endpoints and grid placement) as the source for `SceneTools.add_to_scene_from_asset` plus `ActorTools.set_actor_transform`. The visualization never feeds back into validated tonnage; AISC weights stay sourced from `bridge/aisc_validator.py`.

### All Businesses: Video Production via OpenMontage

Unreal-captured footage replaces stock footage for marketing video. Flow:

1. Build a branded 3D environment in Unreal (Style 01 industrial cinematic for Your Company, Style 02 corporate or luxury for Pinnacle; never blend brands in one deliverable, per the Video Creation firewall).
2. Capture. The proven method is posed `CaptureViewport` frames plus live PIE, exactly as in the video. Sequencer camera moves are the richer but unproven path.
3. Export from Unreal. A numbered PNG frame sequence from `CaptureViewport` is the proven path today.
4. Hand off to FFmpeg or OpenMontage. FFmpeg assembles the PNG sequence into a clip; OpenMontage handles composition. Video work writes to `Video Creation/ACTIVE_PROJECTS/<Name>/` and `OUTPUTS/<Name>/`, never into bid folders.

Note OpenMontage is currently NOT installed (host-side Windows finish pending, needs numpy), so this track is blocked on that plus a Windows GPU host.

### All Businesses: Web 3D Graphics

Two browser-embed options:
- Pixel Streaming: Unreal renders on a GPU host and streams an interactive feed to a browser. Richest option, but needs an always-on GPU host and is not demonstrated in either repo. Infrastructure-heavy; later phase.
- WebGL or glTF export: export the scene or a key asset and embed a lightweight web viewer (model-viewer or three.js). Cheaper, no streaming host, but loses Unreal-grade lighting. Good for a single product or structure spinnable in the browser.

Neither repo demonstrates the web-embed step, so both are GAP items. WebGL or glTF is the pragmatic first target; Pixel Streaming is the premium target.

### AIRS: Environment and Set Production

Unreal as the production environment for AI-generated sets. Claude builds the set (City Sample base, a PCG environment, or a Cesium real-world location, all three proven in the video), dresses it via the toolsets, and captures. Capture mirrors the video-production track. Integration with AIRS narrative steering: the agent receives shot direction and translates it into MCP tool calls (place set pieces, position cameras with `SetCameraTransform`, set lighting via `ObjectTools.set_properties`), then captures. Most exploratory application; depends on the same Sequencer and capture questions flagged above.

---

## Implementation Roadmap

### Phase 0 - Confirm Setup (no build yet)

Install Unreal Engine 5.8 on a capable machine (Windows or DX12, or Mac Apple Silicon, 64 GB RAM target, fast NVMe). Open a test project, enable the Unreal MCP plugin plus AllToolsets and PythonScriptPlugin, restart, and start the MCP server. Have Claude write or generate `.mcp.json` and connect with `/mcp`. Optionally install the Epic official plugin for the supported skill and SessionStart hook. Smoke test: place a cube via `SceneTools.add_to_scene_from_asset`, `CaptureViewport`, decode, read - the exact "ClaudeHelloCube" check from the video. Pick and lock one free port (avoid local Python apps that squat 8000). Outcome: a verified "agent is driving Unreal" baseline. Joseph task.

### Phase 1 - Your Company Bid Pipeline Proof of Concept

One Tekla model to one rendered image. Confirm the Tekla-to-FBX route on a real, complete bid (Open Question 2); export FBX; import via `StaticMeshTools.import_file`; bounds-check and correct scale; assemble with ground plane, sky, neutral daylight, and a steel material; capture three-angle stills with `SetCameraTransform` plus `CaptureViewport`; pick the hero still; embed it as the page-1 cover render through `documents.generate_proposal(render_path=...)`. Validate against the bid document rules and `validate_bid_output.py`. Reuse `<bid>/model` coordinate-member JSON as the placement source. Outcome: a real structural-steel render in a real bid layout, labeled as visualization.

### Phase 2 - Video Capture Pipeline

A capture path to OpenMontage. The video proves viewport-frame capture; start there. Pose a camera path, capture a numbered viewport-frame sequence, assemble with FFmpeg, hand to OpenMontage. Probe whether the Epic Sequencer toolset can drive a higher-quality render (Open Question 3) as an upgrade, not a dependency. Blocked until OpenMontage is installed (Windows finish plus numpy) and a Windows GPU host exists. Outcome: a branded flythrough produced with zero stock footage.

### Phase 3 - Web 3D Embed

Start with WebGL or glTF export of a single structure into a three.js or model-viewer embed, as the cheap proof of concept. If the interactive bar must rise, stand up a Pixel Streaming GPU host. Outcome: a visitor-interactive 3D structure or product on a Your Company, Pinnacle, or DOVA page.

---

## Open Questions

1. CLOSED. The video was watched on 2026-06-24 in three focused passes (0:00 to 7:00, 7:00 to 14:00, 14:00 to 20:25) at 1024px with full captions, and this KB is reconciled against it. No further transcription pass is needed unless a specific sub-second detail is wanted.
2. Tekla to Unreal import route for steel. MCP `import_file` is FBX and OBJ only; IFC is not directly supported. Confirm which path the Your Company Tekla version supports best: direct FBX export, IFC-to-FBX conversion, or Datasmith or Twinmotion Direct Link. Test all three on one complete model, pick the cleanest, document it. Gates Phase 1.
3. Cinematic render output. The video used viewport stills plus PIE only; no Sequencer and no Movie Render Queue were shown. Determine whether the Epic Sequencer toolset can trigger a high-quality render callable from MCP, or whether the reliable path stays a viewport-frame sequence assembled by FFmpeg. Probe the Sequencer toolset with `describe_toolset` once an editor is connected. Gates Phase 2 quality.
4. UFUNCTION reach. The MCP layer cannot call arbitrary UFUNCTIONs (the Cesium rebase was the on-camera example). Decid
---

## Phase 0 - VERIFIED 2026-06-25

Phase 0 is closed. The agent is driving Unreal over MCP end to end. Verified on the office machine, UE 5.8.0, project YourCoMCP, signed in as YourCompany.

What was confirmed. The in-editor MCP server (Anthropic ModelContextProtocol plugin, AllToolsets, PythonScriptPlugin all enabled) listens on 127.0.0.1:8000/mcp, owned by UnrealEditor. A full MCP session ran against it: initialize handshake returned a session id, list_toolsets returned all 52 toolsets, describe_toolset returned the SceneTools schema, get_current_level returned /Temp/Untitled_1, and add_to_scene_from_asset spawned a 3x engine cube named YourCo_Smoke at (0,0,100). The call returned a concrete actor reference (StaticMeshActor_UAID_D843AEF70E1326E802_2030492175) and the editor level went to unsaved with the actor present in the outliner. That is the "agent is driving Unreal" baseline.

Server start. Auto-start was set to False in EditorPerProjectUserSettings.ini after it was implicated in a startup hang; the server is started manually from the editor console with ModelContextProtocol.StartServer 8000. If a launch ever hangs at 0 percent after SDK detection, kill the stuck Turnkey/UAT cmd.exe children and the editor proceeds.

Interface correction (carries into Phase 1). Toolset tools are NOT called by their fully-qualified name. The server exposes three top-level meta-tools only: list_toolsets, describe_toolset, call_tool. To run a toolset tool, call call_tool with toolset_name set to the full registry path (for example editor_toolset.toolsets.scene.SceneTools) and tool_name set to the BARE tool name (for example add_to_scene_from_asset, not the dotted path). Passing the dotted full name as tool_name returns "Tool not found". describe_toolset takes toolset_name. The engine cube asset path is /Engine/BasicShapes/Cube. Avoid find_actors with empty filters during a scripted smoke run; it blocked in testing.

Port discipline holds: 8000 is the locked port and is free on this machine. The earlier note about local Python apps squatting 8000 did not apply here.
or Unreal MCP plugin, shown on screen at 02:32 as the source for the enable steps.
- The in-editor "Unreal MCP" plugin is authored by Anthropic (v1.0, Experimental), with a companion "MCP Client Toolset" by Epic Games (v1.0, Experimental). Source-tree and console identifier: `ModelContextProtocol`.
- https://www.youtube.com/@per_simmons - the AI for Mortals YouTube channel. https://www.aiformortals.co/ - the newsletter and site.
- Cesium for Unreal v2.27.0 (built from GitHub source for 5.8) plus Google Photorealistic 3D Tiles - real-world city streaming. Google tiles now require your own Google Maps Platform API key with the Map Tiles API enabled and billing attached (tileset URL `https://tile.googleapis.com/v1/3dtiles/root.json?key=YOUR_KEY`). Free Path B: a Cesium ion token with Cesium World Terrain, Cesium OSM Buildings, and Bing imagery (non-commercial).
- Epic Fab marketplace - free and paid realistic meshes; Epic login required, manual add-to-project only.
- Epic City Sample (Matrix Awakens) - free Complete Project used as the playable photoreal city, about 91 GB. Use the 5.8-compatible build; an older 5.4 build will not work with the MCP server.
- BlenderMCP (port 9876) plus Claude Desktop and Blender 4.3.2 - shown as an interactive Blender-over-MCP reference; the actual cathedral was built with headless Blender driven by the harness.
- Harness internal docs worth reading directly: `docs/00-GETTING-STARTED.md`, `docs/CITY-SAMPLE-PLAYABLE.md`, `docs/pie-qa-capture.md`, `AGENTIC-GAMEDEV-GUIDE.md`, `BUILD-LOG.md`, and the Cesium and PCG and Blender-detail guides.
- Epic plugin internal docs: `skills/unreal-mcp/SKILL.md`, `skills/unreal-mcp/references/setup.md`, `skills/unreal-mcp/references/operations.md`, `skills/create-toolset/SKILL.md`, `skills/unreal-skill/SKILL.md`.

## Photoreal render recipe (CEO render-quality standard, 2026-06-25)

Every UE render of a structure must match the photoreal bar. Reference look
target and the full cross-engine standard live in the YourDivision office at
`renders/RENDER_QUALITY_STANDARD.md` (RENDER_LOOK_TARGET.png is the approved
twilight reference). Build inside-and-out first, then light it to this recipe.

- GI: Lumen GI + Lumen Reflections ON. Virtual Shadow Maps. Hardware ray
  tracing if the box supports it. High screen percentage / TSR.
- Sky: Sky Atmosphere + Sky Light (real-time capture) for physically based sky
  and reflections. Exponential Height Fog, subtle. Directional Light = sun:
  any sun angle for the chosen time of day (e.g. ~24 deg daylight, low and warm
  for dusk). Time of day is free; what is fixed is photoreal materials, physical
  sky, and a real-looking environment, not a studio void.
- Interior glow: Rect Lights inside the cabin at ~3000K + an emissive material
  on the window and LED, so warm light pours out the open door and the window.
- Materials: PBR. Navy clad steel metallic ~0.1, roughness ~0.35 with a
  roughness/normal detail; beveled edges (mesh bevel or normal detail); glass
  translucent; emissive for window and LED. No flat untextured surfaces.
- Post Process Volume (unbound): manual exposure metered to match, filmic/ACES
  grade, subtle Bloom, Cine Camera DOF, light vignette, grain off.
- Camera: Cine Camera Actor ~35 mm, f/4-7, focus on the subject. Unit sits on a
  real pad, never floating.
- Output: Movie Render Queue or High Resolution Screenshot, 1920 px+, high AA,
  Lumen + DOF on.

Realism of the background matters as much as the object: use a real-capture Sky
Light / HDRI or the Cesium real-world tiles so surroundings and reflections read
true, never a bare void. Reject any render that reads flat, plastic, or over-bright. An AI image
(gpt-image-1) interprets and is illustrative only; it is never the source for a
structural-frame or member-accuracy claim. Your Company bid governance unchanged.
