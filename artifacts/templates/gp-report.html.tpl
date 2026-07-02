<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{project_name}} - GP Report (INTERNAL)</title>
<style>
  @page { size: Letter; margin: 0.6in; }
  body { font-family: "Calibri", "Segoe UI", Arial, sans-serif; color:#111; font-size:10.5pt; line-height:1.4; }
  h1 { font-size:18pt; margin:0 0 4pt; color:#7a1a24; }
  h2 { font-size:12pt; margin:14pt 0 6pt; border-bottom:1pt solid #999; padding-bottom:2pt; }
  .ribbon { background:#7a1a24; color:#fff; padding:6pt 10pt; font-weight:700; letter-spacing:1pt; margin-bottom:10pt; }
  table { width:100%; border-collapse:collapse; margin:4pt 0 8pt; }
  th, td { border:0.5pt solid #999; padding:4pt 7pt; font-size:10pt; vertical-align:top; }
  th { background:#eee; text-align:left; }
  td.num, th.num { text-align:right; }
  .verdict { font-weight:700; padding:3pt 8pt; border-radius:4pt; display:inline-block; }
  .verdict.READY { background:#d3eddf; color:#1f4f3a; }
  .verdict.REVIEW { background:#fff0d3; color:#5a3d1a; }
  .verdict.STOP { background:#f3d3d6; color:#5a1f24; }
  ul { margin:4pt 0 8pt 18pt; }
</style>
</head>
<body>

<div class="ribbon">INTERNAL - YOUR COMPANY - GP REPORT - NOT FOR CLIENT</div>

<h1>{{project_name}} - GP Report</h1>
<p>
  Submission date: {{submission_date}}<br>
  Proposal No.: {{proposal_number}}<br>
  Prepared by: {{preparer}}<br>
  Verdict: <span class="verdict {{verdict_class}}">{{verdict}}</span>
</p>

<h2>1. Cost Breakdown by Phase</h2>
<table>
  <thead>
    <tr><th>Phase</th><th class="num">Qty</th><th>Unit</th><th class="num">Unit Rate</th><th class="num">Extended</th><th class="num">Margin %</th></tr>
  </thead>
  <tbody>
    {{#cost_phases}}
    <tr>
      <td>{{phase}}</td>
      <td class="num">{{qty}}</td>
      <td>{{unit}}</td>
      <td class="num">${{unit_rate}}</td>
      <td class="num">${{extended}}</td>
      <td class="num">{{margin_pct}}%</td>
    </tr>
    {{/cost_phases}}
  </tbody>
</table>

<h2>2. Steel Tonnage Build-up</h2>
<p>
  Fab baseline applied: 11 hr/ton at $145/hr shop. Overhead 1.15x. Engineering at $175/hr folded in.<br>
  AISC Shapes Database v16.0 used for all weight calculations.
</p>
<table>
  <thead><tr><th>Item</th><th class="num">Tonnage</th><th class="num">hr/ton</th><th class="num">Total hr</th></tr></thead>
  <tbody>
    {{#tonnage_rows}}
    <tr><td>{{item}}</td><td class="num">{{tonnage}}</td><td class="num">{{hr_per_ton}}</td><td class="num">{{total_hr}}</td></tr>
    {{/tonnage_rows}}
  </tbody>
</table>

<h2>3. Direct Cost Subtotal and Markups</h2>
<table>
  <tbody>
    <tr><th>Direct cost subtotal</th><td class="num">${{direct_subtotal}}</td></tr>
    <tr><th>Overhead 1.15x</th><td class="num">${{overhead_applied}}</td></tr>
    <tr><th>G&amp;A 7.5%</th><td class="num">${{ga_applied}}</td></tr>
    <tr><th>Margin</th><td class="num">${{margin}}</td></tr>
    <tr><th>Sell price (client proposal)</th><td class="num">${{sell_total}}</td></tr>
    <tr><th>GP %</th><td class="num">{{gp_pct}}%</td></tr>
  </tbody>
</table>

<h2>4. Reconciliation Summary</h2>
<p>
  Critical issues: {{critical_count}}<br>
  High issues: {{high_count}}<br>
  Medium issues: {{medium_count}}<br>
  Low issues: {{low_count}}
</p>
<ul>
  {{#critical_issues}}
  <li><b>{{title}}</b> - {{recommended_action}} ({{source_doc}} p{{source_page}}, {{req_id}})</li>
  {{/critical_issues}}
</ul>

<h2>5. Contract Risk Register</h2>
<table>
  <thead><tr><th>Risk</th><th>Severity</th><th>Clause</th><th>Recommendation</th></tr></thead>
  <tbody>
    {{#contract_risks}}
    <tr><td>{{risk_type}}</td><td>{{severity}}</td><td>{{clause_reference}}</td><td>{{recommendation}}</td></tr>
    {{/contract_risks}}
  </tbody>
</table>

<h2>6. Time-based Preliminaries</h2>
<p>Total duration: {{total_duration_weeks}} weeks. Driving phase: {{driving_phase}}.</p>

<h2>7. Approvals</h2>
<p>
  CEO sign-off: __________________________ (The Owner)<br>
  COO sign-off: __________________________ (Amber)<br>
  Date: ____________
</p>

</body>
</html>
