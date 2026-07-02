<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Requirement Register - {{bid_name}}</title>
<style>
  body { margin:0; background:#0f1115; color:#e6e8ec; font-family:-apple-system,"Segoe UI",Roboto,sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid #2a2f3a; display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; }
  .filter { display:flex; gap:6px; flex-wrap:wrap; }
  .chip { padding:4px 10px; border:1px solid #2a2f3a; border-radius:14px; font-size:12px; cursor:pointer; background:#161a22; }
  .chip.on { background:#5aa9ff; color:#0f1115; border-color:#5aa9ff; }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:8px 12px; border-bottom:1px solid #2a2f3a; text-align:left; font-size:13px; vertical-align:top; }
  th { background:#161a22; color:#8a93a3; text-transform:uppercase; font-size:11px; letter-spacing:1px; position:sticky; top:0; }
  td.req { font-family:"SF Mono",Consolas,monospace; color:#8a93a3; white-space:nowrap; }
  td.cat { font-weight:600; }
  td.cat.Direct { color:#6ed3a8; }
  td.cat.Subcontractor { color:#5aa9ff; }
  td.cat.ContingencyPrelim { color:#ffd166; }
  td.cat.Excluded { color:#ff9f43; }
  td.text { max-width:520px; }
  td.src { color:#8a93a3; font-size:12px; white-space:nowrap; }
  td.status { font-size:11px; padding:2px 8px; border-radius:4px; display:inline-block; }
  .gap { background:#5a1f24; color:#ff4d4f; }
  .matched { background:#1f4f3a; color:#6ed3a8; }
  .orphan { background:#5a3d1a; color:#ff9f43; }
</style>
</head>
<body>

<header>
  <h1>Requirement Register - {{bid_name}}</h1>
  <div class="filter">
    <span class="chip on" data-bucket="All">All ({{total}})</span>
    <span class="chip" data-bucket="Direct">Direct ({{direct_count}})</span>
    <span class="chip" data-bucket="Subcontractor">Subcontractor ({{sub_count}})</span>
    <span class="chip" data-bucket="ContingencyPrelim">Prelim ({{prelim_count}})</span>
    <span class="chip" data-bucket="Excluded">Excluded ({{excl_count}})</span>
  </div>
</header>

<table>
  <thead>
    <tr>
      <th>REQ ID</th>
      <th>Bucket</th>
      <th>Discipline</th>
      <th>Requirement</th>
      <th>Source</th>
      <th>Qty</th>
      <th>Unit</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    {{#rows}}
    <tr data-bucket="{{category}}">
      <td class="req">{{req_id}}</td>
      <td class="cat {{category}}">{{category}}</td>
      <td>{{discipline}}</td>
      <td class="text">{{requirement_text}}</td>
      <td class="src">{{source_doc}} p{{source_page}}</td>
      <td>{{expected_qty}}</td>
      <td>{{expected_unit}}</td>
      <td><span class="status {{status_class}}">{{status}}</span></td>
    </tr>
    {{/rows}}
  </tbody>
</table>

<script>
  document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
    c.classList.add('on');
    const b = c.dataset.bucket;
    document.querySelectorAll('tbody tr').forEach(r => {
      r.style.display = (b === 'All' || r.dataset.bucket === b) ? '' : 'none';
    });
  }));
</script>

</body>
</html>
