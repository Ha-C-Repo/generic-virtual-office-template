<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Reconciliation Dashboard - {{bid_name}}</title>
<style>
  :root {
    --bg: #0f1115;
    --panel: #161a22;
    --border: #2a2f3a;
    --text: #e6e8ec;
    --muted: #8a93a3;
    --critical: #ff4d4f;
    --high: #ff9f43;
    --medium: #ffd166;
    --low: #6ed3a8;
    --accent: #5aa9ff;
  }
  body { margin:0; background:var(--bg); color:var(--text); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:18px; font-weight:600; }
  .verdict { padding:6px 12px; border-radius:6px; font-weight:600; font-size:13px; letter-spacing:0.5px; }
  .verdict.READY { background:#1f4f3a; color:var(--low); }
  .verdict.REVIEW { background:#5a3d1a; color:var(--high); }
  .verdict.STOP { background:#5a1f24; color:var(--critical); }
  .stats { display:flex; gap:14px; padding:14px 24px; border-bottom:1px solid var(--border); }
  .stat { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:10px 14px; min-width:96px; }
  .stat .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:1px; }
  .stat .value { font-size:22px; font-weight:600; margin-top:4px; }
  .stat.critical .value { color:var(--critical); }
  .stat.high .value { color:var(--high); }
  .stat.medium .value { color:var(--medium); }
  .stat.low .value { color:var(--low); }
  main { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; padding:14px 24px; }
  .panel { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; }
  .panel h2 { margin:0 0 10px; font-size:13px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); }
  .issue { border-top:1px solid var(--border); padding:10px 0; }
  .issue:first-child { border-top:none; }
  .issue .row1 { display:flex; justify-content:space-between; gap:10px; }
  .issue .title { font-weight:600; font-size:14px; }
  .issue .prio { font-size:11px; padding:2px 8px; border-radius:4px; align-self:flex-start; }
  .issue .prio.Critical { background:#5a1f24; color:var(--critical); }
  .issue .prio.High { background:#5a3d1a; color:var(--high); }
  .issue .prio.Medium { background:#5a4d1a; color:var(--medium); }
  .issue .prio.Low { background:#1f4f3a; color:var(--low); }
  .issue .src { color:var(--muted); font-size:12px; margin-top:6px; }
  .issue .action { font-size:13px; margin-top:6px; color:var(--accent); }
</style>
</head>
<body>

<header>
  <h1>Reconciliation Dashboard - {{bid_name}}</h1>
  <span class="verdict {{verdict_class}}">{{verdict}}</span>
</header>

<section class="stats">
  <div class="stat critical"><div class="label">Critical</div><div class="value">{{critical_count}}</div></div>
  <div class="stat high"><div class="label">High</div><div class="value">{{high_count}}</div></div>
  <div class="stat medium"><div class="label">Medium</div><div class="value">{{medium_count}}</div></div>
  <div class="stat low"><div class="label">Low</div><div class="value">{{low_count}}</div></div>
</section>

<main>
  <section class="panel">
    <h2>Scope Gaps</h2>
    {{#gaps}}
    <div class="issue">
      <div class="row1">
        <div class="title">{{title}}</div>
        <span class="prio {{priority}}">{{priority}}</span>
      </div>
      <div class="src">{{req_id}} - {{source_doc}} p{{source_page}}</div>
      <div class="action">{{recommended_action}}</div>
    </div>
    {{/gaps}}
  </section>

  <section class="panel">
    <h2>Orphan Lines</h2>
    {{#orphans}}
    <div class="issue">
      <div class="row1">
        <div class="title">{{title}}</div>
        <span class="prio {{priority}}">{{priority}}</span>
      </div>
      <div class="src">{{line_id}}</div>
      <div class="action">{{recommended_action}}</div>
    </div>
    {{/orphans}}
  </section>

  <section class="panel">
    <h2>Rate Anomalies</h2>
    {{#anomalies}}
    <div class="issue">
      <div class="row1">
        <div class="title">{{title}}</div>
        <span class="prio {{priority}}">{{priority}}</span>
      </div>
      <div class="src">{{line_id}} - {{discipline}} {{unit}}</div>
      <div class="action">{{recommended_action}}</div>
    </div>
    {{/anomalies}}
  </section>
</main>

</body>
</html>
