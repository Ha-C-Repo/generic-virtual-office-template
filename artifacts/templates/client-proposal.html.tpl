<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{project_name}} - Bid Proposal</title>
<style>
  @page { size: Letter; margin: 0.75in; }
  body { font-family: "Calibri", "Segoe UI", Arial, sans-serif; color:#111; font-size:11pt; line-height:1.45; }
  h1 { font-size:20pt; margin:0 0 4pt; }
  h2 { font-size:13pt; margin:18pt 0 6pt; border-bottom:1pt solid #999; padding-bottom:3pt; }
  h3 { font-size:11pt; margin:10pt 0 4pt; }
  .cover { text-align:left; }
  .meta { color:#444; font-size:10pt; }
  table { width:100%; border-collapse:collapse; margin:6pt 0; }
  th, td { border:0.5pt solid #999; padding:5pt 8pt; text-align:left; font-size:10.5pt; vertical-align:top; }
  th { background:#eee; }
  ul { margin:4pt 0 8pt 18pt; padding:0; }
  li { margin:2pt 0; }
  .footer { color:#666; font-size:9pt; margin-top:18pt; border-top:0.5pt solid #999; padding-top:6pt; }
  .price-summary td.amt { text-align:right; font-weight:600; }
</style>
</head>
<body>

<div class="cover">
  <h1>Bid Proposal</h1>
  <div class="meta">
    Project: {{project_name}}<br>
    Location: {{project_location}}<br>
    Submitted to: {{client_name}}<br>
    Date: {{submission_date}}<br>
    Proposal No.: {{proposal_number}}<br><br>
    Your Company, LLC<br>
    [COMPANY ADDRESS]<br>
    Office [COMPANY PHONE]<br>
    ISNetworld ID [ISN ID]
  </div>
</div>

<h2>1. Scope Summary</h2>
<p>{{scope_summary}}</p>

<h2>2. Inclusions</h2>
<ul>
  {{#inclusions}}
  <li>{{text}}</li>
  {{/inclusions}}
  <li>Engineering and detailing folded into fabrication and erection rates.</li>
  <li>Deck supply and installation.</li>
</ul>

<h2>3. Exclusions</h2>
<ul>
  {{#exclusions}}
  <li>{{text}}</li>
  {{/exclusions}}
</ul>

<h2>4. Price Summary</h2>
<table class="price-summary">
  <thead>
    <tr><th>Phase</th><th>Description</th><th style="text-align:right;">Amount</th></tr>
  </thead>
  <tbody>
    {{#price_phases}}
    <tr>
      <td>{{phase}}</td>
      <td>{{description}}</td>
      <td class="amt">${{amount}}</td>
    </tr>
    {{/price_phases}}
    <tr>
      <td colspan="2" style="text-align:right; font-weight:600;">Total Lump Sum</td>
      <td class="amt">${{total}}</td>
    </tr>
  </tbody>
</table>

<h2>5. Schedule</h2>
<p>{{schedule_summary}}</p>
<p>Total duration: {{total_duration_weeks}} weeks from notice to proceed.</p>

<h2>6. Qualifications</h2>
<ul>
  {{#qualifications}}
  <li>{{text}}</li>
  {{/qualifications}}
</ul>

<h2>7. Payment Terms</h2>
<p>{{payment_terms}}</p>

<h2>8. Validity</h2>
<p>This proposal is valid for 30 days from the submission date above.</p>

<div class="footer">
  Your Company, LLC. Established 2017. Houston, TX.<br>
  Contact: The Owner, CEO. owner@yourcompany.example.com.
</div>

</body>
</html>
