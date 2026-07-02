// ── BRIDGE ──────────────────────────────────────────────────────
function api(){return window.pywebview&&window.pywebview.api;}
function waitApi(){return new Promise(r=>{if(api())return r();const t=setInterval(()=>{if(api()){clearInterval(t);r();}},50);});}

// ── STATE ────────────────────────────────────────────────────────
let voice='owner', history=[], pendingFiles=[], lc=false, rc=false;
let chatScrollPos=0;
let activeProject=null;

// ── PROJECT CONTEXT BANK ─────────────────────────────────────────
// Accumulates data from multiple file drops into a single project context.
// Each drop ADDS to the bank. "generate bid" / "build it" uses everything.
// New structural PDF with different project name = fresh bank.
const projectBank = {
  files: [],           // [{name, type, result, timestamp}]
  members: [],         // accumulated AISC-verified members
  tonnage: 0,          // running total
  bidNumber: null,
  projectName: null,
  gcCompany: null,
  draftEstimate: null,
  stlPaths: [],        // accumulated 3D models
  lastAction: null,    // 'takeoff'|'bid'|'estimate' - for "continue" routing
  pdfPath: null,       // last structural PDF path for re-processing

  add(result, fileName) {
    this.files.push({name: fileName, result, timestamp: Date.now()});
    if (result.members && result.members.length) {
      // Merge members (avoid duplicates by mark)
      const existingMarks = new Set(this.members.map(m => m.mark));
      for (const m of result.members) {
        if (!existingMarks.has(m.mark)) {
          this.members.push(m);
          existingMarks.add(m.mark);
        }
      }
    }
    if (result.total_tonnage) this.tonnage = this.members.reduce((s,m) => s + (m.weight_tons||0), 0) || result.total_tonnage;
    if (result.bid_number) this.bidNumber = result.bid_number;
    if (result.project_name) this.projectName = result.project_name;
    if (result.draft_estimate) this.draftEstimate = result.draft_estimate;
    if (result.stl_paths) this.stlPaths = this.stlPaths.concat(result.stl_paths);
    if (result.pdf_path) this.pdfPath = result.pdf_path;
    this.lastAction = 'takeoff';
    this.updateStatusBar();
  },

  clear() {
    this.files = []; this.members = []; this.tonnage = 0;
    this.bidNumber = null; this.projectName = null; this.gcCompany = null;
    this.draftEstimate = null; this.stlPaths = []; this.lastAction = null;
    this.pdfPath = null;
    this.updateStatusBar();
  },

  hasContext() { return this.files.length > 0 || this.members.length > 0; },

  summary() {
    const parts = [];
    if (this.projectName) parts.push('"' + this.projectName + '"');
    if (this.bidNumber) parts.push(this.bidNumber);
    parts.push(this.members.length + ' members');
    parts.push(this.tonnage.toFixed(2) + ' tons');
    parts.push(this.files.length + ' file' + (this.files.length !== 1 ? 's' : ''));
    return parts.join(' / ');
  },

  contextForAI() {
    if (!this.hasContext()) return '';
    return ' [CONTEXT BANK: ' + this.summary()
      + '. Members: ' + this.members.slice(0,10).map(m => m.shape + ' x' + m.qty).join(', ')
      + (this.members.length > 10 ? ' (+' + (this.members.length-10) + ' more)' : '')
      + '. Estimate: ' + (this.draftEstimate ? '$' + (this.draftEstimate.total||0).toLocaleString() : 'pending')
      + ']';
  },

  updateStatusBar() {
    const el = document.getElementById('ctx-bank-bar');
    if (!el) return;
    if (!this.hasContext()) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    document.getElementById('ctx-files').textContent = this.files.length;
    document.getElementById('ctx-members').textContent = this.members.length;
    document.getElementById('ctx-tons').textContent = this.tonnage.toFixed(1);
    const nameEl = document.getElementById('ctx-name');
    if (nameEl) nameEl.textContent = this.projectName || 'Unnamed project';
  }
};

// Queue for batch PDF processing (prevents race conditions on rapid drops)
let _pdfQueue = [];
let _pdfQueueTimer = null;
const PDF_BATCH_DELAY = 3000; // 3s window to collect rapid drops

function queuePdfForExtraction(file) {
  _pdfQueue.push(file);
  clearTimeout(_pdfQueueTimer);
  _pdfQueueTimer = setTimeout(() => processPdfQueue(), PDF_BATCH_DELAY);
}

async function processPdfQueue() {
  const batch = [..._pdfQueue];
  _pdfQueue = [];
  if (!batch.length) return;

  const a = api();
  if (!a || !a.save_temp_file) return;

  for (const file of batch) {
    try {
      const saved = await a.save_temp_file(file.name, file.data);
      if (!saved.ok) continue;

      appendMsg('ai', '**Processing** `' + file.name + '`  -  extracting members (no LLM math)...', null, 'LOCAL/auto-pipeline');

      // Honor the one-shot force-new flag set by chat command `force new bid`
      const forceNew = !!window._forceNextDropAsNewBid;
      if (forceNew) {
        window._forceNextDropAsNewBid = false;  // consume it
        appendMsg('ai', '_force-new flag consumed: this drop will create a brand-new bid, not update an existing one._', null, 'LOCAL/force-new');
      }
      // v3.2.7: launch in background so UI stays responsive during long vision calls
      const startR = await a.start_auto_process_drawing(saved.data.path, '', '', true, forceNew);
      if (!startR || !(startR.ok||startR.success)) { 
        appendMsg('ai','Failed to start PDF processing: '+(startR&&startR.error||'unknown'),'error');
        continue;
      }
      const jobId = startR.data.job_id;
      // Poll with progress updates - 500ms intervals, max 5 minutes
      let r = null;
      let pollMs = 500;
      /* PROD-02: raised 5min -> 10min for large structural PDFs */
      for (let attempt = 0; attempt < 1200; attempt++) {
        if (attempt === 240) pollMs = 1000; // back-off to 1s after 2min
        await new Promise(res => setTimeout(res, pollMs));
        const poll = await a.poll_auto_process_drawing(jobId);
        if (!poll || !(poll.ok||poll.success)) break;
        const pd = poll.data;
        if (pd.status === 'done') { r = pd.result; break; }
        if (pd.status === 'error') {
          appendMsg('ai','PDF processing failed: '+(pd.error||'unknown'),'error');
          break;
        }
        // Update loading message every 4s with progress
        if (attempt % 8 === 0 && attempt > 0) {
          const lm = document.querySelector('.loading-msg .thinking-label');
          if (lm) lm.textContent = pd.progress + ' (' + pd.elapsed_s + 's elapsed)...';
        }
      }
      if (!r) { 
        appendMsg('ai','PDF processing timed out - large PDFs (80MB+) need up to 10 min. Retry or use a smaller drawing set.','error');
        continue;
      }
      if (r.ok && r.data) {
        const d = r.data;
        projectBank.add(d, file.name);

        // Keep legacy globals in sync
        window._lastPipelineResult = d;
        window._lastProjectName = d.project_name || file.name.replace(/\.[^.]+$/, '');
        if (d.pdf_path) window._lastPdfPath = d.pdf_path;
        if (d.members) window._lastTakeoffMembers = typeof teklaMembersFromVerified === 'function' ? teklaMembersFromVerified(d.members) : d.members;
        activeProject = d.project_name || file.name;

        // Show result
        const lines = [];
        lines.push('**' + file.name + '** processed. `' + (d.bid_number||'') + '`');
        lines.push(d.member_count + ' members / ' + d.total_tonnage + ' tons (AISC verified)');
        if (d.draft_estimate) {
          lines.push('Rough estimate: **$' + (d.draft_estimate.total||0).toLocaleString() + '**');
        }
        // P1 ROADMAP: inline inventory thumbnail of all unique extracted shapes
        if (d.inventory_thumbnail_path) {
          const pathUri = 'file://' + d.inventory_thumbnail_path.replace(/\\/g, '/');
          lines.push('');
          lines.push('![member inventory](' + pathUri + ')');
        }
        if (projectBank.files.length > 1) {
          lines.push('');
          lines.push('**Running total:** ' + projectBank.summary());
        }
        lines.push('');
        lines.push('_Drop more files or type **generate bid** / **3d model** / **continue**_');
        appendMsg('ai', lines.join('\n'), null, 'LOCAL/auto-pipeline');

        // Load 3D if available
        if (d.stl_paths && d.stl_paths.length && typeof loadMultiStlBase64 === 'function') {
          window._projStlPaths = projectBank.stlPaths;
        }
      } else {
        // Extraction found nothing - still useful context (bid invite, spec, etc.)
        projectBank.files.push({name: file.name, result: {}, timestamp: Date.now()});
        projectBank.updateStatusBar();
        appendMsg('ai', '**' + file.name + '** loaded. No structural members detected. File available as context for bid generation.', null, 'LOCAL/auto-pipeline');
      }
    } catch(e) {
      console.warn('PDF queue error for', file.name, e);
    }
  }
  // v6.1.3: if user typed "generate bid" while queue was processing, trigger now
  if(window._generateBidAfterQueue && projectBank.hasContext()){
    window._generateBidAfterQueue = false;
    appendMsg('ai', 'All files processed. Generating bid now...', null, 'LOCAL/auto-pipeline');
    setTimeout(()=>cmd('generate bid'), 500);
  }
  // Show action buttons after final file
  if(projectBank.hasContext()){
    const lastMsg = document.querySelector('#messages .msg.ai:last-child');
    if(lastMsg && !lastMsg.querySelector('.artifact-actions')){
      const actDiv = document.createElement('div');
      actDiv.className = 'artifact-actions';
      const bn = projectBank.bidNumber||'new';
      const pn = projectBank.projectName||'project';
      const tons = projectBank.tonnage||0;
      const est = projectBank.draftEstimate ? projectBank.draftEstimate.total : 0;
      actDiv.innerHTML =
        '<button onclick="cmd(\'generate bid\')"> GENERATE PROPOSAL</button>'
        + '<button onclick="cmd(\'Generate bid AS-IS with available data only. No questions. Both PDFs.\')"> GENERATE AS-IS</button>'
        + (projectBank.stlPaths.length ? '<button onclick="setMode(\'model\')"> VIEW 3D MODEL</button>' : '');
      lastMsg.appendChild(actDiv);
    }
  }
}


// ══ PROFESSIONAL SVG ICON SYSTEM ═══════════════════════════════
// Replaces all emoji icons with crisp, scalable SVG icons
// Structural steel / industrial design language
const ICONS = {
  // Navigation
  status:    '<svg viewBox="0 0 24 24"><rect x="3" y="13" width="4" height="8" rx="1"/><rect x="10" y="9" width="4" height="12" rx="1"/><rect x="17" y="4" width="4" height="17" rx="1"/></svg>',
  chat:      '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 01-9 9 9 9 0 01-5.6-2L3 20l1.3-3.7A9 9 0 013 12a9 9 0 019-9 9 9 0 019 9z"/></svg>',
  field:     '<svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
  model:     '<svg viewBox="0 0 24 24"><path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 22V12"/><path d="M21 7l-9 5-9-5"/></svg>',
  settings:  '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.32 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',

  // Actions
  newbid:    '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
  takeoff:   '<svg viewBox="0 0 24 24"><path d="M2 20h20"/><path d="M5 20v-8l4-4 3 3 4-4 3 3v10"/><circle cx="9" cy="8" r="1"/></svg>',
  compliance:'<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
  cube3d:    '<svg viewBox="0 0 24 24"><path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 22V12"/><path d="M21 7l-9 5-9-5"/></svg>',
  dxf:       '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><line x1="12" y1="3" x2="12" y2="21"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"/><line x1="18.4" y1="5.6" x2="5.6" y2="18.4"/></svg>',
  montecarlo:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="8" height="8" rx="1.5"/><circle cx="5.5" cy="5.5" r=".8" fill="currentColor" stroke="none"/><circle cx="8.5" cy="8.5" r=".8" fill="currentColor" stroke="none"/><circle cx="7" cy="7" r=".8" fill="currentColor" stroke="none"/><rect x="13" y="13" width="8" height="8" rx="1.5"/><circle cx="15" cy="15" r=".8" fill="currentColor" stroke="none"/><circle cx="19" cy="19" r=".8" fill="currentColor" stroke="none"/><circle cx="17" cy="17" r=".8" fill="currentColor" stroke="none"/><circle cx="15" cy="19" r=".8" fill="currentColor" stroke="none"/><circle cx="19" cy="15" r=".8" fill="currentColor" stroke="none"/></svg>',

  // Tools
  search:    '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  email:     '<svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 6 12 13 2 6"/></svg>',
  briefing:  '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>',
  research:  '<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  weight:    '<svg viewBox="0 0 24 24"><path d="M6 18L2 22"/><path d="M18 18l4 4"/><rect x="2" y="6" width="20" height="12" rx="2"/><line x1="6" y1="10" x2="6" y2="14"/><line x1="18" y1="10" x2="18" y2="14"/><line x1="10" y1="10" x2="14" y2="10"/><line x1="10" y1="14" x2="14" y2="14"/></svg>',
  wrench:    '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>',
  phone:     '<svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>',
  schedule:  '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="10 14 12 16 16 12"/></svg>',
  factory:   '<svg viewBox="0 0 24 24"><path d="M2 20h20"/><path d="M5 20V8l5 4V8l5 4V4h4a1 1 0 011 1v15"/></svg>',
  chart:     '<svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  doc:       '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>',
  copy:      '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>',
  check:     '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>',
  alert:     '<svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  print:     '<svg viewBox="0 0 24 24"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>',
};

function icon(name, cls) {
  const svg = ICONS[name] || ICONS.doc;
  return '<span class="ic ' + (cls || '') + '">' + svg + '</span>';
}

// ── VIEW MODE ────────────────────────────────────────────────────
function setMode(m){
  // Save chat scroll position before switching away
  if(document.getElementById('shell').dataset.mode==='chat'){
    const msgs=document.getElementById('messages');
    if(msgs) chatScrollPos=msgs.scrollTop;
  }
  document.getElementById('shell').dataset.mode=m;
  ['status','chat','field','model','controls','settings'].forEach(x=>{
    const b=document.getElementById('btn-'+x);if(b)b.classList.toggle('on',x===m);
  });
  if(m==='chat'){
    setTimeout(()=>{
      const i=document.getElementById('chat-input');if(i)i.focus();
      // Restore chat scroll position
      const msgs=document.getElementById('messages');
      if(msgs && chatScrollPos) msgs.scrollTop=Math.min(chatScrollPos, msgs.scrollHeight-msgs.clientHeight);
    },100);
  }
  if(m==='model'){
    setTimeout(()=>{ if(typeof refreshBidList==='function')refreshBidList(); },200);
  }
  if(m==='field'){
    // P8.7: re-fetch KPIs when switching to FIELD so header strip is never stale
    setTimeout(()=>{ if(typeof populateKPIs==='function')populateKPIs(); },200);
  }
  if(m==='controls'){
    setTimeout(()=>{ if(typeof refreshControls==='function')refreshControls(); },200);
  }
}

// ── CHAT CONTEXT BAR ─────────────────────────────────────────────
function setChatContext(project, detail){
  activeProject=project;
  const bar=document.getElementById('chat-ctx');
  const projEl=document.getElementById('ctx-proj');
  const detEl=document.getElementById('ctx-detail');
  if(!bar)return;
  if(project){
    const icon=/bid|rfq|rfp|proposal/i.test(project)?'\uD83D\uDCC4 ':/takeoff|estimate/i.test(project)?'\uD83D\uDCCF ':/settings|config/i.test(project)?'\u2699\uFE0F ':'\uD83D\uDCC1 ';
    projEl.textContent=icon+project;
    detEl.textContent=detail||'';
    bar.classList.add('on');
  } else {
    bar.classList.remove('on');
  }
}

// ── FILE CLASSIFICATION ──────────────────────────────────────────
function showFileClassification(type, label){
  // Types: bid-invite, scope-creep, change-order, info-only
  const div=document.createElement('div');
  div.className='file-class '+type;
  div.textContent='DETECTED: '+label;
  return div;
}

// ── BID CARD EXPAND ──────────────────────────────────────────────
function toggleBidCard(el){
  el.closest('.bcard').classList.toggle('expanded');
}

// ── SYSTEM HEALTH CHECK ──────────────────────────────────────────
let lastMemMB=0;
async function updateHealthCard(){
  const a=api();if(!a)return;
  const card=document.getElementById('health-card');
  const icon=document.getElementById('health-icon');
  const title=document.getElementById('health-title');
  const sub=document.getElementById('health-sub');
  if(!card)return;
  try{
    const [healthR, keysR] = await Promise.all([a.get_health(), a.check_api_keys().catch(()=>null)]);
    const keysOk = keysR && keysR.ok && keysR.data && keysR.data.any_ai;
    if(healthR&&healthR.ok&&healthR.data&&healthR.data.status==='healthy'){
      const mem=parseFloat(healthR.data.memory_mb)||0;
      const trend=lastMemMB>0?(mem>lastMemMB+5?'\u2191':mem<lastMemMB-5?'\u2193':'\u2192'):'';
      const memColor=mem>500?'var(--red)':mem>300?'var(--amber)':'var(--green)';
      lastMemMB=mem;
      // P8.4: reflect real handler health, not just "bridge instantiates"
      const errCount = healthR.data.handler_errors_60s || 0;
      const healthColor = healthR.data.health_color || (errCount === 0 ? 'green' : errCount < 3 ? 'yellow' : 'red');
      const healthLabel = healthR.data.health_label || 'ALL SYSTEMS OPERATIONAL';
      if(!keysOk){
        card.classList.add('fail');
        icon.textContent='\u26a0\ufe0f';
        title.textContent='NO API KEYS';
        title.className='health-title fail';
      } else if(healthColor === 'green'){
        card.classList.remove('fail');
        icon.textContent='\u2705';
        title.textContent=healthLabel;
        title.className='health-title ok';
      } else if(healthColor === 'yellow'){
        card.classList.remove('fail');
        icon.textContent='\u26a0\ufe0f';
        title.textContent=healthLabel;
        title.className='health-title warn';
      } else {
        card.classList.add('fail');
        icon.textContent='\u274c';
        title.textContent=healthLabel;
        title.className='health-title fail';
      }
      const up=healthR.data.uptime_human||'';
      const now=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
      const keyNote=keysOk?'':' \xb7 add keys in API KEYS';
      sub.innerHTML='Bridge healthy'+(up?' \xb7 uptime '+up:'')+(mem?' \xb7 <span style="color:'+memColor+'">'+mem+'MB '+trend+'</span>':'')+keyNote+' \xb7 checked '+now;
    } else {
      card.classList.add('fail');
      icon.textContent='\u274c';
      title.textContent='SYSTEM ERROR';
      title.className='health-title fail';
      sub.textContent=healthR&&healthR.error?healthR.error:'Bridge returned unhealthy status';
    }
  }catch(e){
    card.classList.add('fail');
    icon.textContent='\u26a0\ufe0f';
    title.textContent='BRIDGE OFFLINE';
    title.className='health-title fail';
    sub.textContent='Cannot reach virtual office backend';
  }
}

async function checkApiKeyStatus(){
  const a=api();if(!a){setTimeout(checkApiKeyStatus,2000);return;}
  try{
    const r=await a.check_api_keys();
    if(!r||!r.ok)return;
    const d=r.data;
    const pill=document.getElementById('active-model');
    if(!pill)return;
    if(d.claude){
      pill.textContent='CLAUDE \u00b7 READY';
      pill.style.color='';
    } else if(d.any_ai){
      pill.textContent=(d.openai?'OPENAI':d.gemini?'GEMINI':'AI')+' \u00b7 READY';
      pill.style.color='var(--amber)';
    } else {
      pill.textContent='NO API KEYS';
      pill.style.color='var(--red)';
    }
  }catch(e){}
}

// ── SIDEBAR COLLAPSE ─────────────────────────────────────────────
function toggleL(){
  lc=!lc;
  document.getElementById('mgrid').classList.toggle('lc',lc);
  document.getElementById('ltog').textContent=lc?'▶':'◀';
}
function toggleR(){return; // right sidebar removed
  rc=!rc;
  document.getElementById('mgrid').classList.toggle('rc',rc);
  document.getElementById('rtog').textContent=rc?'◀':'▶';
}

// ── CLOCK ────────────────────────────────────────────────────────
function startClock(){
  function tick(){
    const c=new Date(new Date().toLocaleString('en-US',{timeZone:'America/Chicago'}));
    const pad=n=>String(n).padStart(2,'0');
    const el=document.getElementById('live-clock');
    if(el)el.textContent=pad(c.getHours())+':'+pad(c.getMinutes())+':'+pad(c.getSeconds())+' CST';
  }
  tick();setInterval(tick,1000);
}

// ── KPI COUNTERS ─────────────────────────────────────────────────
function anim(el,t,pre,suf,dec){
  if(!el)return;
  const s=performance.now(),d=1200;
  (function f(n){
    const p=Math.min((n-s)/d,1),e=1-Math.pow(1-p,3),v=t*e;
    el.textContent=(pre||'')+(dec?v.toFixed(dec):Math.floor(v))+(suf||'');
    if(p<1)requestAnimationFrame(f);else el.textContent=(pre||'')+t+(suf||'');
  })(s);
}
async function populateKPIs(){
  // v3.2.7: pull real data from Bridge.get_kpis(). Falls back to dashes on
  // failure so we never display lies.
  const a = api();
  if(!a){
    ['k-tons','k-rev','k-blk','k-jobs'].forEach(id=>{
      const el=document.getElementById(id); if(el) el.textContent='-';
    });
    return;
  }
  try {
    const r = await a.get_kpis();
    if(r && (r.ok||r.success) && r.data){
      const d = r.data;
      const tonsVal = d.active_tons || d.tons_active || 0;
      anim(document.getElementById('k-tons'), tonsVal, '', d.tons_growing?'+':'');
      const ktTons = document.getElementById('kt-tons');
      if(ktTons){ if(tonsVal === 0){ ktTons.textContent = '–'; ktTons.className = 'ktrend'; } }
      const rev = d.pipeline_value_m || (d.open_bids_value ? d.open_bids_value/1e6 : 0);
      anim(document.getElementById('k-rev'), rev, '$', 'M', rev>=1?1:2);
      const ktRev = document.getElementById('kt-rev');
      if(ktRev){ if(rev === 0){ ktRev.textContent = '–'; ktRev.className = 'ktrend'; } }
      anim(document.getElementById('k-blk'), d.blockers||0, '', '');
      anim(document.getElementById('k-jobs'), d.active_projects||d.active_jobs||0, '', '');
      // v3.2.7 pass 9a: update field-mode KPI strip (was hardcoded $5.9M)
      const fkPipe = document.getElementById('fk-pipe');
      if(fkPipe){
        const activeProj=d.active_projects||d.active_jobs||0;
        fkPipe.textContent = rev>=1?'$'+rev.toFixed(1)+'M pipeline':rev>0?'$'+(rev*1000).toFixed(0)+'K pipeline':activeProj>0?activeProj+' active project'+(activeProj!==1?'s':''):'No active pipeline';
      }
      const fkBlk = document.getElementById('fk-blk');
      if(fkBlk) fkBlk.textContent = (d.blockers||0) + ' blocker' + ((d.blockers||0)===1?'':'s');
      const fkJobs = document.getElementById('fk-jobs');
      if(fkJobs) fkJobs.textContent = (d.active_projects||d.active_jobs||0) + ' active';
    } else {
      ['k-tons','k-rev','k-blk','k-jobs'].forEach(id=>{
        const el=document.getElementById(id); if(el) el.textContent='-';
      });
    }
  } catch(e) {
    console.warn('KPI fetch failed:', e);
    ['k-tons','k-rev','k-blk','k-jobs'].forEach(id=>{
      const el=document.getElementById(id); if(el) el.textContent='-';
    });
  }
}

// ── VOICE MODE BADGE ─────────────────────────────────────────────
function cycleVoice(){
  // v3.2: voice split removed. ONE professional voice for all output.
  // Function kept as no-op for any legacy onClick handlers.
}

// ── FILE HANDLING ────────────────────────────────────────────────
const FT={'image/png':'image','image/jpeg':'image','image/gif':'image','image/webp':'image',
  'application/pdf':'pdf','text/plain':'text','text/csv':'text','application/json':'text','text/markdown':'text'};
function fcat(t,n){if(FT[t])return FT[t];const e=(n||'').split('.').pop().toLowerCase();if(['png','jpg','jpeg','gif','webp'].includes(e))return'image';if(e==='pdf')return'pdf';if(['txt','md','csv','json','xml','log','py','js','html','css','yaml','bat'].includes(e))return'text';return'other';}
function fmt(b){if(b<1024)return b+'B';if(b<1048576)return(b/1024).toFixed(1)+'KB';return(b/1048576).toFixed(1)+'MB';}
function readAs(file,m){return new Promise((r,j)=>{const x=new FileReader();x.onload=()=>r(x.result);x.onerror=()=>j(x.error);m==='text'?x.readAsText(file):x.readAsDataURL(file);});}
// ── FILE PROCESSOR - AUTO-ROUTE ON DROP ──────────────────────────
// Collects ALL files first (batch-safe debounce), then auto-triggers
// the project pipeline when structural files are detected.
async function processFiles(fl){
  const promises = [];
  for(const f of fl){
    // Structural PDFs (ICD, Topgolf, etc.) routinely exceed 20MB.
    // Raised to 200MB to match real job drawing sets.
    // The auto-pipeline drag-drop path has no JS size check - this
    // cap only applies to the chat attachment button.
    if(f.size>200*1024*1024){showToast('File too large (max 200MB): '+f.name,'warn',4000);continue;}
    const c=fcat(f.type,f.name);
    promises.push((async()=>{
      let d='',txt='';
      if(c==='text'){d=await readAs(f,'text');txt=d;}
      else{const u=await readAs(f,'url');d=u.split(',')[1];}
      return {name:f.name,type:f.type,size:f.size,cat:c,data:d,text:txt};
    })());
  }
  // Wait for ALL files to finish reading before adding to pending
  const loaded = await Promise.all(promises);
  for(const lf of loaded) pendingFiles.push(lf);
  renderChips();

  // ── AUTO-CLASSIFY: inspect filename/content for classification badges ──
  for(const lf of loaded){
    const nm=(lf.name||'').toLowerCase();
    const tx=(lf.text||'').toLowerCase().slice(0,2000);
    let cType=null, cLabel=null;
    if(/rfq|request.for.quote|invitation.to.bid|itb|bid.invite|rfp/i.test(nm+' '+tx)){
      cType='bid-invite'; cLabel='BID INVITE';
    } else if(/scope.creep|additional.work|extra.work|beyond.scope|not.in.contract|out.of.scope/i.test(nm+' '+tx)){
      cType='scope-creep'; cLabel='SCOPE CREEP';
    } else if(/change.order|co[#\- ]\d|co\d{2,}|modification|amendment|revised.scope|pco|ccd/i.test(nm+' '+tx)){
      cType='change-order'; cLabel='CHANGE ORDER';
    } else if(/rfi|request.for.information|clarification|question/i.test(nm+' '+tx)){
      cType='info-only'; cLabel='RFI';
    } else if(/submittal|shop.drawing|material.approval|product.data/i.test(nm+' '+tx)){
      cType='change-order'; cLabel='SUBMITTAL';
    } else if(/safety|prequal|isnetworld|avetta|osha|emr|insurance|w9/i.test(nm+' '+tx)){
      cType='bid-invite'; cLabel='SAFETY/PREQUAL';
    } else if(/fyi|info|update|newsletter|notice|reminder|schedule/i.test(nm)){
      cType='info-only'; cLabel='INFORMATION';
    }
    if(cType){
      const badge=showFileClassification(cType, cLabel);
      const msgs=document.getElementById('messages');
      if(msgs){
        const wrapper=document.createElement('div');
        wrapper.style.cssText='display:flex;justify-content:center;padding:4px 0';
        wrapper.appendChild(badge);
        msgs.appendChild(wrapper);
        msgs.scrollTop=msgs.scrollHeight;
      }
    }
  }

  // ── AUTO-PIPELINE: structural drawing PDFs trigger 3D extraction first ──
  // Honors the Hard Rule (no LLM math): we extract members locally and
  // populate verified tonnage from the AISC database BEFORE any AI is
  // asked to price the bid. The user gets a clear "VIEW 3D MODEL" button
  // and the artifacts auto-route to Documents/Your Company Bids/.
  for(const lf of loaded){
    if(lf.cat === 'pdf'){
      // v6.1.3 fix: use the batch queue (sequential processing) instead of
      // concurrent maybeAutoProcessDrawing calls. Dropping 3 PDFs at once
      // crashed the pywebview bridge because it can't handle 3 simultaneous
      // Python bridge calls. The queue processes them one at a time.
      lf._autoProcessed = true;
      queuePdfForExtraction(lf);
    }
  }

  // Show chip count when multiple files loaded
  if(loaded.length > 1){
    showToast(`${loaded.length} files loaded. Ready to process.`,'success',2000);
  }

  // ── AUTO-TRIGGER: structural/project files with no typed text ──
  // Use longer debounce (2s) to allow dropping multiple files in rapid succession
  // Skip files already handled by maybeAutoProcessDrawing (Bug 1 fix)
  const unprocessed = pendingFiles.filter(f => !f._autoProcessed);
  const hasProjectFile = unprocessed.some(f=>
    f.cat==='pdf' || f.cat==='image' ||
    (f.text && /W\d+[xX]\d+|HSS|rfq|request for|bid|drawing|structural/i.test(f.text))
  );
  if(hasProjectFile && unprocessed.length>0){
    clearTimeout(window._autoTrigger);
    window._autoTrigger = setTimeout(()=>{
      // Only auto-trigger if user hasn't typed anything
      if(pendingFiles.length>0 && !document.getElementById('chat-input').value.trim()){
        runProjectPipeline();
      }
    }, 2000); // 2s gives time for batch drops
  }
}

// ── PROJECT PIPELINE - MAIN AUTO-ROUTER ──────────────────────────
async function runProjectPipeline(){
  const a=api();
  if(!a){appendMsg('ai','Bridge not connected.','error');return;}
  // Filter out files already processed by maybeAutoProcessDrawing
  const files=pendingFiles.filter(f => !f._autoProcessed);
  if(!files.length)return;
  pendingFiles=[];renderChips();

  // Show user message with file names and count
  const fileLabel = files.length > 1
    ? `${files.length} files: ${files.map(f=>f.name).join(', ')}`
    : `${files[0].name}`;
  appendMsg('user', fileLabel);

  // Real progress bar - polls bridge.get_pipeline_progress() every 250ms
  appendMsg('ai','','loading');
  const setLabel=t=>{const l=document.querySelector('.loading-msg .thinking-label');if(l)l.textContent=t;};
  setLabel('Starting pipeline…');

  // Inject progress bar styles + element into the loading message
  const loadEl = document.querySelector('.loading-msg');
  if (loadEl && !document.getElementById('pipeline-pb-host')) {
    const pb = document.createElement('div');
    pb.id = 'pipeline-pb-host';
    pb.style.cssText = 'margin-top:10px;background:var(--c5);border-radius:3px;height:6px;overflow:hidden;width:100%;max-width:280px;';
    pb.innerHTML = '<div id="pipeline-pb-fill" style="height:100%;width:0%;background:var(--molten);transition:width 0.3s ease;"></div>';
    loadEl.appendChild(pb);
  }

  // Poll for progress while pipeline runs
  let progPollHandle = setInterval(async () => {
    try {
      const pr = await a.get_pipeline_progress();
      if (pr.ok && pr.data) {
        const fill = document.getElementById('pipeline-pb-fill');
        if (fill) fill.style.width = pr.data.pct + '%';
        if (pr.data.detail) setLabel(pr.data.detail);
        if (!pr.data.active) clearInterval(progPollHandle);
      }
    } catch(e) { /* keep polling */ }
  }, 250);

  try{
    const payload = files.map(f=>({name:f.name,type:f.type,cat:f.cat,data:f.data||'',text:f.text||''}));
    const r = await a.auto_process_project_files(payload, activeBidTemplate);
    clearInterval(progPollHandle);
    removeLoading();

    if(!r.ok){
      // Fall back to regular AI ask
      const fp=files.map(f=>({name:f.name,type:f.type,cat:f.cat,data:f.data}));
      const ai_r=await a.ai_ask('Analyze these files. Extract any structural steel members, project details, and provide a bid summary.',voice,history.slice(-10),fp);
      if(ai_r.ok) appendMsg('ai',ai_r.data.text,null,(ai_r.data.provider||'ai').toUpperCase());
      else appendMsg('ai','Could not process files: '+(r.error||'unknown error'),'error');
      return;
    }

    const d = r.data;

    // Render the project card
    showProjectCard(d);

    // Auto-load 3D models if generated
    if(d.stl_paths && d.stl_paths.length > 0 && d.stl_paths[0].stl_b64){
      setTimeout(()=>{
        try{ loadMultiStlBase64(d.stl_paths); }
        catch(e){ console.warn('Multi-STL load error',e); }
      }, 500);
    } else if(d.stl_b64){
      setTimeout(()=>{
        try{ loadStlBase64(d.stl_b64, d.filenames ? d.filenames[0] : 'Project Model'); }
        catch(e){ console.warn('3D load error',e); }
      }, 500);
    }

    // Add to history
    const summary = d.summary || 'Project files processed';
    history.push({role:'user', content:'[Files: '+files.map(f=>f.name).join(', ')+']'});
    history.push({role:'assistant', content:summary+(d.bid_text?'\n\n[Bid document generated]':'')});

  } catch(err){
    clearInterval(progPollHandle);
    removeLoading();
    appendMsg('ai','Pipeline error: '+err.message,'error');
    console.error('runProjectPipeline error',err);
  }
}

// ── PROJECT CARD - Rich display for pipeline results ──────────────
function showProjectCard(d){
  const fileType = d.file_type||'general';
  const members  = d.members||[];
  const cost     = d.cost||{};
  const isDrawing= ['drawing','bid_with_drawings'].includes(fileType)||members.length>0;
  const isBid    = ['bid_invite','bid_with_drawings'].includes(fileType)||d.bid_text;

  let html = '<div class="proj-card">';

  // Header - shows file type + tonnage + data source transparency
  const typeLabel = isBid&&isDrawing ? icon('newbid')+' Drawing + Bid Invite' :
                    isBid            ? icon('compliance')+' Bid Invite Detected'  :
                    isDrawing        ? icon('newbid')+' Structural Drawing'    : icon('doc')+' Document';
  const filesLabel = d.filenames && d.filenames.length > 1
    ? `${d.filenames.length} files`
    : (d.filenames && d.filenames[0]) || 'file';
  const fallbacks = d.openai_fallback_count || 0;
  const sourceNote = fallbacks > 0
    ? `AISC CSV + ${fallbacks} OpenAI fallback(s)`
    : 'AISC CSV (fully offline)';
  html += `<div class="proj-hdr"><span class="proj-type">${typeLabel} · ${filesLabel}</span>`;
  if(d.total_tons>0) html += `<span class="proj-tons">${d.total_tons.toFixed(1)} tons · ${(d.total_lbs||0).toLocaleString()} lbs</span>`;
  html += `</div>`;
  html += `<div style="padding:4px 14px;font-family:monospace;font-size:9px;color:#5C7A94;border-bottom:1px solid #22303D;">`;
  html += `Math source: ${sourceNote} · Costs from bid_rates.json · Zero LLM arithmetic</div>`;

  // Member schedule table
  if(members.length>0){
    html += '<div class="proj-section">';
    html += '<div class="proj-section-title">MEMBER SCHEDULE - AISC CATALOG</div>';
    html += '<table class="proj-table"><thead><tr>';
    html += '<th>Designation</th><th>Family</th><th>Qty</th><th>Length</th><th>lb/ft</th><th>Weight</th><th>AISC</th>';
    html += '</tr></thead><tbody>';
    for(const m of members){
      const inAisc = m.in_aisc_csv;
      const badge  = inAisc ? '<span class="aisc-ok">✓</span>' : '<span class="aisc-miss">?</span>';
      html += `<tr>
        <td class="desig">${m.designation}</td>
        <td>${m.family}</td>
        <td>${m.count}</td>
        <td>${(m.length_ft||0).toFixed(0)} ft</td>
        <td>${m.lb_per_ft||'-'}</td>
        <td>${m.weight_lbs ? m.weight_lbs.toLocaleString()+' lbs' : '-'}</td>
        <td>${badge}</td>
      </tr>`;
    }
    html += '</tbody></table>';
    if(members.some(m=>!m.in_aisc_csv))
      html += '<div class="proj-note">? = shape not found in AISC CSV · verify designation</div>';
    html += '</div>';
  }

  // Cost summary
  if(cost.total>0){
    html += '<div class="proj-section">';
    html += '<div class="proj-section-title">ESTIMATED PRICING</div>';
    html += '<div class="proj-cost-grid">';
    html += `<div class="cost-row"><span>Fabrication</span><span>$${(cost.fabrication||0).toLocaleString()}</span></div>`;
    html += `<div class="cost-row"><span>Erection</span><span>$${(cost.erection||0).toLocaleString()}</span></div>`;
    html += `<div class="cost-row"><span>G&A (5.5%)</span><span>$${(cost.ga||0).toLocaleString()}</span></div>`;
    html += `<div class="cost-row total"><span>TOTAL BID</span><span>$${(cost.total||0).toLocaleString()}</span></div>`;
    if(cost.per_ton) html += `<div class="cost-note">~$${cost.per_ton.toLocaleString()}/ton all-in</div>`;
    html += '</div>';
    html += '</div>';
  }

  // 3D model trigger
  if(d.stl_paths && d.stl_paths.length > 0){
    html += '<div class="proj-section">';
    html += '<button class="proj-btn" onclick="loadMultiStlBase64(window._projStlPaths)">▶ VIEW 3D MODEL (' + d.stl_paths.length + ' shapes)</button>';
    html += '<span class="proj-note"> Click to open Three.js viewer with all members</span>';
    html += '</div>';
    window._projStlPaths = d.stl_paths;
  } else if(d.stl_b64){
    html += '<div class="proj-section">';
    html += '<button class="proj-btn" onclick="loadStlBase64(window._projStl,\'Project Model\')">▶ VIEW 3D MODEL</button>';
    html += '<span class="proj-note"> Click to open Three.js viewer with all members</span>';
    html += '</div>';
    window._projStl = d.stl_b64;
  }

  // Bid invite info
  if(d.bid_invite_info){
    const bi = d.bid_invite_info;
    html += '<div class="proj-section">';
    html += '<div class="proj-section-title">BID INVITE DETAILS</div>';
    if(bi.project_name) html += `<div class="proj-row"><b>Project:</b> ${bi.project_name}</div>`;
    if(bi.owner)        html += `<div class="proj-row"><b>Owner/GC:</b> ${bi.owner}</div>`;
    if(bi.location)     html += `<div class="proj-row"><b>Location:</b> ${bi.location}</div>`;
    if(bi.bid_due_date) html += `<div class="proj-row"><b>Due:</b> ${bi.bid_due_date}</div>`;
    html += '</div>';
  }

  // Bid document
  if(d.bid_text){
    html += '<div class="proj-section">';
    html += '<div class="proj-section-title">GENERATED BID - '+activeBidTemplate+' TEMPLATE';
    html += ' <button class="proj-copy-btn" onclick="copyBid()">COPY BID</button>';
    html += ' <button class="proj-copy-btn" onclick="exportProjectPdf()" style="margin-left:8px;">SAVE PDF</button>';
    html += '</div>';
    html += '<pre class="proj-bid-text" id="proj-bid-pre">'+escHtml(d.bid_text)+'</pre>';
    html += '</div>';
    window._projBidText = d.bid_text;
    window._projData = d;        // preserve full data for PDF export
  }

  html += '</div>'; // proj-card

  appendMsg('ai', html, null, 'PROJECT/PIPELINE', true);
}

function copyBid(){
  if(window._projBidText){
    navigator.clipboard.writeText(window._projBidText)
      .then(()=>showToast('Bid copied to clipboard','success',2500))
      .catch(()=>showToast('Copy failed. Select text manually.','warn',3000));
  }
}

async function exportProjectPdf(){
  if(!window._projData){
    showToast('No project data to export','warn',2500);
    return;
  }
  const a = api(); if(!a) return;
  showToast('Generating PDF…','info',1500);
  try {
    const r = await a.export_project_card_pdf(window._projData);
    if(r.ok){
      const fn = r.data.filename || 'proposal.pdf';
      const sz = (r.data.size_bytes/1024).toFixed(1);
      showToast(`✓ Saved ${fn} (${sz} KB)`,'success',4500);
      // Add a chat message so Owner has a record
      appendMsg('ai', `PDF saved to <code>output/${fn}</code> · ${sz} KB · Your Company branded`, null, 'EXPORT');
    } else {
      showToast('PDF export failed: '+(r.error||'unknown'),'error',4000);
    }
  } catch(e){
    showToast('PDF export error: '+e.message,'error',4000);
  }
}

function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function renderChips(){
  const b=document.getElementById('file-chips');if(!b)return;b.innerHTML='';
  pendingFiles.forEach((f,i)=>{
    const c=document.createElement('div');c.className='file-chip '+f.cat;
    c.innerHTML='<span class="fname">'+f.name+'</span><span class="fsize">'+fmt(f.size)+'</span><button class="fremove" onclick="rmFile('+i+')">&times;</button>';
    b.appendChild(c);
  });
}
function rmFile(i){pendingFiles.splice(i,1);renderChips();}
document.getElementById('file-input').addEventListener('change',function(e){if(e.target.files.length)processFiles(e.target.files);e.target.value='';});

const mb=document.getElementById('messages');const dov=document.getElementById('drop-ov');let dc=0;
mb.addEventListener('dragenter',e=>{e.preventDefault();dc++;dov.classList.add('active');});
mb.addEventListener('dragleave',e=>{e.preventDefault();dc--;if(dc<=0){dc=0;dov.classList.remove('active');}});
mb.addEventListener('dragover',e=>e.preventDefault());
mb.addEventListener('drop',e=>{e.preventDefault();dc=0;dov.classList.remove('active');if(e.dataTransfer.files.length)processFiles(e.dataTransfer.files);});

// ── SEND MESSAGE ─────────────────────────────────────────────────
async function sendMessage(override){
  if(document.getElementById('shell').dataset.mode!=='chat')setMode('chat');
  const inp=document.getElementById('chat-input');
  const text=override||inp.value.trim();
  const files=[...pendingFiles];
  if(!text&&!files.length)return;
  if(!override)inp.value='';
  inp.style.height='auto';pendingFiles=[];renderChips();
  const w=document.querySelector('.welcome');if(w)w.remove();
  let ud=text||'';if(files.length)ud=(ud?ud+'\n':'')+files.map(f=>'['+f.name+']').join(' ');
  appendMsg('user',ud);
  history.push({role:'user',content:text||'Analyze the attached file(s).'});
  const a=api();
  if(!a){appendMsg('ai','Bridge not connected. Run via pywebview.','error');return;}
  // ── LOCAL COMMAND INTERCEPTS - no AI needed ──
  // Normalize: lowercase, then strip trailing punctuation so "status!"
  // and "how are we doing?" match the same regexes as their bare forms.
  const tl=text.toLowerCase().replace(/[?!.,;\s]+$/, '');
  // Template switching
  if(tl.match(/switch.*template|use.*(simple|standard|detailed|refinery).*template|change.*template/)){
    let tplName='STANDARD';
    if(tl.includes('simple'))tplName='SIMPLE';
    else if(tl.includes('detailed'))tplName='DETAILED';
    else if(tl.includes('refinery')||tl.includes('industrial'))tplName='REFINERY';
    else if(tl.includes('standard'))tplName='STANDARD';
    else{cycleBidTemplate();appendMsg('ai','Switched bid template. Current: '+BID_TEMPLATES[activeBidTemplate].name+'\\n'+BID_TEMPLATES[activeBidTemplate].desc,null,'LOCAL/template');return;}
    activeBidTemplate=tplName;
    document.getElementById('tpl-active').textContent=BID_TEMPLATES[tplName].name.toUpperCase();
    a.set_user_pref('bid_template',tplName).catch(()=>{});
    appendMsg('ai','Bid template set to **'+BID_TEMPLATES[tplName].name+'**\\n'+BID_TEMPLATES[tplName].desc+'\\n\\nSections: '+BID_TEMPLATES[tplName].sections.join(' → '),null,'LOCAL/template');
    return;
  }
  // Tour
  if(tl.match(/start.*tour|show.*tour|guided.*tour|restart.*tour/)){startTour();return;}

  // ── LOCAL METHOD INTERCEPTS (P2 features) ─────────────────────
  // These hit Bridge methods directly. No LLM. No API call. Instant response.

  // 0. v3.2.7: 'help' / 'commands' / 'what can you do' - list working commands
  if (tl.match(/^(help|commands?|what\s+can\s+you\s+do\??|show\s+commands|\?)$/)) {
    const HELP = [
      ['help', 'list these commands'],
      ['status', 'daily status line'],
      ['morning brief', 'full morning briefing'],
      ['list bids', 'show active bids'],
      ['compliance', 'show compliance blockers + cascade hints'],
      ['steel prices', 'latest service center pricing'],
      ['3d model of W14X82 at 20ft', 'generate 3D STL locally (no AI)'],
      ['plate weight PL.5X12X12 x24', 'plate weight calculator'],
      ['lookup W14X82', 'AISC shape properties'],
      ['lien deadlines from YYYY-MM-DD', 'Texas Ch.53 lien calendar'],
      ['scan and fix', 'VJ codebase scan (catches real bugs)'],
      ['draft email to <name>', 'cold email draft'],
      ['scope creep check: <email>', 'AIA G701 change-order detection'],
      ['new bid', 'start a new bid from template'],
      ['drop a PDF', 'auto-extracts members + tonnage'],
      ['quotes', 'list vendor quotes from Outlook poller'],
      ['poll vendors', 'check Outlook now for new quotes'],
      ['whitelist', 'show locked vendor sender domains'],
      ['add vendor <domain>', 'add a new service center to the whitelist'],
      ['models', 'show AI model routing (Haiku/Sonnet/Opus 4.6/4.7)'],
      ['use opus for <task>', 'escalate a task to Opus 4.7 (max accuracy)'],
      ['escalate to opus: <prompt>', 'one-shot Opus 4.7 call'],
      ['connectors', 'list remote MCP connectors (Claude App-compatible)'],
      ['call with mcps <names>: <prompt>', 'API call with MCP servers attached'],
      ['start mcp http', 'expose Bridge to claude.ai project via HTTP MCP'],
      ['mcp http status', 'check if HTTP MCP server is running'],
      ['mcp token', 'show bearer token for claude.ai connector setup'],
      ['rotate mcp token', 'generate new token (invalidates old)'],
      ['stop mcp http', 'shut down the HTTP MCP server'],
      ['export tekla', 'export current members to Tekla XML'],
      ['export strumis', 'export current members to Strumis XML'],
      ['cascade N', 'advance compliance item N to OPEN'],
    ];
    let m = '**Available commands** (v3.2.7):\n\n';
    HELP.forEach(p => { m += '* `' + p[0] + '` - ' + p[1] + '\n'; });
    m += '\nDrop files into chat or onto the MODEL tab. Ctrl+K opens the palette.';
    appendMsg('ai', m, null, 'LOCAL/help');
    return;
  }

  // 1. Morning briefing: "morning briefing", "what's on my plate", "today", "what should I look at"
  if(tl.match(/^(morning\s+briefing|what'?s?\s+on\s+my\s+plate|what\s+should\s+i\s+(look\s+at|focus\s+on|do)|today'?s?\s+(briefing|summary|agenda)|^briefing$|good\s+morning|whats?\s+up\s+today|what\s+do\s+i\s+have\s+(today|on))/)){
    try {
      const r = await a.morning_briefing();
      if (r && r.ok) {
        const d = r.data;
        let msg = '**' + (d.date || 'Today') + '**\n\n';
        if (d.pipeline && Object.keys(d.pipeline).length) {
          msg += '**Pipeline:** ' + Object.entries(d.pipeline).map(([s,n]) => s + ': ' + n).join(', ') + '\n\n';
        } else {
          msg += '**Pipeline:** empty\n\n';
        }
        if (d.recent_bids && d.recent_bids.length) {
          msg += '**Recent bids:**\n';
          d.recent_bids.forEach(b => {
            msg += '  - [' + b.id + '] ' + (b.name || '(unnamed)') + ' - ' + (b.state || '?') + '\n';
          });
          msg += '\n';
        }
        // Stale-bid alert (Owner M2): bids in SCANNED > 7 days bubble to the top of attention
        if (d.stale_bids && d.stale_bids.length) {
          msg += '**STALE BIDS (need GO/NO-GO decision):**\n';
          d.stale_bids.forEach(b => {
            const days = (b.days_stale != null) ? (b.days_stale + 'd') : '?';
            msg += '  - [' + b.id + '] ' + (b.name || '(unnamed)') + ' - sitting ' + days + '\n';
          });
          msg += '\n';
        }
        if (d.compliance_blockers && d.compliance_blockers.length) {
          msg += '**Compliance blockers:**\n';
          d.compliance_blockers.forEach(c => {
            msg += '  - ' + c.item + (c.blocks ? ' (blocks ' + c.blocks + ')' : '') + '\n';
          });
          msg += '\n';
        }
        msg += '**Next:** ' + (d.suggested_next_action || 'Check the bids folder.');
        appendMsg('ai', msg, null, 'LOCAL/briefing');
      } else {
        appendMsg('ai', 'Morning briefing failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Morning briefing error: ' + e, 'error'); }
    return;
  }

  // 2. List active bids: "list bids", "active bids", "show pipeline", "what bids"
  //    Variants (the Owner's roadmap #1): "list bids killed" / "won" / "lost" /
  //    "terminal" / "all" filter the output.
  const listBidsMatch = tl.match(/^(?:list\s+bids|active\s+bids|show\s+(?:me\s+)?(?:the\s+)?(?:my\s+)?(?:active\s+)?(?:bids|pipeline)|what\s+bids|what'?s?\s+(?:the\s+)?pipeline|pipeline\s+status|my\s+bids|show\s+me\s+my\s+bids|any\s+(?:new\s+)?(?:rfqs?|bids?)|what\s+(?:have|do)\s+i\s+(?:have|got)(?:\s+in(?:\s+the)?(?:\s+pipeline)?)?)(?:\s+(killed|passed|won|lost|terminal|dead|all|active))?$/);
  if(listBidsMatch){
    let stateFilter = (listBidsMatch[1] || 'active').toLowerCase();
    if (stateFilter === 'dead') stateFilter = 'killed';  // alias
    try {
      const r = await a.list_active_bids(25, stateFilter);
      if (r && r.ok) {
        const bids = r.data.bids || [];
        const filterLabel = (r.data.state_filter !== 'active')
          ? ` (filter: ${r.data.state_filter})` : '';
        if (!bids.length) {
          const emptyMsg = (stateFilter === 'active')
            ? 'No active bids. Drop a PDF or use VM Discovery to scan inbox.\n_To see closed bids, try `list bids terminal`._'
            : `No bids match filter "${stateFilter}".`;
          appendMsg('ai', emptyMsg, null, 'LOCAL/bids');
        } else {
          let msg = '**' + bids.length + ' bid(s)' + filterLabel + '**\n\n';
          bids.forEach(b => {
            const ev = b.estimated_value ? '$' + Number(b.estimated_value).toLocaleString() : 'TBD';
            msg += '  [' + b.id + '] ' + (b.name || '?') + '\n';
            msg += '      ' + (b.state || '?') + ' | ' + (b.tonnage || '?') + ' tons | ' + ev + '\n';
          });
          if (r.data.by_state) {
            msg += '\n**By state:** ' + Object.entries(r.data.by_state).map(([s,n]) => s + '=' + n).join(', ');
          }
          if (stateFilter === 'active') {
            msg += '\n_For closed bids: `list bids killed` / `list bids won` / `list bids terminal`_';
          }
          appendMsg('ai', msg, null, 'LOCAL/bids');
        }
      } else {
        appendMsg('ai', 'Could not list bids: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'List bids error: ' + e, 'error'); }
    return;
  }

  // 3. Plate weight: "plate weight PL.5X12X12 x24", "weight of PL.5X12X12"
  const plateMatch = text.match(/(?:plate\s+weight|weight\s+of)\s+(.+?)(?:\s+(?:x|qty\s*[:=]?\s*)(\d+))?$/i);
  if (plateMatch) {
    const notation = plateMatch[1].trim();
    const qty = parseInt(plateMatch[2] || '1', 10);
    try {
      const r = await a.calculate_plate_weight(notation, qty);
      if (r && r.ok) {
        const d = r.data;
        const msg = '**' + notation + '** x' + qty + '\n  - Per piece: ' + (d.weight_per_piece_lbs || 0).toFixed(1) + ' lbs\n  - Total: ' + Math.round(d.weight_total_lbs || 0).toLocaleString() + ' lbs = ' + (d.weight_total_tons || 0).toFixed(3) + ' tons';
        appendMsg('ai', msg, null, 'LOCAL/plate');
      } else {
        appendMsg('ai', 'Plate calc failed: ' + (r && r.error || 'cannot parse notation'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Plate calc error: ' + e, 'error'); }
    return;
  }

  // 4. Misc steel: "misc steel for 65 tons", "misc factor 65 tons 18 members"
  //    P6 ROADMAP: lead with one-line summary; "misc steel detail N" shows the breakdown.
  const miscMatch = tl.match(/^(?:misc\s+steel|misc\s+factor|connection\s+steel)(?:\s+(detail|breakdown|full))?\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*tons?(?:\s+(\d+)\s+members?)?(?:\s+(\w+))?/);
  if (miscMatch) {
    const showDetail = !!miscMatch[1];
    const tons = parseFloat(miscMatch[2]);
    const mc = parseInt(miscMatch[3] || '10', 10);
    const bt = miscMatch[4] || 'commercial';
    try {
      const r = await a.estimate_misc_steel(tons, mc, bt);
      if (r && r.ok) {
        const d = r.data;
        let msg = '**' + (d.summary_line || ('misc steel = ' + (d.misc_tons || 0) + ' tons')) + '**';
        if (showDetail) {
          msg += '\n\nBreakdown on ' + tons + ' verified tons (' + bt + '):\n' +
                 '  + Plates: ' + (d.plate_tons || 0) + ' tons\n' +
                 '  + Connections: ' + (d.connection_tons || 0) + ' tons\n' +
                 '  + Remaining misc: ' + (d.remaining_misc_tons || 0) + ' tons\n' +
                 '  = TOTAL: ' + (d.total_tons || 0) + ' tons (+' + (d.tonnage_increase_pct || 0) + '%)';
        } else {
          msg += '\n_type `misc steel detail for ' + tons + ' tons` for the breakdown_';
        }
        appendMsg('ai', msg, null, 'LOCAL/misc');
      } else {
        appendMsg('ai', 'Misc steel calc failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Misc steel error: ' + e, 'error'); }
    return;
  }

  // 5. Generate proposal from bid: "proposal for bid 3", "generate proposal #3", "proposal for #3"
  const propMatch = tl.match(/(?:generate\s+)?proposal\s+(?:for\s+)?(?:bid\s*)?#?(\d+)/);
  if (propMatch) {
    const bidId = parseInt(propMatch[1], 10);
    try {
      const r = await a.generate_proposal_from_bid(bidId);
      if (r && r.ok) {
        const path = r.data.path || r.data.filename || '';
        appendMsg('ai', '**Proposal generated** for bid #' + bidId + '\n  File: ' + path, null, 'LOCAL/proposal');
      } else {
        appendMsg('ai', 'Proposal failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Proposal error: ' + e, 'error'); }
    return;
  }

  // 6. Quick bid: "bid 65 tons 22 joists 38400 sf" or "bid estimate 65t 38400sf"
  const bidMatch = tl.match(/^(?:quick\s+)?bid(?:\s+estimate)?\s+(\d+(?:\.\d+)?)\s*t(?:ons?)?(?:\s+(\d+(?:\.\d+)?)\s*j(?:oists?)?)?\s+(\d+(?:,\d+)?)\s*(?:sf|sqft)?/);
  if (bidMatch) {
    const st = parseFloat(bidMatch[1]);
    const jt = parseFloat(bidMatch[2] || '0');
    const sf = parseFloat(bidMatch[3].replace(/,/g, ''));
    try {
      const r = await a.quick_bid_estimate(st, jt, sf, 0, 'roof', 0, 'Quick estimate', '', '');
      if (r && r.ok) {
        const d = r.data;
        let msg = '**Quick bid estimate**\n';
        (d.line_items || []).forEach(li => {
          msg += '  - ' + li.desc + ': $' + (li.amount || 0).toLocaleString() + '\n';
        });
        msg += '\n**TOTAL: $' + (d.total_bid || 0).toLocaleString() + '** ($' + (d.per_sf || 0).toFixed(2) + '/SF)';
        if (d.vm_review) {
          msg += '\nVM: ' + (d.vm_review.approved ? 'approved' : 'BLOCKED') + ' (' + (d.vm_review.confidence || 0) + '%)';
        }
        appendMsg('ai', msg, null, 'LOCAL/bid');
      } else {
        appendMsg('ai', 'Quick bid failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Quick bid error: ' + e, 'error'); }
    return;
  }

  // 7. Build/plan full building: "build full building 5x4", "plan building 8x6 25ft 22ft eave"
  //    Optional keywords: "gable" or "gable roof" anywhere, "braced" or "with bracing" anywhere.
  const bldgMatch = tl.match(/^(plan|build|assemble)\s+(?:a\s+|the\s+|full\s+|whole\s+)?building\s+(\d+)\s*(?:[x×]|by)\s*(\d+)(?:\s+(\d+(?:\.\d+)?)\s*ft\s*bays?)?(?:\s+(\d+(?:\.\d+)?)\s*ft\s*eave)?/) ||
                    tl.match(/^(plan|build|assemble)\s+(?:a\s+|the\s+)?(\d+)\s*(?:[x×]|by)\s*(\d+)\s+(?:full\s+|whole\s+)?building(?:\s+(\d+(?:\.\d+)?)\s*ft\s*bays?)?(?:\s+(\d+(?:\.\d+)?)\s*ft\s*eave)?/);
  if (bldgMatch) {
    const mode = bldgMatch[1];               // plan or build/assemble
    const bx = parseInt(bldgMatch[2], 10);
    const by = parseInt(bldgMatch[3], 10);
    const spacing = parseFloat(bldgMatch[4] || '25');
    const eave = parseFloat(bldgMatch[5] || '18');
    const roof = /gable/i.test(tl) ? 'gable' : 'flat';
    const bracing = /\b(braced|bracing|x-?brac)/i.test(tl);
    // Optional pitch like "3:12" or "4:12"
    let pitch = 0.25;
    const pitchMatch = tl.match(/(\d+(?:\.\d+)?)[:\s]?12\s*(?:pitch|roof)?/);
    if (pitchMatch && roof === 'gable') {
      pitch = parseFloat(pitchMatch[1]) / 12.0;
    }
    try {
      let r;
      if (mode === 'plan') {
        r = await a.plan_building(bx, by, spacing, spacing, eave,
                                  'W12x65', 'W21x44', 'W18x40',
                                  roof, pitch, 'W18x35', 'W21x44',
                                  bracing, 'HSS6x6x1/2');
        if (r && r.ok) {
          const d = r.data;
          let msg = '**Plan: ' + bx + ' x ' + by + ' bays** (' + spacing + 'ft spacing, ' + eave + 'ft eave';
          if (roof === 'gable') msg += ', gable roof ' + pitch.toFixed(2) + ' pitch';
          if (bracing) msg += ', X-bracing';
          msg += ')\n' +
            '  - Footprint: ' + (bx*spacing) + 'ft x ' + (by*spacing) + 'ft = ' + d.building_sf.toLocaleString() + ' SF\n' +
            '  - Columns: ' + d.column_count + '\n' +
            '  - Beams: ' + d.beam_count + ' (' + d.perim_beam_count + ' perim';
          if (d.interior_beam_count) msg += ', ' + d.interior_beam_count + ' interior';
          if (d.rafter_count) msg += ', ' + d.rafter_count + ' rafters';
          if (d.ridge_count) msg += ', ' + d.ridge_count + ' ridge';
          if (d.brace_count) msg += ', ' + d.brace_count + ' brace';
          msg += ')\n' +
            '  - Total members: ' + d.total_members + '\n' +
            '  - Approx tonnage: **' + d.approx_tonnage + ' tons** (' + d.lb_per_sf + ' lb/SF)\n\n' +
            'To build the STL: `build building ' + bx + 'x' + by + (roof==='gable' ? ' gable' : '') + (bracing ? ' braced' : '') + '`';
          appendMsg('ai', msg, null, 'LOCAL/plan-building');
        } else {
          appendMsg('ai', 'Plan failed: ' + (r && r.error || 'no response'), 'error');
        }
      } else {
        r = await a.build_full_building(bx, by, spacing, spacing, eave,
                                        'W12x65', 'W21x44', 'W18x40', '',
                                        roof, pitch, 'W18x35', 'W21x44',
                                        bracing, 'HSS6x6x1/2');
        if (r && r.ok) {
          const d = r.data;
          let msg = '**' + d.message + '**\n' +
            '  - File: ' + d.filename + '\n' +
            '  - Path: ' + d.path + '\n' +
            '  - Members: ' + d.member_count + '\n' +
            '  - Triangles: ' + d.triangle_count.toLocaleString() + '\n' +
            '  - Size: ' + (d.file_size_bytes/1024).toFixed(1) + ' KB\n' +
            '  - Approx tonnage: ' + (d.plan ? d.plan.approx_tonnage + ' tons' : 'see plan') + '\n\n';
          // Inline thumbnail preview (Owner roadmap item)
          if (d.thumbnail_path) {
            // Convert local file path to file:// URI that pywebview can load
            const pathUri = 'file://' + d.thumbnail_path.replace(/\\/g, '/');
            msg += '![building preview](' + pathUri + ')\n\n';
          }
          if (d.stl_b64 && typeof loadStlBase64 === 'function') {
            try { loadStlBase64(d.stl_b64, d.filename || 'Building Model'); } catch(e) {}
            setMode('model');
            msg += 'Building loaded into MODEL viewer.';
          } else {
            msg += 'Open the .stl in Windows 3D Viewer, Blender, or any STL app.';
          }
          appendMsg('ai', msg, null, 'LOCAL/build-building');
        } else {
          let err = r && r.error || 'no response';
          if (r && r.fix) err += '\n**fix:** ' + r.fix;
          appendMsg('ai', 'Build failed: ' + err, 'error');
        }
      }
    } catch(e) { appendMsg('ai', 'Building error: ' + e, 'error'); }
    return;
  }

  // 8. iMessage internal (Path A): "text owner <msg>" or "text joseph <msg>"
  const internalText = text.match(/^(?:text|imessage|message)\s+(owner|joseph)[:\s]+(.+)$/i);
  if (internalText) {
    const who = internalText[1].toLowerCase();
    const body = internalText[2].trim();
    try {
      const fn = who === 'owner' ? a.text_owner_imessage : a.text_joseph_imessage;
      const r = await fn.call(a, body);
      if (r && r.ok) {
        appendMsg('ai', '**Sent to ' + who.charAt(0).toUpperCase() + who.slice(1) + '**\n  "' + body + '"', null, 'LOCAL/imessage');
      } else {
        appendMsg('ai', 'iMessage failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'iMessage error: ' + e, 'error'); }
    return;
  }

  // 9. iMessage external (Path B - GATED): "text Mike Verdugo: <msg>" (colon required to be safe)
  // Two-step: send_imessage_to_contact(preview_only=true) → render Confirm button →
  //          confirm_imessage_send(to, body) when button clicked.
  const externalText = text.match(/^(?:text|imessage|message)\s+([A-Z][A-Za-z\s\-']{1,40}):\s+(.+)$/);
  if (externalText) {
    const contact = externalText[1].trim();
    const body = externalText[2].trim();
    try {
      const r = await a.send_imessage_to_contact(contact, body, true, true);
      // Bridge returns: {ok, data: {preview: bool, draft: text, to: phone, gate: {}, confirm_action}}
      if (r && r.ok && r.data && r.data.preview === true) {
        const draftText = r.data.draft || body;
        const phone = r.data.to || contact;
        // Render preview with a Confirm button. Body gets escaped via textContent to avoid HTML injection.
        const btnId = 'imsg_confirm_' + Date.now();
        const escaped = draftText.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        const escContact = contact.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        const html =
          '<div style="border:1px solid var(--molten,#d4a256);padding:12px;border-radius:8px;background:rgba(212,162,86,0.06);">' +
          '<div style="font-weight:700;margin-bottom:6px;">iMessage preview - GATED (TCPA)</div>' +
          '<div style="margin-bottom:4px;"><strong>To:</strong> ' + escContact + ' (' + phone + ')</div>' +
          '<div style="margin-bottom:10px;font-style:italic;">"' + escaped + '"</div>' +
          '<button id="' + btnId + '" class="msg-act-btn" style="background:var(--molten,#d4a256);color:#000;font-weight:700;padding:6px 14px;">CONFIRM SEND</button>' +
          '<button id="' + btnId + '_cancel" class="msg-act-btn" style="margin-left:6px;">CANCEL</button>' +
          '</div>';
        appendMsg('ai', html, null, 'LOCAL/imessage-preview', true);
        // Wire the button AFTER it's in the DOM
        setTimeout(() => {
          const btn = document.getElementById(btnId);
          const cbtn = document.getElementById(btnId + '_cancel');
          if (btn) {
            btn.onclick = async () => {
              btn.disabled = true; btn.textContent = 'SENDING...';
              try {
                const r2 = await a.confirm_imessage_send(contact, body);
                if (r2 && r2.ok) {
                  btn.textContent = 'SENT ✓'; btn.style.background = 'var(--green,#4caf50)';
                  appendMsg('ai', 'iMessage to ' + contact + ' confirmed and sent.', null, 'LOCAL/imessage-sent');
                } else {
                  btn.textContent = 'FAILED'; btn.disabled = false;
                  appendMsg('ai', 'Send failed: ' + (r2 && r2.error || 'no response'), 'error');
                }
              } catch(e) {
                btn.textContent = 'ERROR'; btn.disabled = false;
                appendMsg('ai', 'Confirm error: ' + e, 'error');
              }
            };
          }
          if (cbtn) {
            cbtn.onclick = () => {
              if (btn) { btn.disabled = true; btn.style.opacity = '0.4'; }
              cbtn.textContent = 'CANCELLED'; cbtn.disabled = true;
            };
          }
        }, 0);
      } else if (r && r.ok) {
        // Some other ok response that doesn't require confirmation
        appendMsg('ai', 'Sent: ' + JSON.stringify(r.data).slice(0, 200), null, 'LOCAL/imessage');
      } else {
        const errMsg = r && r.error || 'no response';
        // Bridge returns blocked info in either r.data (when wrapped) or r (legacy)
        const blockedData = (r && r.data && r.data.blocked) ? r.data : ((r && r.blocked) ? r : null);
        if (blockedData || errMsg.toLowerCase().includes('engagement')) {
          let msg = '**Blocked: no engagement record on file for ' + contact + '**\n\n';
          msg += 'TCPA compliance requires a logged prior business engagement (email reply, meeting, referral) before any iMessage.\n\n';
          if (blockedData && blockedData.fix) {
            msg += '**fix:** ' + blockedData.fix;
          } else if (r && r.fix) {
            msg += '**fix:** ' + r.fix;
          } else {
            msg += 'Log one with: `create engagement record for ' + contact + '`';
          }
          appendMsg('ai', msg, null, 'LOCAL/imessage-blocked');
        } else {
          appendMsg('ai', 'iMessage preview failed: ' + errMsg, 'error');
        }
      }
    } catch(e) { appendMsg('ai', 'iMessage error: ' + e, 'error'); }
    return;
  }

  // 10. Engagement scan: "scan engagements" / "scan gmail" / "auto-create engagements"
  //     Without args this is a dry-run; the user must paste messages (or use a future
  //     Gmail MCP fetch). When backed by the connector this will become one-click.
  if(tl.match(/^(scan|preview|check)\s+(engagement|gmail)|^auto.?create\s+engagement/)){
    // For now, just inform Owner of the surface area. Real scan needs message data.
    appendMsg('ai',
      '**Engagement record auto-scan**\n\n' +
      'This scans email replies and proposes engagement records (TCPA gate).\n\n' +
      'Wire-up options:\n' +
      '  1. **Gmail MCP** (future): one-click pull recent replies, propose records\n' +
      '  2. **Single email** (now): use `propose_engagement_from_email` Bridge method\n' +
      '  3. **Batch** (now): use `scan_engagements_from_messages` with JSON message list\n\n' +
      'The scan never creates records on dry-run. Set `dry_run=false` to commit.\n' +
      'See `bridge/engagement_auto.py` for the parsing rules (sender, phone, company).',
      null, 'LOCAL/engagement-scan');
    return;
  }

  // 11. Daily status (one-liner): "status", "top of day", "quick status"
  if(tl.match(/^(status|top\s+of\s+day|daily\s+status|quick\s+status|how\s+(are\s+we|'?re?\s+we|are\s+things)(\s+doing|\s+going|\s+looking)?|how'?s\s+(it|things|everything)(\s+going|\s+looking)?|where\s+are\s+we|what'?s?\s+(the\s+)?(status|update|latest))$/)){
    try {
      const r = await a.daily_status();
      if (r && r.ok) {
        appendMsg('ai', r.data.status_line, null, 'LOCAL/daily-status');
      } else {
        appendMsg('ai', 'Status failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Status error: ' + e, 'error'); }
    return;
  }

  // 12. Update bid from drawing: "update bid 3 from <path>"
  //     Useful when Owner has a REVISED drawing for an existing bid -
  //     avoids the duplicate-bid problem.
  const updMatch = tl.match(/^update\s+bid\s+(\d+)\s+(?:from|with)\s+(.+)$/);
  if (updMatch) {
    const bidId = parseInt(updMatch[1], 10);
    const pdfPath = updMatch[2].trim().replace(/^['"]|['"]$/g, '');
    try {
      const r = await a.update_bid_from_drawing(bidId, pdfPath);
      if (r && r.ok) {
        const d = r.data;
        let msg = '**' + d.message + '**\n';
        msg += '  - Members extracted: ' + d.members_extracted + '\n';
        msg += '  - Tonnage delta: ' + (d.tonnage_delta != null ? (d.tonnage_delta >= 0 ? '+' : '') + d.tonnage_delta + ' tons' : 'unknown');
        appendMsg('ai', msg, null, 'LOCAL/update-bid');
      } else {
        let err = r && r.error || 'no response';
        if (r && r.fix) err += '\n**fix:** ' + r.fix;
        appendMsg('ai', 'Update failed: ' + err, 'error');
      }
    } catch(e) { appendMsg('ai', 'Update error: ' + e, 'error'); }
    return;
  }

  // 14a. Blockers: "blockers", "show blockers" - must come BEFORE compliance
  if(tl.match(/^(show\s+)?blockers?$/)){
    try {
      const r = await a.get_blockers();
      if (r && r.ok) {
        const d = r.data;
        const bl = Array.isArray(d) ? d : (d.blockers || []);
        let msg = bl.length ? ('**Blockers:** ' + bl.length + '\n' + bl.slice(0,10).map(b => '  - ' + (b.name || b.title || b.action || JSON.stringify(b))).join('\n')) : 'No active blockers.';
        appendMsg('ai', msg, null, 'LOCAL/blockers');
      } else {
        appendMsg('ai', 'Blockers: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Blockers error: ' + e, 'error'); }
    return;
  }

  // 14b. Compliance summary: "compliance status", "compliance", "what's blocked"
  if(tl.match(/^(compliance(\s+status|\s+summary)?|what'?s?\s+blocked|what'?s?\s+blocking\s+(us|me)?)$/)){
    try {
      const r = await a.compliance_summary();
      if (r && r.ok) {
        const d = r.data;
        let msg = '**Compliance:** ' + d.summary_line + '\n';
        if (d.priority_blockers && d.priority_blockers.length) {
          msg += '\n**Priority blockers:**\n';
          d.priority_blockers.forEach(b => {
            msg += '  - ' + b.item + '\n    ' + (b.owner || '') + '\n';
          });
        }
        if (d.cascade_hints && d.cascade_hints.length) {
          msg += '\n💡 **Cascade ready** (upstream blockers resolved):\n';
          d.cascade_hints.forEach(h => {
            msg += '  - #' + h.downstream_n + ' ' + h.downstream_item +
                   ' can move ' + h.current_status + ' → ' + h.suggested_status + '\n';
            msg += '    upstream OK: ' + (h.upstream_items || []).join(', ') + '\n';
            msg += '    ' + h.action + '\n';
          });
        }
        if (d.counts.open > 0) {
          msg += '\n' + d.counts.open + ' OPEN items not yet started.';
        }
        appendMsg('ai', msg, null, 'LOCAL/compliance-summary');
      } else {
        appendMsg('ai', 'Compliance summary failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Compliance error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 fix M: pipeline split (research vs active) ───────────
  // `pipeline` / `project pipeline` shows the research-seeds vs
  // active-bids breakdown that Fix E exposed on the backend.
  if(tl.match(/^(project\s+)?pipeline$|^show\s+pipeline$/)){
    try {
      const r = await a.get_project_pipeline();
      if (r && (r.ok||r.success) && r.data) {
        const d = r.data;
        let msg = '**Project pipeline**\n';
        msg += '- Research seeds: **' + (d.research_seeds_count||0) + '** (deep-research leads, no live bids)\n';
        msg += '- Active bids: **' + (d.active_count||0) + '**\n';
        if (d.by_source) {
          msg += '\n**By source:**\n';
          Object.entries(d.by_source).forEach(([src, n]) => {
            msg += '  - ' + src + ': ' + n + '\n';
          });
        }
        if ((d.active_count||0) === 0) {
          msg += '\n_No active bids. Drop a PDF in a `Bids to sort` folder or use `add bid` to populate._';
        }
        appendMsg('ai', msg, null, 'LOCAL/pipeline');
      } else {
        appendMsg('ai', 'Pipeline fetch failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Pipeline error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 fix L: compare grades shortcut ───────────────────────
  // `compare grades` runs grade_comparison on window._lastTakeoffMembers.
  // Without takeoff context, prompts the user to drop a PDF first.
  if(tl.match(/^(compare|grade)\s+grades?$|^grade\s+compar|^value\s+grades?$/)){
    const members = window._lastTakeoffMembers;
    if (!members || !members.length) {
      appendMsg('ai',
        'No takeoff loaded. Drop a structural PDF first, then run `compare grades`.',
        null, 'LOCAL/compare-grades');
      return;
    }
    try {
      const r = await a.compare_grades(JSON.stringify(members));
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**Grade comparison** (current: ' + (d.current_grade||'A992') + ')\n';
        msg += 'Current cost: $' + (d.current_cost||0).toLocaleString() + '\n';
        if (d.options && d.options.length) {
          msg += '\n**Alternatives:**\n';
          d.options.slice(0,5).forEach(o => {
            const sign = (o.savings_vs_current||0) >= 0 ? '+' : '';
            msg += '  - ' + o.grade + ': $' + (o.cost||0).toLocaleString() +
                   ' (' + sign + '$' + (o.savings_vs_current||0).toLocaleString() +
                   ', ' + ((o.savings_pct||0)).toFixed(1) + '%)\n';
          });
        }
        if (d.best_savings) {
          msg += '\n_Best savings: $' + (d.best_savings||0).toLocaleString() + '_';
        }
        appendMsg('ai', msg, null, 'LOCAL/compare-grades');
      } else {
        appendMsg('ai', 'compare_grades failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'compare_grades error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 fix L: erection order shortcut ───────────────────────
  if(tl.match(/^erection\s+(order|sequence|plan)$|^erection$|^sequence$/)){
    const members = window._lastTakeoffMembers;
    if (!members || !members.length) {
      appendMsg('ai',
        'No takeoff loaded. Drop a structural PDF first, then run `erection order`.',
        null, 'LOCAL/erection');
      return;
    }
    try {
      const r = await a.recommend_erection_order(JSON.stringify(members));
      if (r && r.ok && r.data) {
        const d = r.data;
        const seq = d.sequence || [];
        let msg = '**Erection sequence** (' + (d.total_pieces||seq.length) + ' pieces)\n';
        // Group by shape category for human-readable phases
        const columns = seq.filter(m =>
          /^HSS|^W14|^W12|^W10|^PIPE/i.test(m.shape||''));
        const beams = seq.filter(m => !columns.includes(m));
        if (columns.length) {
          msg += '\n**Phase 1 - Columns** (' + columns.length + ' marks)\n';
          columns.slice(0,10).forEach(m =>
            msg += '  - ' + m.mark + ' (' + m.shape + ') x' + (m.qty||1) + '\n');
          if (columns.length > 10) msg += '  - ... +' + (columns.length-10) + ' more\n';
        }
        if (beams.length) {
          msg += '\n**Phase 2 - Beams** (' + beams.length + ' marks)\n';
          beams.slice(0,10).forEach(m =>
            msg += '  - ' + m.mark + ' (' + m.shape + ') x' + (m.qty||1) + '\n');
          if (beams.length > 10) msg += '  - ... +' + (beams.length-10) + ' more\n';
        }
        appendMsg('ai', msg, null, 'LOCAL/erection');
      } else {
        appendMsg('ai', 'recommend_erection_order failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'erection order error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 fix L: truck-load planning shortcut ──────────────────
  if(tl.match(/^(plan\s+)?truck\s*(loads?|planning)$|^truck\s+plan$/)){
    const members = window._lastTakeoffMembers;
    if (!members || !members.length) {
      appendMsg('ai',
        'No takeoff loaded. Drop a structural PDF first, then run `truck loads`.',
        null, 'LOCAL/trucks');
      return;
    }
    // Convert members to pieces format
    const pieces = members.map((m, i) => ({
      mark: m.mark || m.designation || ('P' + (i+1)),
      weight_lbs: ((m.weight_per_ft||m.lb_per_ft||0) * (m.length_ft||m.length||0) * (m.qty||m.quantity||1)) || 100,
      sequence: m.sequence || 1
    }));
    try {
      const r = await a.plan_truck_loads(JSON.stringify(pieces), 48000);
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**Truck loads** (' + (d.truck_count||0) + ' trucks @ 48k lbs cap)\n';
        msg += 'Total: ' + (d.total_pieces||pieces.length) + ' pieces, ~'
            + (((d.total_weight_lbs||0)/2000)).toFixed(1) + ' tons\n';
        if (d.trucks && d.trucks.length) {
          msg += '\n**Per truck:**\n';
          d.trucks.slice(0,10).forEach((t, i) => {
            msg += '  - Truck #' + (i+1) + ': ' + (t.piece_count||0)
                + ' pcs, ' + ((t.weight_lbs||0)/1000).toFixed(1) + 'k lbs\n';
          });
        }
        appendMsg('ai', msg, null, 'LOCAL/trucks');
      } else {
        appendMsg('ai', 'plan_truck_loads failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'truck planning error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 pass 7: vendor quote shortcuts ───────────────────────
  // `vendor quotes` / `quotes` shows recent recorded vendor quotes.
  // `poll vendors` / `poll quotes` runs one poll cycle now.
  // `vendor whitelist` shows the locked sender domains.
  // `poller status` shows last-poll + counts.
  if(tl.match(/^(vendor\s+)?quotes?$|^show\s+(vendor\s+)?quotes?$|^recent\s+quotes?$/)){
    try {
      const r = await a.get_vendor_quotes(null, null, 30, null);
      if (r && r.ok && r.data) {
        const d = r.data;
        if (!d.count) {
          appendMsg('ai', 'No vendor quotes recorded in the last 30 days. Run `poll vendors` to check Outlook.',
            null, 'LOCAL/quotes');
          return;
        }
        let msg = '**Vendor quotes** (last 30d: ' + d.count + ')\n';
        d.quotes.slice(0,10).forEach(q => {
          msg += '\n  - ' + (q.doc_number||'?') + '  ' + (q.vendor_name||'?') +
                 ' / ' + (q.project_ref||'(no project)') + '\n    received ' +
                 (q.received_at||'?').slice(0,10) + ', ' + (q.attachments||[]).length +
                 ' attachment(s), signals: ' + ((q.signals||[]).join(',') || 'none');
        });
        appendMsg('ai', msg, null, 'LOCAL/quotes');
      } else {
        appendMsg('ai', 'get_vendor_quotes failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'quotes error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^poll\s+(vendors?|quotes?|mailbox|outlook)$|^check\s+(for\s+)?(new\s+)?quotes?$/)){
    try {
      const r = await a.poll_vendor_mailbox(false);
      if (r && r.ok && r.data) {
        const d = r.data;
        if (!d.polled) {
          appendMsg('ai', 'Poll skipped: ' + (d.reason||'unknown') +
            (d.fix ? '\n*fix: ' + d.fix + '*' : ''), null, 'LOCAL/poll');
          return;
        }
        let msg = '**Poll complete** (' + (d.recorded||[]).length + ' new, ' +
                  (d.skipped||0) + ' skipped, whitelist=' + (d.whitelist_size||0) + ')';
        (d.recorded||[]).forEach(r => {
          msg += '\n  + ' + r.doc_number + '  ' + r.vendor + ' / ' + r.project_ref;
        });
        appendMsg('ai', msg, null, 'LOCAL/poll');
      } else {
        appendMsg('ai', 'poll_vendor_mailbox failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'poll error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^(vendor\s+)?whitelist$|^show\s+whitelist$|^vendors?$/)){
    try {
      const r = await a.get_vendor_whitelist();
      if (r && r.ok && r.data) {
        const wl = r.data.whitelist || [];
        let msg = '**Vendor whitelist** (' + wl.length + ' locked)\n';
        wl.forEach(e => {
          msg += '\n  - ' + e.domain.padEnd(20) + ' ' + (e.vendor_name||'') +
                 ' (' + (e.vendor_type||'?') + ')';
        });
        msg += '\n\nAdd a new vendor: `add vendor <domain>`';
        appendMsg('ai', msg, null, 'LOCAL/whitelist');
      } else {
        appendMsg('ai', 'get_vendor_whitelist failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'whitelist error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^poller\s+status$|^vendor\s+status$/)){
    try {
      const r = await a.vendor_poller_status();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**Poller status**\n';
        msg += '  Last poll: ' + (d.last_poll_at || 'never') + '\n';
        msg += '  Total quotes: ' + (d.total_quotes||0) +
               ' (recent 30d: ' + (d.recent_quotes_30d||0) + ')\n';
        msg += '  Whitelist: ' + (d.whitelist_size||0) + ' domains\n';
        msg += '  Business hours now: ' + (d.business_hours_now ? 'yes' : 'no') + '\n';
        msg += '  Platform: ' + (d.platform||'?') +
               ' (Outlook ' + (d.outlook_available ? 'available' : 'unavailable') + ')';
        appendMsg('ai', msg, null, 'LOCAL/poller-status');
      } else {
        appendMsg('ai', 'vendor_poller_status failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'poller status error: ' + e, 'error'); }
    return;
  }
  const addVendorMatch = tl.match(/^add\s+vendor\s+([\w.-]+\.\w+)(?:\s+(.+))?$/);
  if (addVendorMatch) {
    const domain = addVendorMatch[1];
    const name = (addVendorMatch[2] || '').trim();
    try {
      const r = await a.add_vendor_to_whitelist(domain, name, 'service_center', '');
      if (r && r.ok && r.data) {
        if (r.data.added) {
          appendMsg('ai', 'Added `' + domain + '` to whitelist.', null, 'LOCAL/add-vendor');
        } else {
          appendMsg('ai', 'Not added: ' + (r.data.reason||'unknown'), null, 'LOCAL/add-vendor');
        }
      } else {
        appendMsg('ai', 'add_vendor_to_whitelist failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'add vendor error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 pass 8: model routing + Opus escalation ────────────
  // `models` shows the routing map (tier per task -> model).
  // `use opus for <task>` overrides one task to the max (Opus 4.7) tier.
  // `escalate to opus: <prompt>` runs a one-shot Opus 4.7 call.
  // `reset model routing` clears all overrides.
  if(tl.match(/^models?$|^model\s+(status|routing|map)$|^which\s+model/)){
    try {
      const r = await a.get_model_routing();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**Model routing** (' + (d.total_tasks||0) + ' tasks, ' +
                  (d.overridden_count||0) + ' overridden)\n';
        msg += '\n**Tiers available:**\n';
        Object.entries(d.tiers||{}).forEach(([t, spec]) => {
          msg += '  - `' + t + '` -> ' + spec.label + ' (' + spec.model + ') - ' + spec.cost_tier + ' cost\n';
        });
        msg += '\n**Active overrides:**\n';
        const overs = d.active_overrides || {};
        if (!Object.keys(overs).length) {
          msg += '  (none - all tasks on defaults)\n';
        } else {
          Object.entries(overs).forEach(([task, tier]) => {
            msg += '  - ' + task + ' -> ' + tier + '\n';
          });
        }
        msg += '\nOverride: `use <tier> for <task>` (e.g. `use opus for compliance`)\n';
        msg += 'Escalate now: `escalate to opus: <your prompt>`\n';
        msg += 'Reset all: `reset model routing`';
        appendMsg('ai', msg, null, 'LOCAL/models');
      } else {
        appendMsg('ai', 'get_model_routing failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'models error: ' + e, 'error'); }
    return;
  }
  const useTierMatch = tl.match(/^use\s+(fast|default|accurate|max|opus|opus[\s-]?4[.-]?7|opus[\s-]?4[.-]?6|sonnet|haiku)\s+for\s+(.+)$/);
  if (useTierMatch) {
    let tier = useTierMatch[1];
    const task = useTierMatch[2].trim().replace(/\s+/g, '_');
    // Normalize tier aliases
    if (tier.match(/opus[\s-]?4[.-]?7|^opus$/)) tier = 'max';
    else if (tier.match(/opus[\s-]?4[.-]?6/)) tier = 'accurate';
    else if (tier === 'sonnet') tier = 'default';
    else if (tier === 'haiku') tier = 'fast';
    try {
      const r = await a.set_model_routing(task, tier);
      if (r && r.ok && r.data) {
        appendMsg('ai', 'Set `' + task + '` -> ' + tier + ' (' + (r.data.model||'?') + ').',
          null, 'LOCAL/set-model');
      } else {
        appendMsg('ai', 'set_model_routing failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'set model error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^reset\s+model\s+routing$|^clear\s+(all\s+)?model\s+overrides?$/)){
    try {
      const r = await a.clear_model_routing('');
      if (r && r.ok && r.data) {
        appendMsg('ai', 'Cleared ' + (r.data.cleared||0) + ' override(s). All tasks back to defaults.',
          null, 'LOCAL/clear-models');
      } else {
        appendMsg('ai', 'clear_model_routing failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'clear model error: ' + e, 'error'); }
    return;
  }
  const opusMatch = tl.match(/^(escalate\s+to\s+opus|ask\s+opus|opus(?:\s+47?)?)[:\s]+(.+)$/i);
  if (opusMatch) {
    const promptText = opusMatch[2].trim();
    appendMsg('ai', '(escalating to Opus 4.7...)', null, 'LOCAL/opus');
    try {
      const r = await a.escalate_to_opus(promptText, '', 'max', 2000);
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**' + (d.model||'opus') + '** (' + (d.input_tokens||0) + ' in / ' +
                  (d.output_tokens||0) + ' out)\n\n' + (d.text || '(no output)');
        appendMsg('ai', msg, null, 'OPUS/' + (d.model||'?'));
      } else {
        appendMsg('ai', 'Opus call failed: ' + (r && r.error || 'no response') +
          (r && r.fix ? '\n*fix: ' + r.fix + '*' : ''), 'error');
      }
    } catch(e) { appendMsg('ai', 'opus error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 pass 8: remote MCP connectors ──────────────────────
  // `connectors` lists URL-based remote MCP servers attachable to API calls.
  // `add connector <name> <url>` registers one.
  // `remove connector <name>` deletes one.
  if(tl.match(/^(connectors|remote\s+mcps?|mcps?\s+remote|mcp\s+connectors)$/)){
    try {
      const r = await a.list_remote_mcps();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**Remote MCP connectors** (' + (d.total||0) + ' total, ' +
                  (d.enabled||0) + ' enabled)\n';
        (d.servers||[]).forEach(s => {
          const flag = s.enabled ? '+' : '-';
          msg += '\n  ' + flag + ' ' + s.name.padEnd(20) + ' ' + (s.url||'') +
                 '\n    ' + (s.description||'');
        });
        msg += '\n\nAdd: `add connector <name> <url>`\nUse in API call: `call with mcps <name>: <prompt>`';
        appendMsg('ai', msg, null, 'LOCAL/connectors');
      } else {
        appendMsg('ai', 'list_remote_mcps failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'connectors error: ' + e, 'error'); }
    return;
  }
  const addConnMatch = tl.match(/^add\s+(remote\s+mcp|connector)\s+([\w-]+)\s+(https:\/\/\S+)(?:\s+(.+))?$/);
  if (addConnMatch) {
    const name = addConnMatch[2];
    const url = addConnMatch[3];
    const desc = (addConnMatch[4] || '').trim();
    try {
      const r = await a.add_remote_mcp(name, url, desc, '');
      if (r && r.ok && r.data && r.data.added) {
        appendMsg('ai', 'Added connector `' + name + '` -> ' + url, null, 'LOCAL/add-conn');
      } else {
        appendMsg('ai', 'add connector failed: ' + (r && r.error || 'unknown'), 'error');
      }
    } catch(e) { appendMsg('ai', 'add connector error: ' + e, 'error'); }
    return;
  }
  const rmConnMatch = tl.match(/^remove\s+(connector|remote\s+mcp)\s+([\w-]+)$/);
  if (rmConnMatch) {
    const name = rmConnMatch[2];
    try {
      const r = await a.remove_remote_mcp(name);
      if (r && r.ok) {
        appendMsg('ai', 'Removed `' + name + '`.', null, 'LOCAL/rm-conn');
      } else {
        appendMsg('ai', 'remove connector failed: ' + (r && r.error || 'unknown'), 'error');
      }
    } catch(e) { appendMsg('ai', 'rm connector error: ' + e, 'error'); }
    return;
  }
  const callMcpMatch = tl.match(/^call\s+with\s+mcps?\s+([\w,-]+)[:\s]+(.+)$/);
  if (callMcpMatch) {
    const names = callMcpMatch[1];
    const promptText = callMcpMatch[2].trim();
    appendMsg('ai', '(calling Claude with MCP connectors: ' + names + '...)', null, 'LOCAL/mcp-call');
    try {
      const r = await a.call_with_mcps(promptText, names, '', 'default', '', 2000);
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**' + (d.model||'?') + '** via [' + (d.mcp_servers_used||[]).join(',') + ']\n\n';
        msg += (d.text || '(no output)');
        if ((d.mcp_tool_uses||[]).length) {
          msg += '\n\n_MCP tools used:_ ' +
            d.mcp_tool_uses.map(t => t.server + '.' + t.name).join(', ');
        }
        appendMsg('ai', msg, null, 'MCP/' + names);
      } else {
        appendMsg('ai', 'call_with_mcps failed: ' + (r && r.error || 'no response') +
          (r && r.fix ? '\n*fix: ' + r.fix + '*' : ''), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp call error: ' + e, 'error'); }
    return;
  }

  // ── v3.2.7 pass 9: HTTP MCP server (reverse direction) ────────
  // `start mcp http` / `start mcp server` boots the HTTP MCP transport.
  // `stop mcp http` shuts it down.
  // `mcp http status` / `mcp server status` shows running state.
  // `mcp token` shows the bearer token for claude.ai connector setup.
  // `rotate mcp token` regenerates the token.
  if(tl.match(/^start\s+mcp\s+(http|server|reverse)$|^expose\s+mcp$/)){
    try {
      const r = await a.start_mcp_http_server(7777, '127.0.0.1');
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg;
        if (d.started) {
          msg = '**MCP HTTP server started**\n' +
                '  Local URL: `' + d.url_local + '`\n' +
                '  Health: `' + d.health + '`\n' +
                '  Token fingerprint: ' + d.token_fingerprint + '\n\n' +
                'Next: run `cloudflared tunnel --url http://localhost:7777` to expose a public URL,\n' +
                'then paste that URL into claude.ai project Settings > Connectors.\n' +
                'Get the auth token with `mcp token`.';
        } else {
          msg = 'Not started: ' + (d.reason||'unknown') + '\n*fix: try `stop mcp http` first, then retry*';
        }
        appendMsg('ai', msg, null, 'LOCAL/mcp-http');
      } else {
        appendMsg('ai', 'start_mcp_http_server failed: ' + (r && r.error || 'no response') +
          (r && r.fix ? '\n*fix: ' + r.fix + '*' : ''), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp http start error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^stop\s+mcp\s+(http|server|reverse)$|^unexpose\s+mcp$/)){
    try {
      const r = await a.stop_mcp_http_server();
      if (r && r.ok && r.data) {
        appendMsg('ai', r.data.stopped ? 'MCP HTTP server stopped.'
                                       : ('Not stopped: ' + (r.data.reason||'unknown')),
          null, 'LOCAL/mcp-http');
      } else {
        appendMsg('ai', 'stop_mcp_http_server failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp http stop error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^mcp\s+(http\s+)?(status|server\s+status)$|^mcp\s+server$/)){
    try {
      const r = await a.mcp_http_server_status();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**MCP HTTP server status**\n';
        msg += '  Running: ' + (d.running ? 'yes' : 'no') + '\n';
        if (d.running) {
          msg += '  URL: ' + (d.url_local||'?') + '\n';
          msg += '  Thread alive: ' + (d.thread_alive ? 'yes' : 'no') + '\n';
          msg += '  Recent calls (last 60s): ' + (d.recent_call_count||0) + '\n';
        }
        msg += '  Token file: ' + (d.token_file_exists ? 'present' : 'not yet generated');
        appendMsg('ai', msg, null, 'LOCAL/mcp-status');
      } else {
        appendMsg('ai', 'mcp_http_server_status failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp status error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^(mcp\s+token|show\s+mcp\s+token|get\s+mcp\s+token)$/)){
    try {
      const r = await a.get_mcp_token();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**MCP bearer token** (paste into claude.ai connector auth)\n\n';
        msg += '`' + d.header_value + '`\n\n';
        msg += '_fingerprint:_ ' + d.fingerprint + '\n';
        msg += '_full token:_ `' + d.token + '`';
        appendMsg('ai', msg, null, 'LOCAL/mcp-token');
      } else {
        appendMsg('ai', 'get_mcp_token failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp token error: ' + e, 'error'); }
    return;
  }
  if(tl.match(/^rotate\s+mcp\s+token$|^new\s+mcp\s+token$/)){
    try {
      const r = await a.rotate_mcp_token();
      if (r && r.ok && r.data) {
        const d = r.data;
        let msg = '**New MCP token generated**\n\n';
        msg += '`Bearer ' + d.token + '`\n\n';
        msg += '_fingerprint:_ ' + d.fingerprint + '\n';
        msg += '_warning:_ ' + d.warning;
        appendMsg('ai', msg, null, 'LOCAL/mcp-rotate');
      } else {
        appendMsg('ai', 'rotate_mcp_token failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'mcp rotate error: ' + e, 'error'); }
    return;
  }

  // ── ROADMAP r9: cascade compliance ──────────────────────────────
  // `cascade compliance N` advances item N from BLOCKED to OPEN when
  // its upstream dependencies are all OK. Surfaced in `compliance` hints.
  const cascadeMatch = tl.match(/^cascade\s+compliance\s+(\d+)(?:\s+to\s+(open|monitor|ok))?(?:\s+(.+))?$/);
  if (cascadeMatch) {
    const item_n = parseInt(cascadeMatch[1], 10);
    const target = (cascadeMatch[2] || 'OPEN').toUpperCase();
    const note = (cascadeMatch[3] || '').trim();
    try {
      const r = await a.cascade_compliance(item_n, target, note);
      if (r && r.ok) {
        appendMsg('ai', r.data.message, null, 'LOCAL/cascade-compliance');
      } else {
        let m = (r && r.error) || 'cascade_compliance failed';
        if (r && r.fix) m += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', m, 'error');
      }
    } catch(e) { appendMsg('ai', 'Cascade error: ' + e, 'error'); }
    return;
  }

  // ── set compliance N status VALUE [note] ────────────────────────
  // Direct manual flip - no dependency preconditions.
  // "set compliance 9 status ok COI received"
  // "mark compliance 3 open MFA enabled on all accounts"
  // "compliance 6 ok" (shorthand)
  const setCompMatch = tl.match(
    /^(?:set|mark)\s+compliance\s+(\d+)\s+(?:status\s+)?(blocked|open|monitor|ok)(?:\s+(.+))?$|^compliance\s+(\d+)\s+(blocked|open|monitor|ok)(?:\s+(.+))?$/i
  );
  if (setCompMatch) {
    const item_n = parseInt(setCompMatch[1] || setCompMatch[4], 10);
    const status = (setCompMatch[2] || setCompMatch[5] || 'OPEN').toUpperCase();
    const note = (setCompMatch[3] || setCompMatch[6] || '').trim();
    try {
      const r = await a.set_compliance_status(item_n, status, note);
      if (r && r.ok) {
        appendMsg('ai', r.data.message, null, 'LOCAL/set-compliance');
      } else {
        let m = (r && r.error) || 'set_compliance_status failed';
        if (r && r.fix) m += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', m, 'error');
      }
    } catch(e) { appendMsg('ai', 'Set compliance error: ' + e, 'error'); }
    return;
  }

  // ── ROADMAP item 3: compliance change audit ─────────────────────
  // "compliance diff", "what changed", "compliance changes", "compliance since"
  const cDiffMatch = tl.match(/^(?:compliance\s+(?:diff|changes?|delta)|what\s+changed(?:\s+in\s+compliance)?|compliance\s+since\s+(\d+)\s*d(?:ays?)?)$/);
  if (cDiffMatch) {
    const sinceDays = cDiffMatch[1] ? parseInt(cDiffMatch[1], 10) : 7;
    try {
      const r = await a.compliance_diff(sinceDays);
      if (r && r.ok) {
        const d = r.data;
        if (!d.diff || !d.diff.length) {
          const msg = d.message ||
            `No compliance changes in the last ${sinceDays} day(s).`;
          appendMsg('ai', msg, null, 'LOCAL/compliance-diff');
        } else {
          let msg = `**Compliance changes** (vs ${(d.since || '').slice(0,10)}, ${d.changed_count} item(s))\n`;
          if (d.improved) msg += `  ✓ ${d.improved} improved\n`;
          if (d.worsened) msg += `  ⚠ ${d.worsened} worsened\n`;
          if (d.added)    msg += `  + ${d.added} added\n`;
          if (d.removed)  msg += `  - ${d.removed} removed\n`;
          msg += '\n';
          d.diff.forEach(c => {
            const icon = c.direction === 'improved' ? '✓'
                       : c.direction === 'worsened' ? '⚠'
                       : c.direction === 'added' ? '+'
                       : '-';
            msg += `  ${icon} ${c.item}: ${c.from} → ${c.to}\n`;
          });
          appendMsg('ai', msg, null, 'LOCAL/compliance-diff');
        }
      } else {
        appendMsg('ai', 'Compliance diff failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Compliance diff error: ' + e, 'error'); }
    return;
  }

  // ── ROADMAP item 5: force-new flag for next PDF drop ────────────
  if (/^(force\s+new(\s+bid)?|next\s+(file|pdf|drop)\s+is\s+(a\s+)?new\s+bid|new\s+bid\s+from\s+(next|file|drop))$/.test(tl)) {
    window._forceNextDropAsNewBid = true;
    appendMsg('ai',
      '✓ Force-new flag armed. The **next** PDF you drop will create a brand-new bid, not update an existing one.\n\n_If you change your mind, type `cancel force new` before dropping._',
      null, 'LOCAL/force-new-armed');
    return;
  }
  if (/^cancel\s+force\s+new(\s+bid)?$/.test(tl)) {
    if (window._forceNextDropAsNewBid) {
      window._forceNextDropAsNewBid = false;
      appendMsg('ai', '✓ Force-new flag cleared.', null, 'LOCAL/force-new-cleared');
    } else {
      appendMsg('ai', 'No force-new flag was set.', null, 'LOCAL/force-new-cleared');
    }
    return;
  }

  // ── ROADMAP follow-up: bulk-kill all stale bids ────────────────
  const killAllMatch = tl.match(/^kill\s+all\s+stale(?:\s+(\d+)\s*d(?:ays?)?)?(?:\s+(confirm|commit|do\s+it))?$/);
  if (killAllMatch) {
    const days = parseInt(killAllMatch[1] || '30', 10);
    const confirm = !!killAllMatch[2];
    try {
      const r = await a.kill_all_stale_bids(days, confirm);
      if (r && r.ok) {
        const d = r.data;
        let msg = '';
        if (d.preview) {
          msg = `**${d.stale_count} bid(s) stale ${days}+ days:**\n`;
          (d.stale_bids || []).forEach(b => {
            msg += `  - #${b.id} ${b.name} (${b.state}, ${b.days_stale}d)\n`;
          });
          msg += '\n_type `kill all stale confirm` to advance these to PASSED_';
        } else {
          msg = d.message;
          if (d.killed_count > 0) {
            msg += '\n\nKilled:\n';
            (d.killed_bids || []).forEach(b => {
              msg += `  - #${b.id} ${b.name}\n`;
            });
          }
        }
        appendMsg('ai', msg, null, 'LOCAL/kill-all-stale');
      } else {
        appendMsg('ai', (r && r.error) || 'kill_all_stale failed', 'error');
      }
    } catch(e) { appendMsg('ai', 'kill_all_stale error: ' + e, 'error'); }
    return;
  }

  // ── r18: pipeline summary by score band
  const pipeSummaryMatch = tl.match(/^(?:pipeline|score)\s+(?:summary|health)$/);
  if (pipeSummaryMatch) {
    try {
      const r = await a.pipeline_summary_by_score();
      if (r && r.ok) {
        const d = r.data;
        let txt = '**Pipeline Health**\n' + d.summary_line;
        if (d.total_count > 0) {
          txt += '\n\nTotal: $' + d.total_value.toLocaleString() + ' across ' + d.total_count + ' active bid(s)';
        }
        appendMsg('ai', txt, null, 'LOCAL/pipeline-summary');
      } else {
        let msg = (r && r.error) || 'pipeline_summary failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'pipeline_summary error: ' + e, 'error'); }
    return;
  }

  // ── r18: rescore all active bids
  const rescoreAllMatch = tl.match(/^(?:rescore|recompute|refresh)\s+(?:all|scores)$/);
  if (rescoreAllMatch) {
    try {
      const r = await a.rescore_all_bids();
      if (r && r.ok) {
        const d = r.data;
        let txt = d.message;
        if (d.changed && d.changed.length) {
          txt += '\n\nBids that moved:';
          for (const c of d.changed) {
            const sign = c.delta >= 0 ? '+' : '';
            txt += '\n  #' + c.bid_id + ' ' + c.name + ': ' + c.old_score + ' -> ' + c.new_score + ' (' + sign + c.delta + ')';
          }
        }
        appendMsg('ai', txt, null, 'LOCAL/rescore-all');
      } else {
        let msg = (r && r.error) || 'rescore_all_bids failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'rescore_all error: ' + e, 'error'); }
    return;
  }

  // ── r16: gp only N: regenerate the GP report without the client PDF
  const gpOnlyMatch = tl.match(/^(?:gp|gross\s*profit)\s+(?:only|report)?\s*(?:bid\s+)?(\d+)$/);
  if (gpOnlyMatch) {
    const bid_id = parseInt(gpOnlyMatch[1], 10);
    try {
      const r = await a.generate_gp_only(bid_id);
      if (r && r.ok) {
        const d = r.data;
        appendMsg('ai',
          d.message + '\n*' + d.gp_path + '*',
          null, 'LOCAL/gp-only');
      } else {
        let msg = (r && r.error) || 'generate_gp_only failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'gp_only error: ' + e, 'error'); }
    return;
  }

  // ── r16: score bid N: show pipeline score with factor breakdown
  const scoreBidMatch = tl.match(/^(?:score|rank)\s+bid\s+(\d+)$/);
  if (scoreBidMatch) {
    const bid_id = parseInt(scoreBidMatch[1], 10);
    try {
      const r = await a.pipeline_score(bid_id);
      if (r && r.ok) {
        const d = r.data;
        let txt = d.message;
        if (d.factors && d.factors.length) {
          txt += '\n\nFactors:';
          for (const f of d.factors) {
            const sign = f.delta >= 0 ? '+' : '';
            txt += '\n  ' + sign + f.delta + '  ' + f.label;
          }
        }
        appendMsg('ai', txt, null, 'LOCAL/pipeline-score');
      } else {
        let msg = (r && r.error) || 'pipeline_score failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'pipeline_score error: ' + e, 'error'); }
    return;
  }

  // ── P2 ROADMAP: kill / nogo / dead bid shortcuts ────────────────
  const killMatch = tl.match(/^(?:kill|nogo|no[\s-]?go|dead)\s+bid\s+(\d+)(?:\s+(.+))?$/);
  if (killMatch) {
    const bid_id = parseInt(killMatch[1], 10);
    const reason = (killMatch[2] || '').trim();
    try {
      const r = await a.kill_bid(bid_id, reason);
      if (r && r.ok) {
        const d = r.data;
        appendMsg('ai', d.message + ' (' + d.from + ' → ' + d.to + ')', null, 'LOCAL/kill-bid');
      } else {
        let msg = (r && r.error) || 'kill_bid failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'kill_bid error: ' + e, 'error'); }
    return;
  }

  // ── ROADMAP item 2: restore bid (mirror of kill bid) ───────────
  const restoreMatch = tl.match(/^(?:restore|unkill|revive|reopen)\s+bid\s+(\d+)(?:\s+(?:to\s+)?(scanned|reviewing|pursuing|submitted))?(?:\s+(.+))?$/);
  if (restoreMatch) {
    const bid_id = parseInt(restoreMatch[1], 10);
    const target = (restoreMatch[2] || '').toUpperCase();
    const notes = (restoreMatch[3] || '').trim();
    try {
      const r = await a.restore_bid(bid_id, target, notes);
      if (r && r.ok) {
        const d = r.data;
        appendMsg('ai', d.message, null, 'LOCAL/restore-bid');
      } else {
        let msg = (r && r.error) || 'restore_bid failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'restore_bid error: ' + e, 'error'); }
    return;
  }

  // ── P7 ROADMAP: mark bid won / lost (and won/lost bid N) ────────
  const wonLostMatch = tl.match(/^(?:mark\s+bid\s+(\d+)\s+(won|lost)|(won|lost|awarded)\s+bid\s+(\d+))(?:\s+(.+))?$/);
  if (wonLostMatch) {
    let bid_id, outcome, notes;
    if (wonLostMatch[1]) {
      bid_id = parseInt(wonLostMatch[1], 10);
      outcome = wonLostMatch[2];
    } else {
      const verb = wonLostMatch[3];
      outcome = (verb === 'awarded') ? 'won' : verb;
      bid_id = parseInt(wonLostMatch[4], 10);
    }
    notes = (wonLostMatch[5] || '').trim();
    try {
      const fn = (outcome === 'won') ? a.mark_bid_won : a.mark_bid_lost;
      const r = await fn(bid_id, notes);
      if (r && r.ok) {
        const d = r.data;
        let msg = d.message;
        if (d.transitions && d.transitions.length > 1) {
          msg += '\n  Path: ' + d.transitions.map(t => t.from + '→' + t.to).join(' → ');
        }
        appendMsg('ai', msg, null, 'LOCAL/mark-bid-' + outcome);
      } else {
        let msg = (r && r.error) || 'mark_bid_' + outcome + ' failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'mark_bid error: ' + e, 'error'); }
    return;
  }

  // ── P3 ROADMAP: proposal preview before generating the PDF ───────
  const previewMatch = tl.match(/^(?:preview\s+proposal|proposal\s+preview)(?:\s+(?:for\s+)?bid\s+(\d+))?$/);
  if (previewMatch) {
    const bid_id = parseInt(previewMatch[1] || '0', 10);
    try {
      const r = await a.preview_proposal_from_bid(bid_id, '', '');
      if (r && r.ok) {
        const d = r.data;
        let msg = '**Proposal Preview - Bid ' + d.bid_id + ': ' + d.project_name + '**\n\n';
        msg += '  Tonnage: ' + (d.tonnage || 0).toFixed(1) + ' tons\n';
        msg += '  Total:   **$' + (d.total_bid || 0).toLocaleString() + '**';
        if (d.value_auto_computed) msg += ' _(auto-computed at $4,200/ton)_';
        msg += '\n\n**Scope:**\n' + d.scope_text + '\n\n';
        msg += '_' + d.next_step + '_';
        appendMsg('ai', msg, null, 'LOCAL/proposal-preview');
      } else {
        let msg = (r && r.error) || 'preview_proposal failed';
        if (r && r.fix) msg += '\n*fix: ' + r.fix + '*';
        appendMsg('ai', msg, 'error');
      }
    } catch(e) { appendMsg('ai', 'preview error: ' + e, 'error'); }
    return;
  }

  // 13. Scan recent Gmail for engagements: "scan gmail", "check email for engagements"
  // P4 ROADMAP: chat command now COMMITS records by default (dry_run=false).
  // Use "scan gmail dry" or "preview gmail scan" if you want a dry run.
  const gmailMatch = tl.match(/^(?:scan\s+(?:gmail|email|mail|inbox)|check\s+(?:gmail|email|mail|inbox)\s+for\s+engagements?|gmail\s+scan|preview\s+gmail\s+scan|(?:anything|what'?s?)\s+new\s+(?:in\s+)?(?:gmail|email|mail|inbox)|any\s+(?:new\s+)?(?:email|emails|gmail)|pull\s+recent\s+emails?|check\s+(?:gmail|email|mail|inbox))(?:\s+(?:(dry|preview)|(\d+)\s*d(?:ays?)?(?:\s+(dry|preview))?|(dry|preview)\s+(\d+)\s*d(?:ays?)?))?$/);
  if (gmailMatch) {
    // Parse: optional "dry"/"preview" + optional N-day window in any order
    const isPreview = /preview/.test(tl);
    const isDry = isPreview || !!(gmailMatch[1] || gmailMatch[3] || gmailMatch[5]);
    const days = parseInt(gmailMatch[2] || gmailMatch[6] || '1', 10);
    const dryRun = isDry;
    try {
      const r = await a.scan_recent_gmail_for_engagements(days, 50, dryRun);
      if (r && r.ok) {
        const d = r.data;
        const c = d.counts || {};
        const verb = dryRun ? 'preview' : 'committed';
        let msg = '**Gmail ' + verb + ' (' + (d.days_back || days) + ' day(s) back): ' + (d.scanned || 0) + ' messages**\n';
        msg += '  - ' + (dryRun ? 'Would create' : 'Created') + ': ' + (c.create || 0) + '\n';
        msg += '  - Already on file: ' + (c.exists || 0) + '\n';
        msg += '  - Skipped (no phone): ' + (c.no_phone || 0) + '\n';
        msg += '  - Skipped (no sender): ' + (c.no_sender || 0) + '\n';
        if (dryRun && (c.create || 0) > 0) {
          msg += '\nThis was a preview. Run `scan gmail` (without `dry`) to commit.';
        } else if (!dryRun && (c.create || 0) > 0) {
          msg += '\nRecords are now on file. iMessage gating will pass for these contacts.';
        }
        if (d.message) msg += '\n\n' + d.message;
        appendMsg('ai', msg, null, 'LOCAL/gmail-scan');
      } else {
        let err = r && r.error || 'no response';
        if (r && r.fix) err += '\n**fix:** ' + r.fix;
        appendMsg('ai', 'Gmail scan failed: ' + err, 'error');
      }
    } catch(e) { appendMsg('ai', 'Gmail scan error: ' + e, 'error'); }
    return;
  }

  // 15. AISC shape lookup: "lookup W14X82", "shape W14X82", "W14X82 properties"
  const lookupMatch = tl.match(/^(?:lookup|shape|info|properties)\s+([A-Z]+\d+[A-Z]*\d*)/i) || tl.match(/^([WCS]\d+[Xx]\d+)\s*(?:properties|info|data)?$/i);
  if (lookupMatch) {
    const desig = lookupMatch[1].toUpperCase().replace(/X/, 'X');
    try {
      const r = await a.get_aisc_member_info(desig);
      if (r && r.ok) {
        const d = r.data;
        let msg = '**' + d.designation + '** (AISC v16.0)\n';
        msg += '  - Weight: ' + d.lb_per_ft + ' lb/ft\n';
        msg += '  - Depth: ' + d.depth_in + '"\n';
        msg += '  - Flange width: ' + d.flange_w_in + '"\n';
        msg += '  - Flange thickness: ' + d.tf_in + '"\n';
        msg += '  - Web thickness: ' + d.tw_in + '"';
        appendMsg('ai', msg, null, 'LOCAL/aisc-lookup');
      } else {
        appendMsg('ai', 'AISC lookup: ' + (r && r.error || 'shape not found'), 'error');
      }
    } catch(e) { appendMsg('ai', 'AISC lookup error: ' + e, 'error'); }
    return;
  }

  // 16. Standalone 3D model: "3d model of W14X82 at 20ft", "3d W14X82 30ft"
  const model3dMatch = tl.match(/3d\s*(?:model)?\s*(?:of\s+)?([A-Z]+\d+[A-Z]*\d*)\s*(?:at\s+)?(\d+)\s*(?:ft|feet|')?/i);
  if (model3dMatch) {
    const shape = model3dMatch[1].toUpperCase().replace(/X/, 'X');
    const lengthFt = parseFloat(model3dMatch[2]);
    appendMsg('ai', '', 'loading');
    try {
      const r = await a.generate_3d_view(shape, lengthFt, 1);
      removeLoading();
      if (r && r.ok) {
        const d = r.data;
        if (typeof loadStlBase64 === 'function' && d.stl_b64) {
          loadStlBase64(d.stl_b64, shape + ' x ' + lengthFt + 'ft');
        }
        let msg = '**3D model: ' + shape + ' at ' + lengthFt + ' ft**\n';
        msg += '  - Weight: ' + (d.weight_lbs||0).toLocaleString() + ' lbs (' + (d.weight_tons||0).toFixed(2) + ' tons)\n';
        msg += '  - Depth: ' + (d.depth_in||'?') + '" / Flange: ' + (d.flange_in||'?') + '"\n';
        msg += '  - STL size: ' + ((d.stl_bytes||0) / 1024).toFixed(0) + ' KB';
        appendMsg('ai', msg, null, 'LOCAL/aisc-calc');
      } else {
        appendMsg('ai', '3D model error: ' + (r && r.error || 'failed'), 'error');
      }
    } catch(e) { removeLoading(); appendMsg('ai', '3D error: ' + e, 'error'); }
    return;
  }

  // 17. Steel prices: "steel prices", "steel price", "market prices"
  if (tl.match(/^(?:steel\s+)?prices?$|^market\s+prices?$|^steel\s+market$/)) {
    try {
      const r = await a.fred_key_status();
      if (r && r.ok && r.data && r.data.has_key) {
        const sr = await a.get_steel_prices ? a.get_steel_prices() : null;
        if (sr && sr.ok) {
          appendMsg('ai', sr.data.summary || JSON.stringify(sr.data), null, 'LOCAL/steel-prices');
        } else {
          appendMsg('ai', 'FRED key present but steel price fetch not available. Use desktop chat for full data.', null, 'LOCAL/steel-prices');
        }
      } else {
        appendMsg('ai', '**Steel prices:** FRED API key not configured.\n\nSet up: drop your FRED key in `API Keys/FRED API Key.txt` and restart.\nGet a free key at https://fred.stlouisfed.org/docs/api/api_key.html', null, 'LOCAL/steel-prices');
      }
    } catch(e) { appendMsg('ai', 'Steel price error: ' + e, 'error'); }
    return;
  }

  // 18. VJ scan: "scan and fix", "scan", "vj scan", "code scan"
  // v3.2.7.15: async + poll. Previous version blocked the JS bridge
  // thread on the synchronous vj_scan_and_fix() call. On a real install
  // the scan takes 60-180s (Defender, AISC warmup, diagnostics) and
  // Windows would mark the window "(Not Responding)" after ~10s.
  // Now: kick off async, poll every 2s, animate the dots.
  if (tl.match(/^(?:scan\s+and\s+fix|vj\s+scan(?:\s+and\s+fix)?|code\s+scan|scan\s+codebase|run\s+scan|self[\s-]*repair)$/)) {
    let scanDots = 0;
    const renderLoading = () => {
      const dots = '.'.repeat((scanDots % 4));
      const spaces = ' '.repeat(3 - (scanDots % 4));
      // Replace the loading message text in place if helper exists
      try {
        const el = document.querySelector('.msg.loading');
        if (el) el.textContent = 'Running VJ scan' + dots + spaces + ' (background, UI stays responsive)';
      } catch(_) {}
      scanDots++;
    };
    appendMsg('ai', 'Running VJ scan... (background, UI stays responsive)', 'loading');
    try {
      const r = await a.vj_scan_and_fix_async(true);
      if (!r || !r.ok) {
        removeLoading();
        appendMsg('ai', 'VJ scan failed to start: ' + (r && r.error || 'no response'), 'error');
        return;
      }
      const jobId = (r.data && r.data.job_id) || '';
      if (!jobId) {
        removeLoading();
        appendMsg('ai', 'VJ scan: no job_id returned', 'error');
        return;
      }
      // Poll every 2 seconds. Cap at 5 minutes (150 polls).
      let polls = 0;
      const maxPolls = 150;
      const dotsTimer = setInterval(renderLoading, 700);
      const poll = async () => {
        polls++;
        try {
          const pr = await a.poll_vj_scan(jobId);
          if (pr && pr.ok && pr.data && pr.data.status === 'scanning') {
            if (polls < maxPolls) {
              setTimeout(poll, 2000);
            } else {
              clearInterval(dotsTimer);
              removeLoading();
              appendMsg('ai', 'VJ scan timed out after 5 minutes. Check data/vj_logs/ for partial results.', 'error');
            }
            return;
          }
          // Result returned
          clearInterval(dotsTimer);
          removeLoading();
          if (pr && pr.ok) {
            const d = pr.data;
            const bs = d.by_severity || {high:0, medium:0, low:0};
            const tbs = d.top_by_severity || {high:[], medium:[], low:[]};
            let msg = '**VJ scan complete** (' + (d.files_scanned||0) + ' files in ' + Math.round((d.scan_duration_ms||0)/100)/10 + 's)\n';
            msg += '  - **' + (d.issues_found||0) + '** issues: ';
            msg += bs.high + ' P0 / ' + bs.medium + ' P1 / ' + bs.low + ' informational\n';
            if (d.warnings_count) msg += '  - Warnings: ' + d.warnings_count + '\n';
            if (d.fixes_applied) msg += '  - **' + d.fixes_applied + ' auto-fixes applied**\n';
            if (d.issues_found === 0) {
              msg += '\nCodebase is clean.';
            } else {
              const showSev = (label, arr) => {
                if (!arr.length) return '';
                let s = '\n**Top ' + label + ' issues:**\n';
                arr.forEach((it, i) => {
                  const fileShort = (it.file||'').split(/[\\/]/).pop() || '?';
                  s += '  ' + (i+1) + '. `' + it.category + '` ' + fileShort + ':' + (it.line||'?') + '\n';
                });
                return s;
              };
              if (bs.high > 0) msg += showSev('P0', tbs.high);
              else if (bs.medium > 0) msg += showSev('P1', tbs.medium.slice(0,5));
              else msg += showSev('informational', tbs.low.slice(0,5));
              msg += '\n_Full list in log: ' + (d.log_path||'data/vj_logs/') + '_';
            }
            appendMsg('ai', msg, null, 'LOCAL/vj-scan');
          } else {
            appendMsg('ai', 'VJ scan failed: ' + (pr && pr.error || 'no response'), 'error');
          }
        } catch(e) {
          clearInterval(dotsTimer);
          removeLoading();
          appendMsg('ai', 'VJ scan poll error: ' + e, 'error');
        }
      };
      setTimeout(poll, 2000);
    } catch(e) { removeLoading(); appendMsg('ai', 'VJ scan error: ' + e, 'error'); }
    return;
  }

  // 19a. Scope creep check: "scope creep check: <email text>"
  //      Owner roadmap #6 (pass 10f): wires the help-listed command.
  const screepMatch = tl.match(/^scope\s+creep\s+check\s*:\s*(.+)$/i);
  if (screepMatch) {
    const emailText = screepMatch[1].trim();
    if (!emailText) {
      appendMsg('ai', 'Paste the email body or RFI text after the colon. Example: `scope creep check: please add the canopy framing per RFI 12`', null, 'LOCAL/scope-creep');
      return;
    }
    try {
      const r = await a.check_scope_creep_text(emailText);
      if (r && r.ok) {
        const d = r.data;
        let msg = '**Scope creep check**\n';
        msg += '  - Verdict: **' + (d.verdict || '?') + '**\n';
        if (d.matched_phrases && d.matched_phrases.length) {
          msg += '  - Matched: ' + d.matched_phrases.map(p => '`'+p+'`').join(', ') + '\n';
        }
        msg += '  - Recommended action: ' + (d.recommended_action || '?');
        appendMsg('ai', msg, null, 'LOCAL/scope-creep');
      } else {
        appendMsg('ai', 'scope check failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'scope check error: ' + e, 'error'); }
    return;
  }

  // 19b. Draft email to <name>: routes through ai_ask with the Owner's voice
  //      Owner roadmap #6 (pass 10f): wires the help-listed command.
  const draftMatch = tl.match(/^draft\s+email\s+to\s+(.+)$/i);
  if (draftMatch) {
    const recipientName = draftMatch[1].trim();
    if (!recipientName) {
      appendMsg('ai', 'Tell me who. Example: `draft email to James Wright` then I will ask what it is about.', null, 'LOCAL/draft-email');
      return;
    }
    appendMsg('ai',
      '**Drafting email to ' + recipientName + '**\n\nTell me:\n  - **What is it about?** (bid follow-up, RFI response, schedule change, etc.)\n  - **Any details to include?** (bid number, dates, dollar amounts, specific issues)\n\nI will draft it in your voice (short sentences, plain English, no fluff). Then you can edit and send.',
      null, 'LOCAL/draft-email');
    // Stash recipient name for the follow-up turn
    window._draftEmailRecipient = recipientName;
    return;
  }

  // 19. Lien deadlines: "lien deadlines from 2026-05-01", "lien calendar 2026-01-15"
  const lienMatch = tl.match(/^(?:lien\s+)?(?:deadlines?|calendar)\s+(?:from\s+)?(\d{4}-\d{2}-\d{2})$/);
  if (lienMatch) {
    const startDate = lienMatch[1];
    const d = new Date(startDate + 'T00:00:00');
    if (isNaN(d.getTime())) {
      appendMsg('ai', 'Invalid date. Use YYYY-MM-DD format.', 'error');
    } else {
      // Texas Property Code Ch. 53 deadlines
      const addDays = (base, n) => { const r = new Date(base); r.setDate(r.getDate() + n); return r.toISOString().split('T')[0]; };
      const addMonths = (base, n) => { const r = new Date(base); r.setMonth(r.getMonth() + n); return r.toISOString().split('T')[0]; };
      let msg = '**Texas Ch. 53 Lien Calendar** (from ' + startDate + ')\n\n';
      msg += '| Deadline | Date | Notes |\n|---|---|---|\n';
      msg += '| Preliminary notice | ' + addDays(d, 15) + ' | 15 days - send to owner + GC |\n';
      msg += '| Monthly notice | ' + addDays(d, 30) + ' | Retainage notice if unpaid |\n';
      msg += '| Lien filing | ' + addMonths(d, 4) + ' | 4 months from last work |\n';
      msg += '| Lien lawsuit | ' + addMonths(d, 6) + ' | 1 year from filing (start prep at 6mo) |\n';
      msg += '| Final deadline | ' + addMonths(d, 16) + ' | 16 months - absolute bar |\n';
      msg += '\n_Dates are calendar days per Texas Property Code Ch. 53. Consult Amber for contract-specific terms._';
      appendMsg('ai', msg, null, 'LOCAL/lien-calc');
    }
    return;
  }

  // 20. New bid: "new bid", "start bid", "create bid"
  if (tl.match(/^(?:new|start|create|begin)\s+bid$/)) {
    if (projectBank.hasContext()) {
      appendMsg('ai', 'Context already loaded (' + projectBank.summary() + '). Type `clear` first if you want a fresh start, or drop a PDF to add to the current bid.', null, 'LOCAL/new-bid');
    } else {
      appendMsg('ai', '**New bid started.** Drop a structural PDF to begin takeoff.\n\nOr type a quick estimate: `bid 65t 38400sf`\n\nAvailable after PDF drop:\n- `generate bid` - full proposal\n- `3d model` - view extracted members\n- `gp report` - internal gross profit report', null, 'LOCAL/new-bid');
    }
    return;
  }

  // 21. Export Tekla XML from current project: "export tekla", "tekla xml"
  if (tl.match(/^(?:export\s+)?tekla(?:\s+xml)?$/)) {
    if (projectBank.members.length === 0) {
      appendMsg('ai', 'No members loaded. Drop a structural PDF first, then `export tekla`.', null, 'LOCAL/tekla');
      return;
    }
    try {
      const membersJson = JSON.stringify(projectBank.members);
      const r = await a.export_tekla_xml(membersJson);
      if (r && r.ok) {
        appendMsg('ai', '**Tekla XML exported:** ' + (r.data.path || r.data.filename || 'saved') + '\n' + (r.data.member_count || projectBank.members.length) + ' members.', null, 'LOCAL/tekla');
      } else {
        appendMsg('ai', 'Tekla export failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Tekla error: ' + e, 'error'); }
    return;
  }

  // 22. Export Strumis XML: "export strumis", "strumis xml"
  if (tl.match(/^(?:export\s+)?strumis(?:\s+xml)?$/)) {
    if (projectBank.members.length === 0) {
      appendMsg('ai', 'No members loaded. Drop a structural PDF first, then `export strumis`.', null, 'LOCAL/strumis');
      return;
    }
    try {
      const membersJson = JSON.stringify(projectBank.members);
      const r = await a.export_strumis_xml(membersJson);
      if (r && r.ok) {
        appendMsg('ai', '**Strumis XML exported:** ' + (r.data.path || r.data.filename || 'saved') + '\n' + (r.data.member_count || projectBank.members.length) + ' members.', null, 'LOCAL/strumis');
      } else {
        appendMsg('ai', 'Strumis export failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Strumis error: ' + e, 'error'); }
    return;
  }

  // 23. Compliance cascade: "cascade N" shorthand for "cascade compliance N"
  if (tl.match(/^cascade\s+(\d+)$/)) {
    const n = tl.match(/^cascade\s+(\d+)$/)[1];
    try {
      const r = await a.cascade_compliance(parseInt(n), 'OPEN', '');
      if (r && r.ok) {
        appendMsg('ai', r.data.message || 'Cascade applied.', null, 'LOCAL/cascade');
      } else {
        appendMsg('ai', 'Cascade failed: ' + (r && r.error || 'no response'), 'error');
      }
    } catch(e) { appendMsg('ai', 'Cascade error: ' + e, 'error'); }
    return;
  }

  // ── END LOCAL METHOD INTERCEPTS ──────────────────────────────

  // ── CONTEXT BANK INTERCEPTS: act on accumulated data without AI ──
  if(projectBank.hasContext()){
    // "generate bid" / "build it" / "run with this" / "lock it in"
    if(tl.match(/^(generate|build|create|make)\s*(the\s*)?(bid|proposal)|^build\s*it|^run\s*with\s*this|^lock\s*it\s*in/)){
      // v6.1.3 safety: if PDFs are still queued for processing, wait for them
      if(_pdfQueue.length > 0){
        appendMsg('ai', 'Still processing ' + _pdfQueue.length + ' file(s). Will generate bid when extraction completes.', null, 'LOCAL/auto-pipeline');
        // Set a flag so processPdfQueue auto-generates after finishing
        window._generateBidAfterQueue = true;
        return;
      }
      const pb = projectBank;
      const est = pb.draftEstimate;
      const proposalCmd = 'Generate the navy/gold PDF proposal for ' + (pb.bidNumber||'new')
        + '. Project: ' + (pb.projectName||'TBD')
        + '. Verified tonnage: ' + pb.tonnage.toFixed(2) + ' tons from AISC database.'
        + ' ' + pb.members.length + ' members extracted.'
        + ' Rough estimate total: $' + (est ? est.total||0 : 0).toLocaleString() + '.'
        + (window._lastInboxContext ? ' From inbox: ' + window._lastInboxContext : '')
        + ' Generate both client PDF and internal GP report. Include standard exclusions.';
      cmd(proposalCmd);
      pb.lastAction = 'bid';
      return;
    }
    // "continue" / "proceed" / "next" = advance to next logical step
    if(tl.match(/^(continue|proceed|next|go|yes)\.?$/)){
      if(projectBank.lastAction === 'takeoff'){
        // After takeoff, continue = generate bid
        cmd('Generate the bid proposal for ' + (projectBank.bidNumber||'') + ' using all accumulated takeoff data. '
          + projectBank.tonnage.toFixed(2) + ' tons, ' + projectBank.members.length + ' members. Generate both PDFs.');
        projectBank.lastAction = 'bid';
        return;
      }
      // Fall through to AI for other states
    }
    // "3d model" / "show model" / "view model"
    if(tl.match(/3d\s*model|show\s*model|view\s*model|view\s*3d/)){
      if(projectBank.stlPaths.length){
        window._projStlPaths = projectBank.stlPaths;
        setMode('model');
        if(typeof loadMultiStlBase64 === 'function') loadMultiStlBase64(projectBank.stlPaths);
        appendMsg('ai', 'Loaded ' + projectBank.stlPaths.length + ' models from ' + (projectBank.projectName||'project') + '.', null, 'LOCAL/3d');
      } else {
        appendMsg('ai', 'No project models loaded yet. Try: `3d model of W14X82 at 20ft` for a standalone view, or drop a structural PDF for full takeoff.', null, 'LOCAL/3d');
      }
      return;
    }
    // "profit report" / "gp report" / "internal report"
    if(tl.match(/profit\s*report|gp\s*report|internal\s*report|gross\s*profit/)){
      cmd('Generate the internal GP report (CONFIDENTIAL) for ' + (projectBank.bidNumber||'')
        + '. ' + (projectBank.projectName||'Project') + '. '
        + projectBank.tonnage.toFixed(2) + ' tons. '
        + (projectBank.draftEstimate ? '$' + projectBank.draftEstimate.total.toLocaleString() + ' total.' : '')
        + ' Ivan to verify. Owner to approve. PDF only.');
      projectBank.lastAction = 'gp_report';
      return;
    }
    // "clear" / "new project" / "reset" = clear the bank
    if(tl.match(/^(clear|reset|new\s*project|start\s*over|fresh)\.?$/)){
      projectBank.clear();
      window._lastPipelineResult = null;
      window._lastTakeoffMembers = null;
      activeProject = null;
      appendMsg('ai', 'Context cleared. Drop a new PDF to start.', null, 'LOCAL');
      return;
    }
  }

  appendMsg('ai','','loading');
  window._lt1=setTimeout(()=>{const l=document.querySelector('.loading-msg');if(l)l.innerHTML='<div class="thinking-msg"><div class="thinking-dots"><span></span><span></span><span></span></div><span class="thinking-label">Analyzing your request...</span></div>';},200);
  window._lt2=setTimeout(()=>{const l=document.querySelector('.loading-msg');if(l){const d=l.querySelector('.thinking-label');if(d)d.textContent='Building what\'s needed...';}},6000);
  window._lt3=setTimeout(()=>{const l=document.querySelector('.loading-msg');if(l){const d=l.querySelector('.thinking-label');if(d)d.textContent='Computing your answer...';}},15000);
  const fp=files.map(f=>({name:f.name,type:f.type,cat:f.cat,data:f.data}));
  try{
    // Direct-route patterns: send raw text so backend direct_route.py can match.
    // If project context is injected first, the enriched string won't match.
    const _DR_PATTERNS = [
      /^bid\s+rates?$/i, /^show\s+(?:me\s+)?rates?$/i,
      /^what\s+are\s+(?:the\s+)?(?:bid\s+)?rates?$/i, /^current\s+rates?$/i,
      /^(?:our|fab|erection|joist|deck|anchor|pricing)\s+rates?$/i,
      /^(?:show\s+)?blockers?$/i, /^compliance(?:\s+(?:status|summary))?$/i,
      /^(?:list\s+|active\s+|show\s+)?bids?$/i,
      /^\s*self[\s-]?test\s*[?.!]?\s*$/i,
      /^\s*morning[\s-]?brief(?:ing)?\s*[?.!]?\s*$/i,
      /^\s*(?:ar[\s-]?aging|aging|receivables[\s-]?aging)\s*[?.!]?\s*$/i,
      /^\s*shop\s+kpis?\s*[?.!]?\s*$/i,
      /^\s*(?:market|market[\s-]dashboard)\s*[?.!]?\s*$/i,
      /^\s*help\s*[?.!]?\s*$/i,
      /^\s*(?:stock[\s-]?watchlist|watchlist|stocks)\s*[?.!]?\s*$/i,
    ];
    const _isDirectRoute = !!(text && _DR_PATTERNS.some(p => p.test(text.trim())));
    // Inject active project context so the AI knows what's being worked on
    let enrichedText = text||'Analyze the attached file(s).';
    // v6.1.2: inject accumulated context bank (not just last pipeline result)
    if(projectBank.hasContext()){
      enrichedText += projectBank.contextForAI();
      const ib = window._lastInboxContext || '';
      enrichedText += ' RULES: (1) Search Owner\'s Outlook (mailboxOwnerEmail=owner@yourcompany.example.com)'
        + ' for email chains before asking clarifying questions.'
        + ' (2) Run web searches via Gemini for public project info.'
        + ' (3) After searching, ask for missing info AT MOST ONCE.'
        + ' (4) Always offer a "generate as-is" option alongside any clarifying question.'
        + ' (5) When user says "yes", "proceed", or "generate", act immediately with available data.'
        + ' Flag assumptions at the bottom, do not block on missing info.'
        + (ib ? ' From inbox search: ' + ib : '');
    } else if(activeProject && window._lastPipelineResult){
      const p = window._lastPipelineResult;
      const ib = window._lastInboxContext || '';
      const ctx = ' [CONTEXT: Active project ' + (p.bid_number||'') + ' "'
        + (p.project_name||activeProject) + '", '
        + (p.total_tonnage||0) + ' tons verified from AISC, '
        + (p.member_count||0) + ' members extracted.'
        + (ib ? ' From inbox search: ' + ib : '')
        + ']';
      enrichedText += ctx;
    }
    const r=await a.ai_ask(_isDirectRoute?text:enrichedText,voice,history.slice(-10),fp.length?fp:null);
    removeLoading();
    if(r.ok){
      const d=r.data;
      const prov=(d.provider||'claude').toUpperCase();
      const mdl=(d.model||'').split('/').pop();
      const xb=document.getElementById('xlate-bar');
      if(d.translated){
        document.getElementById('xlate-from').textContent='"'+(d.original||'').substring(0,40)+'"';
        document.getElementById('xlate-to').textContent=(d.expanded||'').substring(0,60)+'...';
        xb.classList.add('show');setTimeout(()=>xb.classList.remove('show'),8000);
      }else xb.classList.remove('show');
      appendMsg('ai',d.text,null,prov+'/'+mdl);
      history.push({role:'assistant',content:d.text});
      // Auto-display 3D model if response contains STL data
      if(d.view_3d && d.view_3d.stl_b64){
        try{ loadStlBase64(d.view_3d.stl_b64, d.view_3d.label); }
        catch(e3d){ console.warn('3D viewer error:', e3d); }
      }
      document.getElementById('active-model').textContent=prov+' · '+mdl.toUpperCase();
      updateFB(prov,mdl);
      const calcs=d.calcs_run;const steps=d.pipeline_steps;const tok=d.input_tokens?(d.input_tokens+d.output_tokens):'';
      document.getElementById('token-note').textContent=
        prov.toLowerCase()+'/'+mdl+' · '+(calcs?'T1-1: '+calcs.join(', ')+' · ':'')
        +(steps?steps.length+' steps · ':'')+(tok?tok+' tokens · ':'')+'20 rules · Enter to send · Ctrl+K palette';
    }else appendMsg('ai',r.error,'error');
  }catch(e){removeLoading();appendMsg('ai','Error: '+e.message,'error');}
}

function appendMsg(role,text,type,route,rawHtml){
  const b=document.getElementById('messages');
  const d=document.createElement('div');d.className='msg '+role;
  if(type==='loading')d.classList.add('loading-msg');
  if(type==='error')d.style.cssText='border-color:var(--red);color:var(--red);';
  // rawHtml=true: text is already HTML (project card, rich display)
  if(rawHtml){d.innerHTML=text;}
  else{d.innerHTML=text.replace(/\n/g,'<br>');}
  // Timestamp + copy button (on AI messages)
  if(type!=='loading'){
    const meta=document.createElement('div');meta.className='msg-meta';
    const now=new Date();const pad=n=>String(n).padStart(2,'0');
    const ts=pad(now.getHours())+':'+pad(now.getMinutes());
    meta.innerHTML='<span class="msg-time">'+ts+'</span>';
    if(role==='ai'&&type!=='error'){
      const cpBtn=document.createElement('button');cpBtn.className='msg-copy';cpBtn.textContent='COPY';
      cpBtn.onclick=function(){
        navigator.clipboard.writeText(text).then(()=>{cpBtn.textContent='COPIED';cpBtn.classList.add('copied');setTimeout(()=>{cpBtn.textContent='COPY';cpBtn.classList.remove('copied');},1500);}).catch(()=>{});
      };
      meta.appendChild(cpBtn);
      // Regenerate button
      const regenBtn=document.createElement('button');regenBtn.className='msg-act-btn';regenBtn.textContent='↻ RETRY';
      regenBtn.onclick=function(){
        const lastUser=history.filter(h=>h.role==='user').pop();
        if(lastUser)sendMessage(lastUser.content);
      };
      meta.appendChild(regenBtn);
    }
    if(route){meta.innerHTML='<span class="live-dot msg-time">'+route+' · '+ts+'</span>'+meta.innerHTML.replace(/<span class="msg-time">.*?<\/span>/,'');}
    d.appendChild(meta);
  }
  b.appendChild(d);b.scrollTop=b.scrollHeight;
}
function removeLoading(){clearTimeout(window._lt1);clearTimeout(window._lt2);clearTimeout(window._lt3);const l=document.querySelector('.loading-msg');if(l)l.remove();}
function handleKey(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}
  const t=e.target;setTimeout(()=>{t.style.height='auto';t.style.height=Math.min(t.scrollHeight,120)+'px';},0);
}
function cmd(c){setMode('chat');sendMessage(c);}

// ── VOICE INPUT ──────────────────────────────────────────────────
let _r=null,_va=false;
function startVoice(e){if(e)e.preventDefault();
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){appendMsg('ai','Voice not supported. Use Chrome/Edge.','error');return;}
  document.getElementById('mic-btn').classList.add('recording');
  _r=new SR();_r.lang='en-US';_r.interimResults=false;_r.maxAlternatives=1;
  _r.onresult=ev=>{const t=ev.results[0][0].transcript;const i=document.getElementById('chat-input');if(i)i.value=t;setTimeout(sendMessage,200);};
  _r.onerror=ev=>{if(ev.error!=='no-speech')appendMsg('ai','Voice error: '+ev.error,'error');stopVoice();};
  _r.onend=stopVoice;_va=true;try{_r.start();}catch(e){}
}
function stopVoice(){document.getElementById('mic-btn').classList.remove('recording');if(_r&&_va){_va=false;try{_r.stop();}catch(e){}}}

// ── FALLBACK BANNER ──────────────────────────────────────────────
function updateFB(prov,mdl){
  const b=document.getElementById('fallback-bar');const t=document.getElementById('fallback-txt');if(!b||!t)return;
  const s=(prov+' '+(mdl||'')).toLowerCase();
  const isFB=s.includes('fallback'),isG=prov==='gemini'||s.includes('gemini'),isO=prov==='openai'||s.includes('gpt');
  if(isFB||(isG&&!s.includes('pipeline'))){
    const eng=isG?'GEMINI 2.5':isO?'GPT-4o':prov.toUpperCase();
    t.textContent='⚠ FALLBACK: '+eng+' ANSWERING · Claude unreachable · Voice rules differ · Review output carefully';
    b.classList.add('on');
  }else b.classList.remove('on');
}

// ── SMS STATUS ───────────────────────────────────────────────────
async function loadSmsStatus(){
  try{
    const a=api();if(!a)return;
    const r=await a.get_sms_status();const d=r.data||r;
    const el=document.getElementById('ch-sms');if(!el)return; // moved to settings
    if(d.configured){el.textContent=d.twilio_number||'ACTIVE';el.className='sms-val sms-ok';}
    else{el.textContent='NOT SET';el.className='sms-val sms-no';}
  }catch(e){}
}

// ── CALL JOSEPH ───────────────────────────────────────────────────
async function callJoseph(){
  const fr = document.getElementById('fresp');
  const a = api();
  if(a){
    try{
      const r = await a.get_sms_status();
      if(r && r.ok && r.data && !r.data.configured){
        if(fr) fr.textContent = 'Twilio not configured - opening device phone app';
      }
    }catch(e){}
  }
  window.open('tel:7139384333');
}

// ── BID SCANNER ──────────────────────────────────────────────────
async function scanBids(){
  setMode('chat');
  const a=api();if(!a){appendMsg('ai','Bridge not connected','error');return;}
  appendMsg('ai','Scanning inbox for bid leads...','loading');
  try{
    const TIMEOUT_MS=10000;
    const scanPromise=a.scan_bids();
    const timeoutPromise=new Promise((_,rej)=>setTimeout(()=>rej(new Error('scan timeout')),TIMEOUT_MS));
    const r=await Promise.race([scanPromise,timeoutPromise]);
    removeLoading();
    if(!r||!r.ok){
      const errMsg=r&&r.error||'unknown error';
      if(errMsg.toLowerCase().includes('not configured')||errMsg.toLowerCase().includes('gmail')||errMsg.toLowerCase().includes('credential')){
        appendMsg('ai','Scan not configured. Set up Gmail credentials in SETTINGS to enable inbox scanning.','error');
      }else{
        appendMsg('ai','Scan error: '+errMsg,'error');
      }
      return;
    }
    const leads=Array.isArray(r.data)?r.data:(r.data&&r.data.leads||[]);
    if(!leads.length){
      appendMsg('ai','No qualifying leads found. All messages were PEMB, out-of-scope, or below threshold.');
      return;
    }
    renderLeads(r.data);
  }catch(e){
    removeLoading();
    if(e.message==='scan timeout'){
      appendMsg('ai','Bid scan timed out after 10 seconds. Gmail may be slow. Try again or check SETTINGS.','error');
    }else{
      appendMsg('ai','Scan error: '+e.message,'error');
    }
  }
}
function renderLeads(data){
  const leads=Array.isArray(data)?data:(data.leads||[]);
  if(!leads.length){appendMsg('ai','No qualifying leads found. All PEMB/out-of-scope or below threshold.');return;}
  const hi=leads.filter(l=>l.tier==='HIGH'),me=leads.filter(l=>l.tier==='MEDIUM');
  let o='BID SCAN RESULTS\n\n';
  if(hi.length){o+='HIGH ('+hi.length+'):\n';hi.forEach(l=>{o+='• '+l.subject+' | '+l.score+'/100\n';if(l.reasons)o+='  '+l.reasons.slice(0,3).join(' · ')+'\n';});}
  if(me.length){o+='\nMEDIUM ('+me.length+'):\n';me.slice(0,3).forEach(l=>{o+='• '+l.subject+' | '+l.score+'/100\n';});}
  anim(document.getElementById('k-bids'),leads.filter(l=>l.tier!=='LOW').length,'','');
  appendMsg('ai',o.trim());
}

// ── VM BID DISCOVERY ─────────────────────────────────────────────
function formatDiscoveryName(raw){
  if(!raw)return'Unnamed Lead';
  return raw
    .replace(/_/g,' ')
    .replace(/\s+NANO\s+CUBE\s+USA.*/i,'')
    .replace(/\s+INTERNAL.*/i,'')
    .replace(/\s+\(2\)$/,'')
    .replace(/\s+2$/,' (2)')
    .replace(/\s{2,}/g,' ')
    .trim()||'Unnamed Lead';
}

async function loadDiscoveryCards(){
  const a=api();if(!a)return;
  try{
    const r=await a.vm_discovery_cards(6);
    if(r.ok&&r.data&&r.data.cards)renderDiscoveryCards(r.data.cards);
  }catch(e){console.log('Discovery cards load:',e.message);}
}

function renderDiscoveryCards(cards){
  const grid=document.getElementById('sv-bid-cards');
  if(!grid)return;
  // Keep the scan button, clear everything else
  const scanBtn=grid.querySelector('.sv-bcard-scan');
  grid.innerHTML='';
  if(!cards.length){
    if(scanBtn)grid.appendChild(scanBtn);
    return;
  }
  cards.forEach(c=>{
    const tierClass=c.vm_tier==='HIGH'?'sv-bcard-high':c.vm_tier==='MEDIUM'?'sv-bcard-med':'';
    const tierBadge=c.vm_tier==='HIGH'?'sv-tier-high':c.vm_tier==='MEDIUM'?'sv-tier-med':'sv-tier-low';
    const reasons=(c.vm_reasons||[]).slice(0,3).map(r=>'+ '+r).join(' ');
    const flags=(c.vm_flags||[]).slice(0,2).map(f=>'- '+f).join(' ');
    const hints=[reasons,flags].filter(Boolean).join(' ');
    const dl=c.deadline?'Due: '+c.deadline:'';
    const rawVal=parseFloat(c.estimated_value)||0;
    const val=rawVal>0?'~$'+rawVal.toLocaleString('en-US',{maximumFractionDigits:0}):'';
    const sub=[c.gc_company,c.location,val].filter(Boolean).join(' . ');
    const displayName=formatDiscoveryName(c.subject||c.project_name||'');

    const card=document.createElement('div');
    card.className='sv-bcard '+tierClass;
    card.innerHTML=
      '<div class="sv-bt"><span class="sv-tier-badge '+tierBadge+'">'+c.vm_tier+'</span> '+c.vm_score+'/100</div>'+
      '<div class="sv-bn">'+esc(displayName)+'</div>'+
      '<div class="sv-bs">'+esc(sub)+'</div>'+
      (hints?'<div class="sv-bw">'+esc(hints)+'</div>':'')+
      (dl?'<div class="sv-bd-deadline">'+esc(dl)+'</div>':'')+
      '<div class="sv-bd-actions">'+
        '<button class="sv-bd-abtn" onclick="event.stopPropagation();startEstimating('+JSON.stringify(JSON.stringify(c))+')">START ESTIMATING</button>'+
        '<button class="sv-bd-abtn sv-bd-abtn-pass" onclick="event.stopPropagation();passBid(\''+esc(c.id||'')+'\')">PASS</button>'+
      '</div>';
    card.onclick=function(){cmd('Tell me more about the bid: '+c.subject+'. Score: '+c.vm_score+'/100. '+c.vm_recommendation);setMode('chat');};
    grid.appendChild(card);
  });
  if(scanBtn)grid.appendChild(scanBtn);
  // Update status badge
  const st=document.getElementById('bd-status');
  if(st)st.textContent=cards.length+' lead'+(cards.length!==1?'s':'')+' found';
}

async function runVmDiscovery(){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  showToast('VM scanning inbox...','info',3000);
  const st=document.getElementById('bd-status');
  if(st)st.textContent='scanning...';
  try{
    const r=await a.vm_discover_bids(3);
    if(r.ok&&r.data){
      renderDiscoveryCards(r.data.leads||[]);
      const s=r.data.stats||{};
      showToast('Scan complete: '+s.qualified+' qualified leads','success',3000);
      if(st)st.textContent=(s.qualified||0)+' qualified of '+(s.total_scanned||0)+' scanned';
      // Also render in chat if user wants detail
      if(r.data.leads&&r.data.leads.length)renderLeads(r.data.leads.map(l=>({subject:l.subject,score:l.vm_score,tier:l.vm_tier,reasons:l.vm_reasons})));
    }else{
      showToast('Scan returned no results','info',2000);
      if(st)st.textContent='no leads';
    }
  }catch(e){
    showToast('Scan error: '+e.message,'error');
    if(st)st.textContent='scan failed';
  }
}

async function startEstimating(bidInfoJson){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  setMode('chat');
  appendMsg('ai','Creating project folder...','loading');
  try{
    const r=await a.vm_start_estimating(bidInfoJson);removeLoading();
    if(r.ok&&r.data){
      const d=r.data;
      let msg='PROJECT FOLDER CREATED\n\n';
      msg+='Bid Number: '+d.bid_number+'\n';
      msg+='Folder: '+d.folder_path+'\n\n';
      if(d.download_links&&d.download_links.length){
        msg+='DOWNLOAD LINKS FOUND:\n';
        d.download_links.forEach(l=>{msg+='  ['+l.source+'] '+l.url+'\n';});
        msg+='\nDownload the structural drawings from the link above.\n';
      }
      msg+='Then drop the PDF files into this chat.\n';
      msg+='You can also paste screenshots or type project notes.\n';
      msg+='Everything gets saved to the project folder.';
      appendMsg('ai',msg);
    }else{
      appendMsg('ai','Folder creation failed: '+(r.error||'unknown'),'error');
    }
  }catch(e){removeLoading();appendMsg('ai','Error: '+e.message,'error');}
}

async function passBid(bidId){
  if(!bidId)return;
  showToast('Bid passed','info',1500);
  // Remove card from display
  loadDiscoveryCards();
}

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// ── EXTRAS (left sidebar more actions) ───────────────────────────
const ALL_QA=[
  {l:'Morning Briefing',c:'ADMIN',t:'Build and send the morning briefing to Owner'},
  {l:'Steel Research',c:'RESEARCH',t:'Research current structural steel market conditions and pricing trends'},
  {l:'3D Model',c:'FAB',t:null}, // Dynamic: uses active project context
  {l:'DXF Section',c:'FAB',t:'Generate a DXF cross-section drawing for W12x35'},
  {l:'Monte Carlo',c:'FINANCE',t:'Run a Monte Carlo simulation: ICD Church 1500 tons, $3750 fab, $970 erection, 15% cost variance'},
  {l:'Weekly Briefing',c:'ADMIN',t:'Generate full weekly operations briefing for Your Company'},
  {l:'Ironworker Schedule',c:'FAB',t:'Generate an ironworker punch schedule for standard connections'},
];
let extOpen=false;
function populateExtras(){
  const a=document.getElementById('extras-a'),b=document.getElementById('extras-b');if(!a||!b)return;
  ALL_QA.slice(0,3).forEach(q=>{
    const x=document.createElement('button');x.className='extra-btn';
    x.innerHTML=q.l+'<span class="ec">'+q.c+'</span>';
    if(q.t===null && q.l==='3D Model'){
      // Dynamic: model the active project, or prompt to drop a PDF
      x.onclick=()=>{
        if(activeProject){
          cmd('Generate a 3D STL model for the active project '+activeProject+'. Use the verified takeoff data from the pipeline.');
          setMode('model');
        } else if(window._lastBidNumber){
          setMode('model');
          loadBidIntoModel(window._lastBidNumber,'');
        } else {
          setMode('model');
          showToast('Drop a structural PDF to generate a 3D model.','info',3000);
        }
      };
    } else {
      x.onclick=()=>cmd(q.t);
    }
    a.appendChild(x);
  });
  ALL_QA.slice(3).forEach(q=>{const x=document.createElement('button');x.className='extra-btn';x.innerHTML=q.l+'<span class="ec">'+q.c+'</span>';x.onclick=()=>cmd(q.t);b.appendChild(x);});
}
function toggleExtras(){extOpen=!extOpen;document.getElementById('extras-b').classList.toggle('on',extOpen);document.getElementById('more-btn').textContent=extOpen?'− Show fewer':'+ Show all actions';}

// ── STATUS DATE HEADER ───────────────────────────────────────────
function updateStatusDate() {
  const now = new Date(new Date().toLocaleString('en-US',{timeZone:'America/Chicago'}));
  const days = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const d = document.getElementById('sv-day');
  const t = document.getElementById('sv-time-lbl');
  const w = document.getElementById('welcome-date');
  const pad = n => String(n).padStart(2,'0');
  const dayStr = days[now.getDay()]+', '+months[now.getMonth()]+' '+now.getDate();
  const timeStr = pad(now.getHours())+':'+pad(now.getMinutes())+' CST';
  if(d) d.textContent = dayStr;
  if(t) t.textContent = timeStr + ' · YOUR COMPANY VIRTUAL OFFICE';
  if(w) w.textContent = dayStr + ' · ' + timeStr;
}
setInterval(updateStatusDate, 30000); updateStatusDate();

// ── TOAST NOTIFICATION SYSTEM ────────────────────────────────────
function showToast(msg, type='info', duration=3000) {
  const c = document.getElementById('toasts');
  if(!c) return;
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(()=>{t.classList.add('exiting');setTimeout(()=>t.remove(),200);}, duration);
}

// ── PRINT STATUS ─────────────────────────────────────────────────
function printStatus() { window.print(); showToast('Print dialog opened','info',1500); }

// ── COPY STATUS TO CLIPBOARD ─────────────────────────────────────
function copyStatus() {
  const el = document.getElementById('v-status');
  if(!el) return;
  navigator.clipboard.writeText(el.innerText).then(()=>{
    showToast('Status copied to clipboard','success',2000);
  }).catch(()=>showToast('Copy failed','error',2000));
}

// ── PROJECT BRIEF (P22.1: local display, zero LLM tokens) ───────
function showProjectBrief(name, status, detail) {
  const msg = '**' + name + '**\n\nStatus: ' + status + '\n' + detail
    + '\n\nType a question in chat for more details.';
  appendMsg('ai', msg, null, 'LOCAL/project-brief');
  setMode('chat');
}

// ── REFRESH STATUS ───────────────────────────────────────────────
function refreshStatus() {
  showToast('Refreshing data...','info',1500);
  init().catch(()=>showToast('Refresh failed','error',2000));
  loadDiscoveryCards();
}

// ── LAST SENT TRACKING ───────────────────────────────────────────
let _lastBriefingSent = null;
function updateLastSent() {
  const els = document.querySelectorAll('.last-sent');
  if(!_lastBriefingSent) return;
  const pad = n => String(n).padStart(2,'0');
  const ts = pad(_lastBriefingSent.getHours())+':'+pad(_lastBriefingSent.getMinutes());
  els.forEach(el => el.textContent = 'Last sent: '+ts);
}

// ── KPI BLOCKERS PULSE ───────────────────────────────────────────
function setBlockerKpiPulse(hasEscalated) {
  const el = document.getElementById('k-blk');
  if(el) el.classList.toggle('escalated', hasEscalated);
}
// Any blocker open 14+ days → escalated. EMR = 28 days → always escalated.
setBlockerKpiPulse(true); // known at boot: EMR is 28d

// ── FIELD TILE DIM / RESET ───────────────────────────────────────
function resetFieldTiles() {
  document.querySelectorAll('.ftile').forEach(t=>t.classList.remove('dimmed'));
  const fr = document.getElementById('fresp');
  if(fr){fr.textContent='TAP A TILE OR HOLD THE MIC TO SPEAK';fr.className='field-resp';}
}

// ── FIELD ACTION ─────────────────────────────────────────────────
function fieldAct(c, tileId) {
  // Dim all tiles except the tapped one
  document.querySelectorAll('.ftile').forEach(t=>{
    t.classList.toggle('dimmed', tileId && t.id !== tileId);
  });
  const fr = document.getElementById('fresp');
  fr.className = 'field-resp active'; fr.textContent = 'Fetching...';
  const a = api();
  if(!a){fr.textContent='Bridge not connected.';return;}
  // v3.5.7: 60s timeout. Without this, "Fetching..." sticks forever if
  // ai_ask hangs (e.g., upstream API key issue, network stall, dead loop).
  // Joseph's screenshot showed exactly that hang state.
  const timeout = new Promise((_, rej) => setTimeout(() =>
    rej(new Error('Field request timed out after 60s. Try again or switch to Chat mode for a longer wait.')), 60000));
  Promise.race([a.ai_ask(c,'owner',history.slice(-4),null), timeout]).then(r=>{
    document.querySelectorAll('.ftile').forEach(t=>t.classList.remove('dimmed'));
    if(r.ok){fr.textContent=r.data.text;history.push({role:'user',content:c},{role:'assistant',content:r.data.text});}
    else if(r.error&&/no api key|api key|no.*key/i.test(r.error)){fieldLocalFallback(tileId,fr);}
    else fr.textContent='Error: '+r.error;
  }).catch(e=>{
    document.querySelectorAll('.ftile').forEach(t=>t.classList.remove('dimmed'));
    fr.textContent='Error: '+e.message;
  });
}

function fieldUrgent() {
  const fr = document.getElementById('fresp');
  const a = api();
  document.querySelectorAll('.ftile').forEach(t => t.classList.toggle('dimmed', t.id !== 'ft-urgent'));
  fr.className = 'field-resp active'; fr.textContent = 'Fetching...';
  if (!a) { fr.textContent = 'Bridge not connected.'; return; }
  const timeout = new Promise((_, rej) => setTimeout(() =>
    rej(new Error('Field request timed out after 60s.')), 60000));
  Promise.race([a.field_urgent_ask(history.slice(-4)), timeout]).then(r => {
    document.querySelectorAll('.ftile').forEach(t => t.classList.remove('dimmed'));
    if (r.ok) { fr.textContent = r.data.text; history.push({role:'user',content:'What is urgent?'},{role:'assistant',content:r.data.text}); }
    else if (r.error && /no api key|api key|no.*key/i.test(r.error)) { fieldLocalFallback('ft-urgent', fr); }
    else fr.textContent = 'Error: ' + r.error;
  }).catch(e => {
    document.querySelectorAll('.ftile').forEach(t => t.classList.remove('dimmed'));
    fr.textContent = 'Error: ' + e.message;
  });
}

async function fieldLocalFallback(tileId, fr){
  const a=api();if(!a){fr.textContent='Bridge not connected. Add API key in Settings.';return;}
  try{
    if(!tileId||/urgent|status/i.test(tileId)){
      const r=await a.get_blockers();
      if(r.ok&&r.data){
        const bl=(r.data.blockers||r.data||[]);
        if(Array.isArray(bl)&&bl.length){
          fr.textContent='No AI key. Blockers:\n'+bl.slice(0,5).map(b=>'- '+(b.title||b.description||b)).join('\n');
        } else {
          fr.textContent='No blockers found. Add API key in Settings > API Keys.';
        }
      } else {
        fr.textContent='AI unavailable. Add API key in Settings > API Keys.';
      }
    } else {
      fr.textContent='AI unavailable. Add API key in Settings > API Keys.';
    }
  }catch(e){fr.textContent='AI unavailable. Add API key in Settings > API Keys.';}
}

// ── FIELD VOICE (with response in middle area) ─────────────────
let _fr=null,_fva=false;
function startFVoice(e){if(e)e.preventDefault();
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR)return;
  document.getElementById('fmic').classList.add('recording');
  _fr=new SR();_fr.lang='en-US';_fr.interimResults=false;
  _fr.onresult=async ev=>{
    const t=ev.results[0][0].transcript;
    const fr=document.getElementById('fresp');fr.className='field-resp active';fr.textContent='Processing: '+t+'...';
    const a=api();if(!a){fr.textContent='Bridge not connected.';return;}
    // v3.5.7: same 60s timeout pattern as fieldAct.
    const timeout = new Promise((_, rej) => setTimeout(() =>
      rej(new Error('Voice request timed out after 60s. Try again.')), 60000));
    try{
      const r = await Promise.race([a.ai_ask(t,'owner',history.slice(-4),null), timeout]);
      if(r.ok){fr.textContent=r.data.text;history.push({role:'user',content:t},{role:'assistant',content:r.data.text});}
      else fr.textContent='Error: '+r.error;
    } catch(e) { fr.textContent='Error: '+e.message; }
  };
  _fr.onerror=()=>stopFVoice();_fr.onend=stopFVoice;_fva=true;try{_fr.start();}catch(e){}
}
function stopFVoice(){document.getElementById('fmic').classList.remove('recording');if(_fr&&_fva){_fva=false;try{_fr.stop();}catch(e){}}}

// ── COMMAND PALETTE ──────────────────────────────────────────────
const PAL_CMDS=[
  {i:icon('compliance'),t:'Compliance Status',c:'ADMIN',x:'Show current compliance status, all blockers, what needs Owner today'},
  {i:icon('search'),t:'Scan Bid Inbox',c:'BIDS',x:'Scan email inbox for bid leads'},
  {i:icon('email'),t:'Draft Cold Email',c:'OUTREACH',x:'Draft a cold outreach email to a GC for structural steel fab and erection in Texas. Owner voice.'},
  {i:icon('chat'),t:'ICD Church Status',c:'PROJECTS',x:'What is the current status of the ICD Church project in Spring TX? Quantum meruit update?'},
  {i:icon('factory'),t:'AFR Brownsville Status',c:'PROJECTS',x:'What is the status on the America First Refining Brownsville SOQ? Any updates since April 24 submission?'},
  {i:icon('factory'),t:'Marathon Petroleum Status',c:'PROJECTS',x:'What is blocking the Marathon Petroleum ISN submission and what is the exact next step?'},
  {i:icon('briefing'),t:'Morning Briefing',c:'ADMIN',x:'Build and send the morning briefing to Owner'},
  {i:icon('research'),t:'Steel Market Research',c:'RESEARCH',x:'Research current structural steel pricing and market conditions'},
  {i:icon('weight'),t:'Weight Calculator',c:'CALC',x:'Calculate weight for 10 W12x35 beams at 30 feet'},
  {i:icon('wrench'),t:'Test Connections',c:'SYSTEM',x:'Test all API connections and report status'},
  {i:icon('phone'),t:'Send SMS Briefing',c:'SYSTEM',x:'Send the morning briefing SMS to Owner now'},
  {i:icon('field'),t:'Field Mode',c:'VIEW',a:()=>setMode('field')},
  {i:icon('settings'),t:'Settings',c:'SYSTEM',a:()=>setMode('settings')},
  {i:icon('status'),t:'Status View',c:'VIEW',a:()=>setMode('status')},
  {i:icon('chat'),t:'Chat Mode',c:'VIEW',a:()=>setMode('chat')},
];
let _ps=0,_pf=[...PAL_CMDS];
function openPal(){
  document.getElementById('palette').classList.add('on');
  const i=document.getElementById('pal-inp');i.value='';_pf=[...PAL_CMDS];_ps=0;renderPal();
  setTimeout(()=>i.focus(),50);
}
function closePal(){document.getElementById('palette').classList.remove('on');}
function filterPal(q){const l=q.toLowerCase();_pf=q?PAL_CMDS.filter(c=>c.t.toLowerCase().includes(l)||c.c.toLowerCase().includes(l)):[...PAL_CMDS];_ps=0;renderPal();}
function renderPal(){
  const li=document.getElementById('pal-list');
  if(!_pf.length){li.innerHTML='<div class="pal-empty">No commands match</div>';return;}
  li.innerHTML=_pf.map((c,i)=>`<div class="pal-item${i===_ps?' sel':''}" onclick="runPal(${i})"><span class="pi-ic">${c.i}</span><span class="pi-tx">${c.t}</span><span class="pi-ca">${c.c}</span></div>`).join('');
}
function runPal(i){const c=_pf[i];if(!c)return;closePal();if(c.a)c.a();else cmd(c.x);}
function palKey(e){
  if(e.key==='Escape'){closePal();return;}
  if(e.key==='ArrowDown'){_ps=Math.min(_ps+1,_pf.length-1);renderPal();}
  else if(e.key==='ArrowUp'){_ps=Math.max(_ps-1,0);renderPal();}
  else if(e.key==='Enter'){e.preventDefault();runPal(_ps);}
}
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();openPal();}
  if(e.key==='Escape'){closePal(); closeShortcutHelp();}
  // ── v3.2 Power-user shortcuts (work even when typing) ─────────
  if(e.ctrlKey||e.metaKey){
    // Ctrl+B → generate bid (sends to chat input as if user typed it)
    if(e.key==='b' || e.key==='B'){
      e.preventDefault();
      sendMessage('generate bid for current project');
    }
    // Ctrl+M → morning brief
    else if(e.key==='m' || e.key==='M'){
      e.preventDefault();
      sendMessage('morning brief');
    }
    // Ctrl+R → run self-test (gentler than browser refresh - no page reload)
    else if(e.key==='r' || e.key==='R'){
      e.preventDefault();
      runSelfTestShortcut();
    }
    // Ctrl+/ → shortcut help overlay
    else if(e.key==='/' || e.key==='?'){
      e.preventDefault();
      showShortcutHelp();
    }
  }
  // Mode shortcuts: 1=STATUS, 2=CHAT, 3=FIELD, 4=MODEL, 5=SETTINGS, 6=CONTROLS (only when not typing)
  const tag = (e.target.tagName||'').toLowerCase();
  if(tag!=='input'&&tag!=='textarea'){
    if(e.key==='1')setMode('status');
    if(e.key==='2')setMode('chat');
    if(e.key==='3')setMode('field');
    if(e.key==='4'){setMode('model');refreshBidList();}
    if(e.key==='5')setMode('settings');
    if(e.key==='6')setMode('controls');
  }
});

// ── v3.2 Keyboard shortcut helpers ─────────────────────────────────
async function runSelfTestShortcut(){
  const a = api(); if(!a){showToast('Bridge not connected','error');return;}
  setMode('chat');
  appendMsg('ai', 'Running self-test across all subsystems...', null, 'DIAGNOSTIC');
  try {
    const r = await a.run_self_test();
    const d = r.data || r;
    if(d.passed != null){
      const pct = d.health_pct || (d.passed/Math.max(d.total,1)*100).toFixed(1);
      appendMsg('ai', `Self-test complete · ${d.passed}/${d.total} passed (${pct}%)`, null, 'DIAGNOSTIC');
      showToast(`Self-test: ${d.passed}/${d.total} (${pct}%)`,'success',3500);
    }
  } catch(e){ showToast('Self-test failed: '+e.message,'error',4000); }
}

function showShortcutHelp(){
  if(document.getElementById('sh-overlay'))return;
  const ov = document.createElement('div');
  ov.id = 'sh-overlay';
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.82);z-index:9998;display:flex;align-items:center;justify-content:center;';
  ov.innerHTML = `
    <div style="background:var(--c3);border:1px solid var(--molten);border-radius:12px;padding:28px 32px;max-width:480px;width:90%;box-shadow:0 24px 80px rgba(255,95,0,0.15);">
      <div style="font:700 11px var(--mono);color:var(--molten);letter-spacing:2px;margin-bottom:6px;">KEYBOARD SHORTCUTS</div>
      <div style="font:900 22px var(--disp);letter-spacing:2px;margin-bottom:18px;text-transform:uppercase;color:var(--text);">Power User Keys</div>
      <table style="width:100%;font:400 13px var(--body);color:var(--tm);border-collapse:collapse;">
        <tr><td style="padding:7px 0;width:130px;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Ctrl+K</kbd></td><td>Command palette (15 quick actions)</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Ctrl+B</kbd></td><td>Generate bid for current project</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Ctrl+M</kbd></td><td>Run morning briefing now</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Ctrl+R</kbd></td><td>Run 67-check self-test</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Ctrl+/</kbd></td><td>Show this help (Esc to close)</td></tr>
        <tr><td colspan="2" style="padding:14px 0 4px 0;font:700 10px var(--mono);color:var(--molten);letter-spacing:1.5px;">TAB SWITCHES (when not typing)</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">1 - 6</kbd></td><td>Status / Chat / Field / Model / Settings / Controls</td></tr>
        <tr><td style="padding:7px 0;"><kbd style="background:var(--c5);border:1px solid var(--lineb);border-radius:4px;padding:2px 8px;font:600 11px var(--mono);color:var(--molten);">Esc</kbd></td><td>Close palette / overlay</td></tr>
      </table>
      <div style="text-align:right;margin-top:18px;">
        <button onclick="closeShortcutHelp()" style="padding:8px 20px;border-radius:6px;border:none;background:var(--molten);color:#000;font:700 12px var(--body);cursor:pointer;letter-spacing:1px;">CLOSE</button>
      </div>
    </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if(e.target===ov) closeShortcutHelp(); });
}

function closeShortcutHelp(){
  const ov = document.getElementById('sh-overlay');
  if(ov) ov.remove();
}

// ── MORNING BRIEFING + WEBHOOK + DIAGNOSTICS ─────────────────────
async function sendMorningBriefingNow(){
  try{
    const a=api();if(!a){showToast('Bridge not connected','error');return;}
    showToast('Sending morning briefing...','info',2000);
    const r=await a.send_morning_briefing_now();const d=r.data||r;
    _lastBriefingSent=new Date();updateLastSent();
    showToast('Morning briefing sent to Owner','success',3000);
    if(document.getElementById('shell').dataset.mode==='chat')appendMsg('ai','Morning briefing:\n\n'+(d.briefing||''));
  }catch(e){showToast('Briefing error: '+e.message,'error');}
}
async function startWebhook(){
  const a=api();if(!a)return;setMode('chat');
  appendMsg('ai','Starting webhook server on port 7750...','loading');
  try{const r=await a.start_webhook();removeLoading();if(r.ok)appendMsg('ai','Webhook running at http://localhost:7750\nFor external access, start Cloudflare tunnel.');else appendMsg('ai','Error: '+r.error,'error');}
  catch(e){removeLoading();appendMsg('ai','Error: '+e.message,'error');}
}
async function runDiagnostics(){
  setMode('chat');appendMsg('ai','Running connection diagnostics...','loading');
  try{
    const a=api();if(!a){removeLoading();appendMsg('ai','Not running in pywebview.','error');return;}
    const r=await a.test_connection();removeLoading();
    if(r.ok){
      const d=r.data;
      let o='CONNECTION DIAGNOSTICS\n\n';
      // Backend returns d.Claude, d.Gemini, d.OpenAI objects with .status and .error
      [{label:'Claude (Anthropic)',key:'Claude'},{label:'Gemini (Google)',key:'Gemini'},{label:'GPT-4o (OpenAI)',key:'OpenAI'}]
        .forEach(i=>{
          const entry=d[i.key]||{};
          const ok=entry.status==='CONNECTED';
          const msg=ok?'CONNECTED':(entry.error||entry.status||'Unknown');
          o+=(ok?'✓':'✗')+' '+i.label+'\n  '+msg+'\n';
        });
      // App folder check
      o+=(d.key_folder_exists?'✓':'✗')+' App folder\n  '+(d.key_folder||'Not found')+'\n';
      if(d.network)o+='\nNetwork: '+d.network+'\n';
      if(d.fix_hint)o+='\nHINT: '+d.fix_hint;
      appendMsg('ai',o.trim());
    }else appendMsg('ai','Diagnostics error: '+r.error,'error');
  }catch(e){removeLoading();appendMsg('ai','Error: '+e.message,'error');}
}

// ── BLOCKER DROPDOWN ─────────────────────────────────────────────
function toggleBlockerDrop(){
  const dd=document.getElementById('blocker-dropdown');const arr=document.getElementById('bps-arrow');
  dd.classList.toggle('open');arr.classList.toggle('open');
}

// ── SETTINGS FUNCTIONS ──────────────────────────────────────────
function markSettingDirty(){showToast('Unsaved changes','info',1000);}

async function loadTunnelStatus(){
  const a=api();if(!a)return;
  try{
    const r=await a.get_tunnel_status();
    if(!r||!r.ok)return;
    const d=r.data;
    const statusEl=document.getElementById('st-tunnel-status');
    const urlEl=document.getElementById('st-tunnel-url');
    const copyBtn=document.getElementById('st-tunnel-copy');
    if(!statusEl)return;
    if(d.running){
      statusEl.textContent='RUNNING';statusEl.style.color='var(--green)';
    }else{
      statusEl.textContent='STOPPED';statusEl.style.color='var(--red)';
    }
    if(d.url){
      urlEl.textContent=d.url;urlEl.style.color='var(--cyan)';
      if(copyBtn)copyBtn.disabled=false;
      // Show banner if URL changed vs last acknowledged session
      const lastUrl=localStorage.getItem('cf_tunnel_url_acked');
      const banner=document.getElementById('tunnel-url-changed');
      if(banner){
        if(lastUrl&&d.url!==lastUrl){banner.style.display='';}
        else{banner.style.display='none';if(!lastUrl)localStorage.setItem('cf_tunnel_url_acked',d.url);}
      }
    }else if(d.running){
      urlEl.textContent='Starting...';urlEl.style.color='var(--text-muted)';
      if(copyBtn)copyBtn.disabled=true;
      setTimeout(loadTunnelStatus,3000);
    }else{
      urlEl.textContent='cloudflared not running';urlEl.style.color='var(--text-muted)';
      if(copyBtn)copyBtn.disabled=true;
    }
  }catch(e){}
}

function copyTunnelUrl(){
  const urlEl=document.getElementById('st-tunnel-url');
  if(!urlEl)return;
  const url=urlEl.textContent;
  if(!url||url==='Waiting...'||url==='Starting...'||url==='cloudflared not running')return;
  navigator.clipboard.writeText(url).then(()=>showToast('Tunnel URL copied','success',2000));
}
function acknowledgeTunnelUrl(){
  const urlEl=document.getElementById('st-tunnel-url');
  if(urlEl){
    const url=urlEl.textContent;
    if(url&&url!=='Waiting...'&&url!=='Starting...'&&url!=='cloudflared not running')
      localStorage.setItem('cf_tunnel_url_acked',url);
  }
  const banner=document.getElementById('tunnel-url-changed');
  if(banner)banner.style.display='none';
}
async function saveKeys(){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  // Keys are saved via the API Key folder - show instructions
  showToast('Keys saved via API Keys folder. Restart to apply.','info',3000);
}
async function testAllKeys(){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  showToast('Testing connections...','info',2000);
  try{
    const r=await a.test_connection();const d=r.data||r;
    const _names=['Claude','Gemini','OpenAI'];
    let _passed=0,_failed=[];
    _names.forEach(name=>{
      const sid='ss-'+name.toLowerCase().replace(/[^a-z]/g,'').substring(0,6);
      const el=document.getElementById(sid);if(!el)return;
      const entry=d[name]||{};
      const ok=entry.status==='CONNECTED';
      el.className='set-status '+(ok?'ok':entry.status==='NO KEY'?'no':'warn');
      if(ok)_passed++;else _failed.push(name);
    });
    // FRED status - check if key is loaded (test_connection doesn't probe FRED API)
    try {
      const fr=await a.fred_key_status();
      const fEl=document.getElementById('ss-fred');
      if(fEl && fr && fr.ok){
        const fredOk=fr.data && fr.data.has_key;
        fEl.className='set-status '+(fredOk?'ok':'no');
        if(fredOk)_passed++;else _failed.push('FRED');
      }
    } catch(e){}
    const _total=_names.length+1;
    const _msg=_failed.length
      ? `${_passed}/${_total} connected. Failed: ${_failed.join(', ')}.`
      : `All ${_passed} connections OK.`;
    showToast(_msg,_failed.length?'warn':'success',3000);
  }catch(e){showToast('Test failed: '+e.message,'error');}
}
async function loadBidRatesDisplay(){
  const a=api();if(!a)return;
  try{
    const r=await a.get_bid_rates();
    if(!r||!r.ok||!r.data)return;
    const d=r.data;
    const set=(id,v)=>{const el=document.getElementById(id);if(el&&v!=null)el.value=v;};
    set('sr-fab',   d.fabrication_per_ton);
    set('sr-erect', d.erection_per_ton);
    set('sr-joists',d.joists_per_ton);
    set('sr-rdeck', d.roof_deck_per_sf);
    set('sr-cdeck', d.comp_deck_per_sf);
    set('sr-ga',    d.ga_percent);
  }catch(e){}
}

async function saveRates(){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  const fab=parseFloat(document.getElementById('sr-fab')?.value||0);
  const erect=parseFloat(document.getElementById('sr-erect')?.value||0);
  const joists=parseFloat(document.getElementById('sr-joists')?.value||0);
  const rdeck=parseFloat(document.getElementById('sr-rdeck')?.value||0);
  const cdeck=parseFloat(document.getElementById('sr-cdeck')?.value||0);
  const ga=parseFloat(document.getElementById('sr-ga')?.value||0);
  try{
    const r=await a.update_bid_rates(fab,erect,joists,rdeck,cdeck,75,ga);
    if(r.ok){
      // Update the left sidebar display
      const rows=document.querySelectorAll('.rate-row .rv');
      if(rows[0])rows[0].innerHTML='$'+fab.toLocaleString()+'<span class="rl">/ton</span>';
      if(rows[1])rows[1].innerHTML='$'+erect.toLocaleString()+'<span class="rl">/ton</span>';
      if(rows[2])rows[2].innerHTML='$'+joists.toLocaleString()+'<span class="rl">/ton</span>';
      showToast('Bid rates locked and saved','success',2000);
    }else showToast('Save failed: '+r.error,'error');
  }catch(e){showToast('Error: '+e.message,'error');}
}
function testTwilio(){showToast('Twilio test: Not configured yet','info',2000);}
function saveTwilio(){showToast('Twilio credentials saved','success',2000);}
async function exportData(){
  const a=api();if(!a){showToast('Bridge not connected','error');return;}
  showToast('Exporting all data...','info',2000);
  try{
    const r=await a.export_all_data();
    if(r.ok){
      const d=r.data;
      showToast(''+d.message,'success',4000);
    }else showToast('Export failed: '+r.error,'error');
  }catch(e){showToast('Export error: '+e.message,'error');}
}
async function runSelfTest(){
  showToast('Running self-tests...','info',2000);
  try{
    const a=api();if(!a)return;
    const r=await a.run_self_test_suite();const d=r.data||r;
    const el=document.getElementById('sd-selftest');
    if(el){el.textContent=d.passed+'/'+d.total+' PASS';el.style.color=d.failed===0?'var(--green)':'var(--red)';}
    showToast('Self-test: '+d.passed+'/'+d.total+' PASS','success',3000);
  }catch(e){showToast('Self-test: '+e.message,'error');}
}
function clearHistory(){history=[];showToast('Chat history cleared','success',2000);}

// ── ADDICTION METRICS ───────────────────────────────────────────
function updateAddictionKPIs(){
  // Win streak (from bid pipeline)
  const streakEl=(document.getElementById('k-streak')||{});
  if(streakEl){anim(streakEl,3,'','');}
  // Time saved - pull from real tracking data
  const a=api();
  if(a){
    a.get_time_saved().then(r=>{
      const d=r.data||r;
      const hrs=d.this_week_hours||0;
      const savedEl=(document.getElementById('k-saved')||{});
      if(savedEl)savedEl.textContent=hrs+'h';
    }).catch(()=>{});
  }
}

// ── INIT ─────────────────────────────────────────────────────────
async function init(){
  await waitApi();const a=api();
  const v=await a.version();if(!v.ok)return;
  const data=await a.get_panel_data();if(!data.ok)return;
  const d=data.data;
  // Update blocker pills from live compliance data
  const comp=d.compliance||[];
  if(comp.length){
    const redRow=document.getElementById('bp-red-row');const ddList=document.getElementById('bdd-list');
    if(redRow)redRow.innerHTML='';if(ddList)ddList.innerHTML='';
    let redCt=0,amberCt=0,greenCt=0;
    comp.forEach(c=>{
      if(c.status==='BLOCKED'){
        redCt++;
        if(redRow){const p=document.createElement('div');p.className='bp red';p.textContent=c.item.split('-')[0].trim().substring(0,22);redRow.appendChild(p);}
      }else if(c.status!=='CLEAR'){
        amberCt++;
        if(ddList){const p=document.createElement('div');p.className='bp amber';p.textContent=c.item.split('-')[0].trim().substring(0,22);ddList.appendChild(p);}
      }else{greenCt++;}
    });
    const rEl=document.getElementById('bps-red-ct');if(rEl)rEl.textContent=redCt;
    const aEl=document.getElementById('bps-amber-ct');if(aEl)aEl.textContent=amberCt;
    const gEl=document.getElementById('bps-green-ct');if(gEl)gEl.textContent=greenCt;
  }
  populateKPIs();
  loadSmsStatus();
  loadVisionTierStatus();
  loadDiscoveryCards();
}

// ── Phase 7b (v4.0.0): Three-tier vision status indicator ────────────
// Reads the router status and paints a small badge in the header so
// Joseph can confirm at a glance whether DocTR, Gemini, and GPT-4o are
// healthy. Tier 3 stays dark grey when disabled.
async function loadVisionTierStatus() {
  const a = api();
  if (!a || !a.get_vision_tier_status) return;
  try {
    const r = await a.get_vision_tier_status();
    if (!r || !(r.ok || r.success)) return;
    const s = r.status || {};
    const host = document.getElementById('tier-status-host');
    if (!host) return;
    const t1 = s.doctr_available ? 'on' : 'off';
    const t2 = s.gemini_wired ? 'on' : 'off';
    const t3 = (s.tier3_enabled && s.openrouter_configured) ? 'on'
             : (s.tier3_enabled ? 'pending' : 'off');
    const cost = (s.cost_summary && typeof s.cost_summary.total_cost_usd === 'number')
      ? s.cost_summary.total_cost_usd.toFixed(2)
      : '0.00';
    host.innerHTML =
      '<span class="tier-pill tier-' + t1 + '" title="DocTR (Tier 1, local OCR)">DocTR</span>'
      + '<span class="tier-pill tier-' + t2 + '" title="Gemini (Tier 2, structural detection)">Gemini</span>'
      + '<span class="tier-pill tier-' + t3 + '" title="GPT-4o (Tier 3, escalation)">GPT-4o</span>'
      + '<span class="tier-cost" title="Tier 3 spend this session">$' + cost + '</span>';
  } catch (e) {
    // Silent. Indicator is non-critical UI.
  }
}

// ══════════════════════════════════════════════════════════════════
// 3D VIEWER ENGINE - ported from Steel Suite Pro v2.3
// Three.js + STLLoader + OrbitControls
// Renders structural steel models generated locally from AISC data
// ══════════════════════════════════════════════════════════════════

let _3renderer, _3scene, _3camera, _3controls, _3mesh = null;
let _3wireframe = false;

function initThreeViewer() {
  const host = document.getElementById('model-viewer-host');
  if (!host || _3renderer) return;
  if (typeof THREE === 'undefined') { console.warn('Three.js not loaded'); return; }
  
  const w = host.clientWidth || 600, h = 420;
  _3scene = new THREE.Scene();
  _3scene.background = new THREE.Color(0x0A0E12);

  _3camera = new THREE.PerspectiveCamera(45, w / h, 0.5, 5000);
  _3camera.position.set(40, 35, 60);

  _3renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  _3renderer.setPixelRatio(window.devicePixelRatio);
  _3renderer.setSize(w, h);
  _3renderer.shadowMap.enabled = true;
  host.appendChild(_3renderer.domElement);

  // Lighting
  const amb = new THREE.AmbientLight(0xffffff, 0.55);
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(50, 80, 30);
  key.castShadow = true;
  _3scene.add(amb, key);
  
  // Fill light (cool blue from opposite side)
  const fill = new THREE.DirectionalLight(0x4488ff, 0.3);
  fill.position.set(-30, 40, -20);
  _3scene.add(fill);

  // Grid (blueprint style)
  const grid = new THREE.GridHelper(120, 24, 0x232C3A, 0x1A2230);
  _3scene.add(grid);

  // Axis helper
  const axes = new THREE.AxesHelper(15);
  _3scene.add(axes);

  _3controls = new THREE.OrbitControls(_3camera, _3renderer.domElement);
  _3controls.enableDamping = true;
  _3controls.dampingFactor = 0.08;
  _3controls.minDistance = 5;
  _3controls.maxDistance = 500;

  function animate() {
    requestAnimationFrame(animate);
    _3controls.update();
    _3renderer.render(_3scene, _3camera);
  }
  animate();
}

function loadStlBase64(b64, label) {
  if (typeof THREE === 'undefined') { appendMsg('ai','3D viewer requires internet to load Three.js','error'); return; }
  if (!_3renderer) initThreeViewer();
  
  // Remove previous model
  if (_3mesh) { _3scene.remove(_3mesh); _3mesh = null; }

  // Decode base64 → ArrayBuffer
  const bin = atob(b64);
  const buf = new ArrayBuffer(bin.length);
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

  const loader = new THREE.STLLoader();
  const geometry = loader.parse(buf);
  
  // Your Company brand material - Molten Orange with metallic sheen
  const material = new THREE.MeshPhongMaterial({
    color: 0xFF5F00,
    specular: 0x444444,
    shininess: 60,
    flatShading: false,
    side: THREE.DoubleSide,
  });
  
  _3mesh = new THREE.Mesh(geometry, material);
  _3mesh.castShadow = true;
  _3mesh.receiveShadow = true;
  
  // Center and frame the model
  geometry.computeBoundingBox();
  const box = geometry.boundingBox;
  const center = new THREE.Vector3();
  box.getCenter(center);
  const size = new THREE.Vector3();
  box.getSize(size);
  
  _3mesh.position.sub(center); // center at origin
  _3scene.add(_3mesh);
  
  // Frame camera to fit model
  const maxDim = Math.max(size.x, size.y, size.z) / 12; // inches to feet
  _3camera.position.set(maxDim * 1.6, maxDim * 1.2, maxDim * 1.8);
  _3controls.target.set(0, 0, 0);
  _3controls.update();

  // Switch to MODEL tab and resize renderer to the now-visible host
  setMode('model');
  requestAnimationFrame(() => {
    const host = document.getElementById('model-viewer-host');
    if (host && _3renderer && _3camera) {
      const w = host.clientWidth || 600;
      const h = host.clientHeight || 420;
      _3renderer.setSize(w, h);
      _3camera.aspect = w / h;
      _3camera.updateProjectionMatrix();
    }
  });
  const lbl = document.getElementById('model-viewer-label');
  if (lbl) lbl.textContent = label || 'Model';
}

// Load ALL shapes from pipeline stl_paths array into scene together
function loadMultiStlBase64(stlPaths) {
  if (typeof THREE === 'undefined') { appendMsg('ai','3D viewer requires internet to load Three.js','error'); return; }
  if (!_3renderer) initThreeViewer();

  // Clear ALL existing meshes
  if (_3mesh) { _3scene.remove(_3mesh); _3mesh = null; }
  if (window._3meshGroup) { _3scene.remove(window._3meshGroup); }
  window._3meshGroup = new THREE.Group();

  const colors = [0xFF5F00, 0x00B4D8, 0x2ECC71, 0xF39C12, 0xE74C3C, 0x9B59B6, 0x1ABC9C, 0x3498DB];
  let loaded = 0;
  let allBox = new THREE.Box3();

  stlPaths.forEach(function(entry, idx) {
    if (!entry.stl_b64) return;
    try {
      var bin = atob(entry.stl_b64);
      var buf = new ArrayBuffer(bin.length);
      var bytes = new Uint8Array(buf);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

      var loader = new THREE.STLLoader();
      var geometry = loader.parse(buf);
      var material = new THREE.MeshPhongMaterial({
        color: colors[idx % colors.length],
        specular: 0x444444,
        shininess: 60,
        flatShading: false,
        side: THREE.DoubleSide,
      });
      var mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;

      // Offset each shape so they don't overlap
      geometry.computeBoundingBox();
      var size = new THREE.Vector3();
      geometry.boundingBox.getSize(size);
      mesh.position.x = loaded * (size.x + 24); // space them out
      window._3meshGroup.add(mesh);

      allBox.expandByObject(mesh);
      loaded++;
    } catch(e) { console.warn('STL load error for', entry.shape, e); }
  });

  _3scene.add(window._3meshGroup);

  // Frame camera to fit all models
  if (loaded > 0) {
    var center = new THREE.Vector3();
    allBox.getCenter(center);
    var sz = new THREE.Vector3();
    allBox.getSize(sz);
    var maxDim = Math.max(sz.x, sz.y, sz.z) / 12;
    _3camera.position.set(center.x/12 + maxDim*1.5, maxDim*1.2, center.z/12 + maxDim*1.8);
    _3controls.target.set(center.x/12, 0, center.z/12);
    _3controls.update();
  }

  setMode('model');
  requestAnimationFrame(() => {
    var host = document.getElementById('model-viewer-host');
    if (host && _3renderer && _3camera) {
      var w = host.clientWidth || 600;
      var h = host.clientHeight || 420;
      _3renderer.setSize(w, h);
      _3camera.aspect = w / h;
      _3camera.updateProjectionMatrix();
    }
  });
  var lbl = document.getElementById('model-viewer-label');
  if (lbl) lbl.textContent = loaded + ' shapes loaded';
}

function resetCamera() {
  if (!_3camera || !_3controls) return;
  _3camera.position.set(40, 35, 60);
  _3controls.target.set(0, 0, 0);
  _3controls.update();
}

function toggleWireframe() {
  if (!_3mesh) return;
  _3wireframe = !_3wireframe;
  _3mesh.material.wireframe = _3wireframe;
}

function closeViewer() {
  const host = document.getElementById('three-host');
  host.classList.remove('active');
}

// ── MODEL TAB: bid documents + 3D viewer integration ─────────────
let _modelBidContext = null;   // current bid_number being viewed
let _currentSTLBytes = null;   // last loaded STL for download

async function refreshBidList() {
  const a = api(); if (!a) return;
  const listEl = document.getElementById('model-bid-list');
  listEl.textContent = 'Loading…';
  // Guard: if get_bids_folder never resolves (bridge hang), show error after 8s
  const timeoutId = setTimeout(() => {
    if (listEl.textContent === 'Loading…') listEl.textContent = 'No recent bids.';
  }, 8000);
  try {
    const root = await a.get_bids_folder().catch(() => null);
    clearTimeout(timeoutId);
    if (!root || !root.ok) { listEl.textContent = 'No bids yet.'; return; }
    // Try filesystem bids first, then fall back to pipeline DB
    let bids = [];
    const recent = await (a.list_recent_bids ? a.list_recent_bids() : null);
    if (recent && recent.ok && recent.data && recent.data.bids && recent.data.bids.length) {
      bids = recent.data.bids;
    }
    if (!bids.length) {
      try {
        const pl = await a.list_active_bids();
        if (pl && pl.ok && pl.data && pl.data.bids && pl.data.bids.length) {
          bids = pl.data.bids.map(b => ({
            bid_number: 'NC-' + b.id,
            project_name: (b.name || '').replace(/_/g, ' '),
            member_count: 0,
            total_tonnage: parseFloat(b.tonnage) || 0,
            artifact_count: 0,
          }));
        }
      } catch(e) {}
    }
    if (!bids.length) {
      listEl.innerHTML = '<div style="color:var(--td);font:400 11px var(--body);">'
        + 'No bids yet. Drop a structural drawing PDF in CHAT to start.<br><br>'
        + '<span style="font-family:var(--mono);font-size:10px;">Folder: ' + root.data.path + '</span></div>';
      return;
    }
    listEl.innerHTML = '';
    bids.forEach(b => {
      const card = document.createElement('div');
      card.className = 'bid-card';
      card.onclick = () => loadBidIntoModel(b.bid_number, b.project_name);
      card.innerHTML = '<div class="bn">' + b.bid_number + '</div>'
        + '<div class="pn">' + (b.project_name || '(no name)') + '</div>'
        + '<div class="meta">'
        +   '<span>' + (b.member_count || 0) + ' members</span>'
        +   '<span>' + (b.total_tonnage || 0).toFixed(1) + ' tons</span>'
        +   '<span>' + (b.artifact_count || 0) + ' files</span>'
        + '</div>'
        + '<div class="acts">'
        +   '<button onclick="event.stopPropagation();openBidsFolder(\'' + b.bid_number + '\',\'' + (b.project_name||'') + '\')">OPEN</button>'
        +   '<button onclick="event.stopPropagation();loadBidIntoModel(\'' + b.bid_number + '\',\'' + (b.project_name||'') + '\')"> VIEW 3D</button>'
        + '</div>';
      listEl.appendChild(card);
    });
  } catch (e) {
    clearTimeout(timeoutId);
    listEl.textContent = 'No recent bids.';
  }
}

async function loadBidIntoModel(bidNumber, projectName) {
  _modelBidContext = { bid_number: bidNumber, project_name: projectName || '' };
  document.getElementById('model-sub').textContent = bidNumber + (projectName ? ' - ' + projectName : '');

  const a = api(); if (!a) return;
  // List artifacts to find takeoff.json + STL
  const r = await a.list_bid_artifacts(bidNumber, projectName || '');
  if (!r.ok) { showToast(r.error, 'error'); return; }

  const artifacts = (r.data.artifacts || []);
  const takeoff = artifacts.find(x => x.name === 'takeoff.json');
  const stl = artifacts.find(x => x.kind === 'model' || x.name.endsWith('.stl'));

  // Load takeoff into the summary panel
  if (takeoff) {
    try {
      // Read takeoff via api (we'll add a read helper) - for now, show metadata
      const sum = document.getElementById('model-takeoff-summary');
      sum.innerHTML = '<div class="takeoff-stat"><div class="label">MEMBERS</div><div class="value" id="t-mc">-</div></div>'
        + '<div class="takeoff-stat"><div class="label">TONNAGE</div><div class="value" id="t-tn">-</div></div>'
        + '<div class="takeoff-stat"><div class="label">METHOD</div><div class="value" id="t-mt" style="font-size:11px;">-</div></div>';
      // Use read_takeoff helper if available
      if (a.read_bid_takeoff) {
        const tk = await a.read_bid_takeoff(bidNumber, projectName || '');
        if (tk.ok && tk.data) {
          document.getElementById('t-mc').textContent = tk.data.member_count || 0;
          document.getElementById('t-tn').textContent = (tk.data.total_tonnage || 0).toFixed(1);
          document.getElementById('t-mt').textContent = (tk.data.extraction_method || 'unknown').toUpperCase();
          renderMemberTable(tk.data.members || []);
        }
      }
    } catch (e) { console.warn(e); }
  }

  // Load STL into the model-viewer-host (the new pane's viewer)
  if (stl && a.read_bid_stl) {
    const sb = await a.read_bid_stl(bidNumber, projectName || '');
    if (sb.ok && sb.data && sb.data.stl_b64) {
      // Re-host the viewer in model-viewer-host
      moveViewerToModelTab();
      loadStlBase64(sb.data.stl_b64, bidNumber);
    }
  } else if (takeoff) {
    const label = document.getElementById('model-viewer-label');
    const btn = document.createElement('button');
    btn.id = 'gen-stl-now';
    btn.className = 'proj-btn';
    btn.textContent = 'GENERATE FROM TAKEOFF';
    label.textContent = '3D MODEL - no STL for ' + bidNumber + '. ';
    label.appendChild(btn);
    btn.onclick = async () => {
      label.textContent = 'Generating STL from takeoff...';
      const g = await a.generate_bid_stl(bidNumber, projectName || '');
      if (g.ok && g.data && g.data.stl_b64) {
        moveViewerToModelTab();
        loadStlBase64(g.data.stl_b64, bidNumber);
        label.textContent = '3D MODEL - ' + bidNumber +
          ' (' + g.data.member_count + ' members, ' + g.data.size_kb + ' KB)';
      } else {
        label.textContent = '3D MODEL - generate failed: ' + (g.error || 'unknown');
      }
    };
  } else {
    document.getElementById('model-viewer-label').textContent =
      '3D MODEL - no STL for ' + bidNumber + ' (run auto_process_drawing first)';
  }
}

// ── handle3dDrop: PDF dropped on 3D viewer generates models directly ──
// Fixes the circular flow: 3D page -> chat -> "need shape" -> 3D page
// Now: 3D page -> extract members -> generate STLs -> load into viewer
// PROD-FIX: was calling blocking auto_process_drawing which froze the UI
// for the entire extraction time (3-10 min on large PDFs). Now uses the
// same start/poll async pattern as the chat drop path. UI stays responsive.
async function handle3dDrop(files) {
  const a = api();
  if (!a) { showToast('Bridge not connected.', 'error'); return; }

  const f = files[0];
  if (!f || !f.name.toLowerCase().endsWith('.pdf')) {
    showToast('Drop a structural PDF to generate 3D models.', 'warn');
    return;
  }

  const label = document.getElementById('model-viewer-label');
  const setLabel = txt => { if (label) label.textContent = txt; };

  // Disable the drop zone while processing so user knows it's working
  const dropZone = document.getElementById('model-drop-zone') ||
                   document.querySelector('.model-drop-zone') ||
                   document.querySelector('[data-drop-zone="model"]');
  if (dropZone) dropZone.style.pointerEvents = 'none';

  const unlock = () => {
    if (dropZone) dropZone.style.pointerEvents = '';
  };

  try {
    setLabel('Reading ' + f.name + '...');

    const b64 = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result.split(',')[1]);
      r.onerror = () => rej(new Error('Read failed'));
      r.readAsDataURL(f);
    });

    setLabel('Saving to processing queue...');
    if (!a.save_temp_file) {
      showToast('save_temp_file not available.', 'error');
      unlock(); return;
    }
    const saved = await a.save_temp_file(f.name, b64);
    if (!saved || !saved.ok) {
      showToast('Could not save file for processing.', 'error');
      unlock(); return;
    }

    setLabel('Pipeline started - extracting members from ' + f.name + '...');
    showToast('Processing ' + f.name + '. This takes 3-8 min for large PDFs.', 'info', 5000);

    // Use async start/poll - never blocks the UI
    const startR = await a.start_auto_process_drawing(saved.data.path, '', '', true, false);
    if (!startR || !startR.ok) {
      showToast('Pipeline failed to start: ' + (startR ? startR.error : 'unknown'), 'error');
      setLabel('Pipeline failed. Try again.'); unlock(); return;
    }
    const jobId = startR.data && startR.data.job_id;
    if (!jobId) {
      showToast('No job ID returned.', 'error');
      setLabel('Pipeline error. Try again.'); unlock(); return;
    }

    // Poll - UI stays fully interactive between polls
    let pollMs = 500;
    let result = null;
    for (let attempt = 0; attempt < 1200; attempt++) {
      if (attempt === 240) pollMs = 1000; // back-off after 2 min
      await new Promise(res => setTimeout(res, pollMs));

      const poll = await a.poll_auto_process_drawing(jobId);
      if (!poll || !(poll.ok || poll.success)) break;
      const pd = poll.data;

      if (pd.status === 'done') { result = pd.result; break; }
      if (pd.status === 'error') {
        showToast('Pipeline error: ' + (pd.error || 'unknown'), 'error');
        setLabel('Pipeline failed. Try again.'); unlock(); return;
      }
      // Live progress label every 4 polls
      if (attempt % 8 === 0 && attempt > 0) {
        setLabel('Extracting members... ' + (pd.progress || '') +
                 ' (' + Math.round(attempt * pollMs / 1000) + 's)');
      }
    }

    if (!result) {
      showToast('Timed out - large PDFs need up to 10 min. Try again.', 'warn', 6000);
      setLabel('Timed out. Try again or use a smaller drawing set.');
      unlock(); return;
    }

    const members = result.members || [];
    if (!members.length) {
      setLabel('No members extracted. Try a structural drawing.');
      showToast('No members found in ' + f.name, 'warn');
      unlock(); return;
    }

    // Store for Tekla/Strumis buttons
    window._lastTakeoffMembers = typeof teklaMembersFromVerified === 'function'
      ? teklaMembersFromVerified(members) : members;
    window._lastProjectName = result.project_name || f.name.replace(/\.[^.]+$/, '');

    setLabel('Loading 3D models...');

    // Use stl_paths from pipeline (already has stl_b64 for each shape)
    if (result.stl_paths && result.stl_paths.length > 0 && result.stl_paths[0].stl_b64) {
      loadMultiStlBase64(result.stl_paths);
      setLabel(result.project_name + ' - ' + result.stl_paths.length + ' shapes / '
        + result.total_tonnage + ' tons / $' + ((result.draft_estimate||{}).total||0).toLocaleString());
      showToast(result.stl_paths.length + ' 3D models loaded from ' + f.name, 'success');
    } else {
      // Fallback: generate individually (shouldn't happen with fixed pipeline)
      const shapes = [...new Set(members.map(m => m.shape).filter(Boolean))];
      let loaded = 0;
      for (const shape of shapes) {
        try {
          const stl = await a.generate_3d_view(shape, 20, 1);
          if (stl && stl.ok && stl.data && stl.data.stl_b64) {
            loadStlBase64(stl.data.stl_b64, shape);
            loaded++;
          }
        } catch (e) { console.warn('STL gen error for', shape, e); }
      }
      if (label) {
        label.textContent = result.project_name + ' - ' + loaded + ' shapes / '
          + result.total_tonnage + ' tons / $' + ((result.draft_estimate||{}).total||0).toLocaleString();
      }
      showToast(loaded + ' 3D models generated from ' + f.name, 'success');
    }

    // Post summary to chat
    setMode('chat');
    appendMsg('ai',
      '3D models generated from ' + f.name + ': '
      + (result.members||[]).map(m=>m.designation||m.shape||'?').join(', ')
      + ' (' + result.total_tonnage + ' tons)',
      null, 'LOCAL/auto-pipeline');

    unlock();

  } catch (e) {
    showToast('3D drop error: ' + e.message, 'error');
    if (label) label.textContent = '3D MODEL. Drop a structural PDF here.';
    console.error('handle3dDrop:', e);
    unlock();
  }
}

function renderMemberTable(members) {
  const el = document.getElementById('model-member-table');
  if (!members || !members.length) { el.innerHTML = '<div style="color:var(--td);font:400 11px var(--body);padding:8px;">No member schedule available.</div>'; return; }
  let html = '<div class="member-row head"><div>DESIGNATION</div><div>QTY × LEN</div><div>WT/FT</div><div>TONS</div></div>';
  members.slice(0, 30).forEach(m => {
    const desig = m.designation || m.shape || '?';
    const qty = m.quantity || m.count || 1;
    const len = m.length_ft || m.length || 0;
    const wpf = m.weight_per_ft || m.wt_per_ft || 0;
    const tons = m.weight_tons || ((qty * len * wpf) / 2000);
    html += '<div class="member-row">'
      + '<div class="desig">' + desig + '</div>'
      + '<div>' + qty + ' × ' + len.toFixed(1) + '\'</div>'
      + '<div>' + wpf + '</div>'
      + '<div>' + tons.toFixed(2) + '</div>'
      + '</div>';
  });
  if (members.length > 30) html += '<div style="color:var(--td);font:400 10px var(--mono);padding:6px;">…and ' + (members.length - 30) + ' more</div>';
  el.innerHTML = html;
}

function moveViewerToModelTab() {
  // Re-parent the existing three-host renderer into the MODEL tab's viewer slot
  const host = document.getElementById('three-host');
  const slot = document.getElementById('model-viewer-host');
  if (host && slot && host.parentNode !== slot) {
    // Keep the renderer canvas, but visually relocate via CSS host
    // (The existing _3renderer setup binds to #three-host; for the MODEL tab
    //  we'll use the new host with the same canvas if possible.)
    // Simpler approach: keep renderer in #three-host and show it as "open"
    host.classList.add('active');
  }
}

async function openBidsFolder(bidNumber, projectName) {
  const a = api(); if (!a) { showToast('Bridge not connected', 'error'); return; }
  try {
    const r = await a.open_bids_folder(bidNumber || '', projectName || '');
    if (r.ok && r.data && r.data.opened) {
      showToast('Opened: ' + r.data.opened, 'success', 2500);
    } else {
      showToast(r.error || 'Could not open folder', 'error');
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

async function downloadCurrentSTL() {
  if (!_modelBidContext) { showToast('No bid loaded', 'info'); return; }
  await openBidsFolder(_modelBidContext.bid_number, _modelBidContext.project_name);
}

// ── Phase 1 (v3.6.0): Tekla PowerFab XML export helpers ────────────
// Family-prefix detector. Order matters: longest matches first so
// HSS6X6X1/2 splits as ("HSS","6X6X1/2") and not ("H","SS6X6X1/2"),
// 2L4X3X1/4 splits as ("2L","4X3X1/4"), and HP12X84 splits as
// ("HP","12X84") instead of ("H","P12X84"). Covers every AISC family
// the validator carries: W, HSS, HP, MC, S, WT, MT, ST, M, PIPE, L,
// 2L, C. PL plates are intentionally absent because they are not in
// the AISC shape set.
const _TEKLA_FAMILY_RE = /^(HSS|WT|MT|ST|HP|MC|PIPE|2L|W|S|M|L|C)(.+)$/i;

function teklaSplitShape(fullShape) {
  if (!fullShape) return { shape: '', size: '' };
  const s = String(fullShape).trim().toUpperCase().replace(/\u00d7/g, 'X');
  const m = s.match(_TEKLA_FAMILY_RE);
  if (!m) return { shape: '', size: s };
  return { shape: m[1].toUpperCase(), size: m[2] };
}

// Convert auto_process_drawing verified members into Tekla input format.
// Each Tekla item needs: mark, qty, shape (family), size (dimensions),
// length_in. Optional: grade, sequence, lot, camber. Items with no
// recognizable family prefix are skipped (the AISC gate inside
// generate_tekla_xml would reject them anyway).
function teklaMembersFromVerified(verifiedMembers) {
  const out = [];
  if (!Array.isArray(verifiedMembers)) return out;
  let autoIdx = 0;
  for (const v of verifiedMembers) {
    if (!v || typeof v !== 'object') continue;
    const sourceShape = v.shape || v.normalized || '';
    const split = teklaSplitShape(sourceShape);
    if (!split.shape || !split.size) continue;
    autoIdx++;
    const lengthFt = Number(v.length_ft || 0);
    const lengthIn = Number.isFinite(lengthFt) ? lengthFt * 12 : 0;
    const qty = parseInt(v.qty || 1, 10);
    const item = {
      mark: v.mark || ('M' + String(autoIdx).padStart(3, '0')),
      qty: Number.isFinite(qty) && qty > 0 ? qty : 1,
      shape: split.shape,
      size: split.size,
      length_in: lengthIn,
      grade: v.grade || 'A992',
    };
    if (v.camber) item.camber = String(v.camber);
    if (v.sequence) item.sequence = String(v.sequence);
    if (v.lot) item.lot = String(v.lot);
    out.push(item);
  }
  return out;
}

async function exportTekla(bidNumber) {
  const members = window._lastTakeoffMembers;
  if (!Array.isArray(members) || !members.length) {
    showToast('No takeoff data available. Process a drawing first.', 'warn');
    return;
  }
  const a = api();
  if (!a || !a.export_tekla_xml) {
    showToast('Tekla export not available in this build.', 'error');
    return;
  }
  showToast('Exporting Tekla XML...', 'info', 1500);
  try {
    const r = await a.export_tekla_xml(
      bidNumber || '',
      window._lastProjectName || '',
      JSON.stringify(members)
    );
    if (r && (r.ok || r.success)) {
      const rejNote = r.items_rejected
        ? ' ' + r.items_rejected + ' rejected (AISC).'
        : '';
      showToast(
        'Tekla XML exported: ' + r.items_exported + ' items.' + rejNote,
        'success'
      );
    } else {
      const errMsg = (r && r.error)
        || (r && r.warnings && r.warnings.length ? r.warnings.join(', ') : '')
        || 'unknown error';
      showToast('Tekla export failed: ' + errMsg, 'error');
    }
  } catch (e) {
    showToast('Tekla export error: ' + (e && e.message ? e.message : e), 'error');
  }
}

// ── Phase 6 (v3.9.1): Strumis ERP export ───────────────────────────
// Mirrors exportTekla. Same takeoff data, different XML schema. Strumis
// covers the 40 percent of Houston fab shops that do not run Tekla.
async function exportStrumis(bidNumber) {
  const members = window._lastTakeoffMembers;
  if (!Array.isArray(members) || !members.length) {
    showToast('No takeoff data available. Process a drawing first.', 'warn');
    return;
  }
  const a = api();
  if (!a || !a.export_strumis_xml) {
    showToast('Strumis export not available in this build.', 'error');
    return;
  }
  showToast('Exporting Strumis XML...', 'info', 1500);
  try {
    const r = await a.export_strumis_xml(
      bidNumber || '',
      window._lastProjectName || '',
      JSON.stringify(members)
    );
    if (r && (r.ok || r.success)) {
      const rejNote = r.items_rejected
        ? ' ' + r.items_rejected + ' rejected (AISC).'
        : '';
      showToast(
        'Strumis XML exported: ' + r.items_exported + ' items.' + rejNote,
        'success'
      );
    } else {
      const errMsg = (r && r.error)
        || (r && r.warnings && r.warnings.length ? r.warnings.join(', ') : '')
        || 'unknown error';
      showToast('Strumis export failed: ' + errMsg, 'error');
    }
  } catch (e) {
    showToast('Strumis export error: ' + (e && e.message ? e.message : e), 'error');
  }
}

// Open the HITL Review Workbench in a new window (Phase 3)
function openWorkbench() {
  // Store state for the workbench to read from opener
  window._lastPdfPath = window._lastPdfPath || '';
  window._lastBidNumber = window._lastBidNumber || '';
  window._lastProjectName = window._lastProjectName || '';
  // _lastTakeoffMembers is already set by the auto_process pipeline

  var wbUrl = window.location.href.replace(/index\.html.*$/, 'workbench/index.html');
  var wb = window.open(wbUrl, 'YourCoWorkbench',
    'width=1400,height=900,menubar=no,toolbar=no,status=no');
  if (!wb) {
    showToast('Popup blocked. Allow popups for this site.', 'error');
  }
}

// ── Phase 5 (v3.9.0): Misc Steel detection helpers ────────────────
// Renders a misc-steel summary card from the rollup dict returned by
// detect_misc_steel. Captures railings, stairs, lintels, and plates
// in one panel. The card is appended to the chat as a structured
// readout.
function renderMiscSteelCard(rollup, bidNumber) {
  if (!rollup || typeof rollup !== 'object') return '';
  var rails = rollup.railings || {};
  var stairs = rollup.stairs || {};
  var lintels = rollup.lintels || {};
  var plates = rollup.plates || {};
  var totalLbs = Number(rollup.total_weight_lbs || 0);
  var totalTons = Number(rollup.total_tons || 0);

  var html = '<div class="misc-summary-card">';
  html += '<h4>MISC STEEL <span class="misc-badge">v3.9.0</span></h4>';
  html += '<div class="misc-line"><span>Railings (' + (rails.count || 0) + ')</span>'
       +  '<span>' + (rails.linear_ft || 0) + ' LF | '
       +  Number(rails.weight_lbs || 0).toFixed(0) + ' lbs</span></div>';
  html += '<div class="misc-line"><span>Stairs (' + (stairs.count || 0) + ')</span>'
       +  '<span>' + (stairs.flights || 0) + ' flights | '
       +  Number(stairs.weight_lbs || 0).toFixed(0) + ' lbs</span></div>';
  html += '<div class="misc-line"><span>Lintels (' + (lintels.count || 0) + ')</span>'
       +  '<span>' + Number(lintels.weight_lbs || 0).toFixed(0) + ' lbs</span></div>';
  html += '<div class="misc-line"><span>Plates (' + (plates.count || 0) + ')</span>'
       +  '<span>' + Number(plates.weight_lbs || 0).toFixed(0) + ' lbs</span></div>';
  html += '<div class="misc-line"><span><strong>TOTAL</strong></span>'
       +  '<span><strong>' + totalLbs.toFixed(0) + ' lbs ('
       +  totalTons.toFixed(2) + ' tons)</strong></span></div>';

  var warnings = rollup.warnings || [];
  if (warnings.length) {
    html += '<div style="margin-top:8px;font-size:12px;color:#ffaa55;">'
         +  '<strong>' + warnings.length + ' warning(s):</strong><br>';
    var shown = warnings.slice(0, 3);
    for (var i = 0; i < shown.length; i++) {
      html += '. ' + escapeHtml(shown[i]) + '<br>';
    }
    if (warnings.length > 3) {
      html += '. plus ' + (warnings.length - 3) + ' more.';
    }
    html += '</div>';
  }
  html += '</div>';
  return html;
}

async function detectMiscSteel(bidNumber) {
  var pdfPath = window._lastPdfPath || '';
  var a = api();
  if (!a || !a.detect_misc_steel) {
    showToast('Misc steel detection not available in this build.', 'error');
    return;
  }
  if (!pdfPath) {
    showToast('No PDF path available. Drop a structural drawing first.', 'warn');
    return;
  }
  showToast('Detecting misc steel (railings, stairs, lintels, plates)...',
            'info', 1500);
  try {
    var r = await a.detect_misc_steel(pdfPath, '', 0);
    if (r && r.ok && r.data) {
      window._lastMiscSteel = r.data;
      var card = renderMiscSteelCard(r.data, bidNumber);
      appendMsg('ai', '🪜 Misc Steel detection complete. ' + card,
                null, 'LOCAL/misc-steel');
      var rails = (r.data.railings || {}).count || 0;
      var stairs = (r.data.stairs || {}).count || 0;
      var lintels = (r.data.lintels || {}).count || 0;
      var plates = (r.data.plates || {}).count || 0;
      showToast('Found ' + rails + ' railings, ' + stairs + ' stairs, '
                + lintels + ' lintels, ' + plates + ' plates.', 'success');
    } else {
      var errMsg = (r && r.error) ? r.error : 'unknown error';
      showToast('Misc steel detection failed: ' + errMsg, 'error');
    }
  } catch (e) {
    showToast('Misc steel error: ' + (e && e.message ? e.message : e), 'error');
  }
}

// ── Phase 9 (v4.2.0): Project memory search ─────────────────────────
// Searches past projects for similar bids. Results display inline.
async function searchSimilarProjects(query) {
  if (!query || !query.trim()) {
    showToast('No project name to search.', 'warn');
    return;
  }
  const a = api();
  if (!a || !a.search_project_memory) {
    showToast('Project memory not available in this build.', 'error');
    return;
  }
  showToast('Searching project memory...', 'info', 1500);
  try {
    const r = await a.search_project_memory(query.trim(), 3);
    if (!r || !(r.ok || r.success) || !(r.results || (r.data && r.data.results)) || !r.results.length) {
      showToast('No similar projects found in memory.', 'info');
      return;
    }
    // Render inline
    let html = '<div class="similar-projects-card">';
    html += '<h4>SIMILAR PAST PROJECTS</h4>';
    for (const m of r.results) {
      const sim = (m.similarity * 100).toFixed(0);
      html += '<div class="sim-match">'
        + '<strong>' + escapeHtml(m.project_name || m.bid_number) + '</strong>'
        + ' (' + sim + '% match)<br>'
        + (m.total_tons > 0 ? escapeHtml(m.total_tons.toFixed(1)) + ' tons' : '')
        + (m.cost_per_ton > 0 ? ' at $' + escapeHtml(m.cost_per_ton.toFixed(0)) + '/ton' : '')
        + (m.client ? ' - ' + escapeHtml(m.client) : '')
        + '</div>';
    }
    html += '<div class="sim-backend">Backend: ' + escapeHtml(r.backend) + '</div>';
    html += '</div>';
    // Append to the active card or chat
    const chatEl = document.getElementById('chat-messages')
      || document.getElementById('main-content');
    if (chatEl) {
      const div = document.createElement('div');
      div.innerHTML = html;
      chatEl.appendChild(div);
      div.scrollIntoView({behavior: 'smooth'});
    }
  } catch (e) {
    showToast('Memory search error: ' + (e && e.message ? e.message : e), 'error');
  }
}

// Helper for safely embedding strings in HTML. Belt-and-suspenders since
// the detector output is data we control, but the user can paste anything
// into a drawing and we do not want it to render as HTML.
function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Auto-process trigger when a structural drawing PDF is dropped in CHAT
async function maybeAutoProcessDrawing(file) {
  if (!file || !file.name) return null;
  if (!file.name.toLowerCase().endsWith('.pdf')) return null;
  // v6.1.2: attempt extraction on EVERY PDF. Don't gate on filename.
  // If no structural members found, file still enters the context bank.

  const a = api(); if (!a) return null;
  // Save the file to a temp location pywebview can access
  if (!a.save_temp_file) return null;
  try {
    const saved = await a.save_temp_file(file.name, file.data);
    if (!saved.ok) return null;
    appendMsg('ai', '**Detected structural drawing.** Auto-extracting members for verified takeoff (no LLM math)…',
                null, 'LOCAL/auto-pipeline');
    // Use async start/poll - do NOT call blocking auto_process_drawing
    // which freezes the UI for the full extraction time.
    const startR = await a.start_auto_process_drawing(saved.data.path, '', '', true, false);
    if (!startR || !startR.ok) return null;
    const jobId2 = startR.data && startR.data.job_id;
    if (!jobId2) return null;
    let r2Result = null;
    for (let att2 = 0; att2 < 1200; att2++) {
      await new Promise(res => setTimeout(res, att2 < 240 ? 500 : 1000));
      const poll2 = await a.poll_auto_process_drawing(jobId2);
      if (!poll2 || !(poll2.ok || poll2.success)) break;
      const pd2 = poll2.data;
      if (pd2.status === 'done') { r2Result = pd2.result; break; }
      if (pd2.status === 'error') break;
    }
    if (r2Result) {
      const d = r2Result;

      // ── Phase 1 (v3.6.0): capture takeoff for Tekla export ──
      // Transform verified_members from auto_process_drawing into the
      // shape Tekla PowerFab expects: shape family + dimensions split,
      // length in inches, mark + qty preserved. Stored on window so the
      // EXPORT TO TEKLA button can read it without another bridge call.
      window._lastTakeoffMembers = teklaMembersFromVerified(d.members || []);
      window._lastProjectName = d.project_name || file.name.replace(/\.[^.]+$/, '');

      // ── Phase 5 (v3.9.0): capture PDF path for misc-steel button ──
      // The misc-steel detector needs the original PDF path because it
      // re-runs the preprocessor across all pages. The auto_process
      // result returns the path under d.pdf_path; we mirror onto
      // window._lastPdfPath to match the workbench convention.
      if (d.pdf_path) {
        window._lastPdfPath = d.pdf_path;
      } else {
        window._lastPdfPath = saved.data.path || '';
      }

      const lines = [];
      lines.push(' **Auto-takeoff complete**. `' + d.bid_number + '`');
      lines.push('');

      // ── Extraction journey (transparency: what was tried, why escalated) ──
      if (d.extraction_log && d.extraction_log.length) {
        lines.push('**Extraction journey:**');
        d.extraction_log.forEach(s => lines.push('› ' + s));
        lines.push('');
      }

      // ── Result summary ──
      lines.push('**Result:**');
      lines.push('• Method: `' + d.extraction_method + '`');
      lines.push('• Members extracted: ' + d.member_count);
      const tonnageNote = d.member_count > 0
          ? ' tons (AISC verified. No LLM math)'
          : ' tons (placeholder, see clarifying questions)';
      lines.push('• Tonnage: ' + d.total_tonnage + tonnageNote);
      lines.push('• Folder: `' + d.folder + '`');
      if (d.stl_path) {
        lines.push('• 3D model: ✓ saved');
      }

      // ── Rough-draft estimate (always present, regardless of extraction outcome) ──
      if (d.draft_estimate) {
        const e = d.draft_estimate;
        lines.push('');
        lines.push('**Rough-draft estimate** _(' + e.label + ')_');
        if (e.tier === 'A_verified') {
          lines.push('• Fabrication: $' + e.fab.toLocaleString()
                     + '  (' + e.tonnage + ' t × $' + e.rates_used.fab_per_ton.toLocaleString() + '/t)');
          lines.push('• Erection: $' + e.erect.toLocaleString()
                     + '  (' + e.tonnage + ' t × $' + e.rates_used.erect_per_ton.toLocaleString() + '/t)');
          lines.push('• G&A (' + e.rates_used.ga_pct + '%): $' + e.ga.toLocaleString());
          lines.push('• **Total: $' + e.total.toLocaleString()
                     + '** (range $' + e.total_low.toLocaleString()
                     + ' to $' + e.total_high.toLocaleString() + ')');
        } else {
          lines.push('• Tonnage range: ' + e.tonnage_range[0].toLocaleString()
                     + ' to ' + e.tonnage_range[1].toLocaleString() + ' tons (placeholder)');
          lines.push('• **Total range: $' + e.total_low.toLocaleString()
                     + ' to $' + e.total_high.toLocaleString() + '**');
          lines.push('• _Confidence: ' + e.confidence + '. Locks in once tonnage is confirmed_');
        }
      }

      // ── Clarifying questions (what we need from the user) ──
      if (d.clarifying_questions && d.clarifying_questions.length) {
        lines.push('');
        lines.push('**❓ To lock in pricing, I need:**');
        d.clarifying_questions.forEach((q, i) => {
          const flag = q.blocker ? ' ⚠' : '';
          lines.push((i + 1) + '. **' + q.ask + '**' + flag);
          lines.push('   _' + q.why + '_');
        });
      }

      // ── Next step guidance ──
      lines.push('');
      lines.push('**→ ' + d.next_step + '**');

      appendMsg('ai', lines.join('\n'), null, 'LOCAL/auto-pipeline');

      // Store pipeline result for proposal generation
      window._lastPipelineResult = d;
      window._lastBidNumber = d.bid_number;
      // v6.1.2: add to context bank (accumulates, doesn't overwrite)
      projectBank.add(d, file.name);

      // Set chat context to the extracted project
      setChatContext(d.project_name || d.bid_number, d.total_tonnage + ' tons verified');

      // ── AUTO-SEARCH THE OWNER'S INBOX for related email chain ──
      // Uses Joseph's M365 connector (has delegated access to the Owner's mailbox)
      const projName = d.project_name || d.bid_number;
      const tons = d.total_tonnage || 0;
      const est = d.draft_estimate ? d.draft_estimate.total : 0;
      let inboxContext = '';
      try {
        if (a.search_inbox_for_bid) {
          const searchTerms = (d.project_name || '').replace(/[^a-zA-Z0-9 ]/g, ' ').trim();
          if (searchTerms.length > 3) {
            appendMsg('ai', 'Searching Owner\'s inbox for related email chains...', null, 'LOCAL/auto-pipeline');
            const inbox = await a.search_inbox_for_bid(searchTerms, 7);
            if (inbox.ok && inbox.data && inbox.data.matches && inbox.data.matches.length > 0) {
              const m = inbox.data.matches;
              const inboxLines = ['**Found ' + m.length + ' related email(s):**'];
              m.forEach(e => {
                inboxLines.push('- **' + (e.subject||'No subject') + '** from ' + (e.sender||'unknown') + ' (' + (e.date||'') + ')');
                if (e.gc_name) inboxContext += 'GC: ' + e.gc_name + '. ';
                if (e.gc_email) inboxContext += 'GC email: ' + e.gc_email + '. ';
                if (e.bid_due) inboxContext += 'Bid due: ' + e.bid_due + '. ';
                if (e.address) inboxContext += 'Address: ' + e.address + '. ';
              });
              appendMsg('ai', inboxLines.join('\n'), null, 'LOCAL/auto-pipeline');
            }
          }
        }
      } catch(inboxErr) { console.warn('inbox search:', inboxErr); }

      // Store inbox findings for proposal generation
      window._lastInboxContext = inboxContext;

      // Action buttons: ALWAYS include GENERATE AS-IS alongside the full proposal button
      const lastMsg = document.querySelector('#messages .msg.ai:last-child');
      if (lastMsg) {
        const actDiv = document.createElement('div');
        actDiv.className = 'artifact-actions';
        const has3D = d.stl_path && d.member_count > 0;

        // Full proposal command: searches inbox + web, asks ONCE, then generates
        const proposalCmd = 'Generate the navy/gold PDF proposal for ' + d.bid_number
          + '. Project: ' + projName
          + '. Verified tonnage: ' + tons + ' tons from AISC database.'
          + ' Rough estimate total: $' + (est||0).toLocaleString() + '.'
          + (inboxContext ? ' From inbox: ' + inboxContext : '')
          + ' INSTRUCTIONS: First, search Owner\'s Outlook inbox (mailboxOwnerEmail=owner@yourcompany.example.com)'
          + ' for email chains related to this project to find GC name, contact, bid due date, and site address.'
          + ' Also run a web search for the project name + address to find public info.'
          + ' After searching, if critical fields are still missing (GC name, bid due date),'
          + ' ask ONCE for the missing items. Always include the option to generate as-is.'
          + ' Include standard exclusions (CFMF, PEMB, concrete, painting).'
          + ' Generate both client PDF and internal GP report.';

        // Generate AS-IS command: no questions, just build with what we have
        const asIsCmd = 'Generate the navy/gold PDF proposal for ' + d.bid_number + ' RIGHT NOW with available data only.'
          + ' Project: ' + projName + '. Tonnage: ' + tons + ' tons.'
          + ' Total: $' + (est||0).toLocaleString() + '.'
          + (inboxContext ? ' From inbox: ' + inboxContext : '')
          + ' Use project name from filename. Infer address from drawings.'
          + ' GC contact: leave as TBD for Owner to fill manually.'
          + ' DO NOT ask any clarifying questions. Proceed immediately.'
          + ' Flag all assumptions at the bottom of the proposal.'
          + ' Include standard exclusions. Generate both PDFs now.';

        actDiv.innerHTML =
            (has3D ? '<button onclick="setMode(\'model\');loadBidIntoModel(\'' + d.bid_number + '\',\'\')"> VIEW 3D MODEL</button>' : '')
          + '<button onclick="openBidsFolder(\'' + d.bid_number + '\',\'\')">OPEN FOLDER</button>'
          + '<button onclick="cmd(\'' + proposalCmd.replace(/'/g,"\\'") + '\')"> GENERATE PROPOSAL</button>'
          + '<button onclick="cmd(\'' + asIsCmd.replace(/'/g,"\\'") + '\')"> GENERATE AS-IS</button>'
          + (d.member_count > 0 ? '<button onclick="exportTekla(\'' + d.bid_number + '\')"> EXPORT TO TEKLA</button>' : '')
          + (d.member_count > 0 ? '<button onclick="exportStrumis(\'' + d.bid_number + '\')"> EXPORT TO STRUMIS</button>' : '')
          + ((d.pdf_path || window._lastPdfPath) ? '<button onclick="detectMiscSteel(\'' + d.bid_number + '\')">🪜 DETECT MISC STEEL</button>' : '')
          + (d.member_count > 0 ? '<button onclick="searchSimilarProjects(\'' + escapeHtml(d.project_name || d.bid_number || '') + '\')">SIMILAR PROJECTS</button>' : '')
          + (d.member_count > 0 ? '<button onclick="openWorkbench()">REVIEW WORKBENCH</button>' : '');
        lastMsg.appendChild(actDiv);
      }
      return d;
    } else {
      appendMsg('ai', '⚠ Auto-pipeline: no members extracted.', null, 'LOCAL/auto-pipeline');
    }
  } catch (e) {
    console.warn('auto-process error:', e);
  }
  return null;
}

// Chat artifact buttons - render after AI responses that produce a PDF/STL
function attachArtifactButtons(messageEl, artifactInfo) {
  if (!messageEl || !artifactInfo) return;
  const div = document.createElement('div');
  div.className = 'artifact-actions';
  const bn = artifactInfo.bid_number || '';
  const pn = artifactInfo.project_name || '';
  const fn = artifactInfo.filename || 'document.pdf';
  div.innerHTML =
      '<button onclick="saveArtifactToBids(\'' + bn + '\',\'' + fn + '\',\'' + pn + '\')"> SAVE TO BIDS FOLDER</button>'
    + '<button onclick="openBidsFolder(\'' + bn + '\',\'' + pn + '\')">OPEN FOLDER</button>'
    + (fn.endsWith('.pdf') ? '<button onclick="downloadArtifact(\'' + bn + '\',\'' + fn + '\')">⬇ DOWNLOAD</button>' : '');
  messageEl.appendChild(div);
}

async function saveArtifactToBids(bidNumber, filename, projectName) {
  showToast('Saving ' + filename + ' to Bids folder…', 'info', 1500);
  // The actual save happens server-side when the bridge generates the artifact.
  // This button is mostly a confirmation + opens the folder.
  await openBidsFolder(bidNumber, projectName);
}

async function downloadArtifact(bidNumber, filename) {
  // Open folder with the file selected
  const a = api(); if (!a) return;
  const list = await a.list_bid_artifacts(bidNumber, '');
  if (list.ok && list.data.artifacts) {
    const f = list.data.artifacts.find(x => x.name === filename);
    if (f) {
      await a.open_bids_folder(bidNumber, '');
      showToast('Opened folder. ' + filename + ' is highlighted.', 'success', 3000);
      return;
    }
  }
  showToast('Artifact not found yet. Generate it first.', 'info');
}

// ── Generate 3D model from natural language ──
async function generate3DModel(shape, lengthFt, count) {
  const a = api();
  if (!a) { appendMsg('ai', 'Bridge not connected', 'error'); return; }
  
  appendMsg('ai', '', 'loading');
  try {
    const r = await a.generate_3d_view(shape || 'W14X82', lengthFt || 20, count || 1);
    removeLoading();
    if (r.ok) {
      const d = r.data;
      loadStlBase64(d.stl_b64, d.label);
      appendMsg('ai',
        ' 3D model generated locally from AISC data\n' +
        '• Shape: ' + d.shape + '\n' +
        '• Length: ' + d.length_ft + ' ft\n' +
        '• Weight: ' + d.weight_lbs.toLocaleString() + ' lbs (' + d.weight_tons.toFixed(2) + ' tons)\n' +
        '• Depth: ' + d.depth_in + '″ · Flange: ' + d.flange_in + '″\n' +
        '• Members: ' + d.member_count + '\n' +
        '• STL size: ' + (d.stl_bytes / 1024).toFixed(0) + ' KB\n\n' +
        'Drag to rotate · Scroll to zoom · Right-drag to pan',
        null, 'LOCAL/aisc-calc');
    } else {
      appendMsg('ai', '3D error: ' + r.error, 'error');
    }
  } catch (e) {
    removeLoading();
    appendMsg('ai', '3D error: ' + e.message, 'error');
  }
}

// ── GUIDED TOUR SYSTEM ───────────────────────────────────────────
// Auto-runs on FIRST LAUNCH ONLY. Persisted via bridge → JSON file.
// Skippable. Restartable from Settings → About → "Restart Tour".

const TOUR_STEPS = [
  {
    title: "WELCOME TO VIRTUAL OFFICE",
    body: "This is your AI-powered command center for structural steel operations. Let me show you around. This takes about 60 seconds.<br><br>You can <strong>skip this tour</strong> at any time and restart it later from Settings.",
    target: null,    // centered welcome - no spotlight
  },
  {
    title: "KPI STRIP",
    body: "The top bar shows your live KPIs at a glance: <strong>active tonnage</strong>, <strong>pipeline value</strong>, <strong>blockers</strong>, <strong>active jobs</strong>, <strong>win streak</strong>, and <strong>time saved</strong> by automation.<br><br>Trend arrows (▲▼) show week-over-week changes.",
    target: '.kpi-strip',
    mode: 'status',
    placement: 'bottom',
  },
  {
    title: "MODE BAR",
    body: "Six tabs control what you see: <kbd>1</kbd> STATUS, <kbd>2</kbd> CHAT, <kbd>3</kbd> FIELD, <kbd>4</kbd> MODEL, <kbd>5</kbd> SETTINGS, <kbd>6</kbd> CONTROLS.<br><br>Keyboard shortcuts work anywhere except inside a text field.",
    target: '.mode-bar',
    mode: 'status',
    placement: 'bottom',
  },
  {
    title: "CHAT - YOUR AI ASSISTANT",
    body: "This is where you talk to the system. Type naturally. No commands to memorize.<br><br>Try: <kbd>morning brief</kbd> · <kbd>estimate 500 tons</kbd> · <kbd>who owes us?</kbd> · <kbd>steel prices</kbd><br><br>Drop PDFs here for automatic takeoffs and 3D model generation.",
    target: '#btn-chat',
    mode: 'chat',
    placement: 'bottom',
  },
  {
    title: "ACTIVE PRIORITIES",
    body: "The right sidebar shows your <strong>active priorities</strong>, <strong>recommended bids</strong>, and <strong>SMS channel</strong>.<br><br>Each bid card has <strong>PURSUE</strong> / <strong>DETAILS</strong> / <strong>PASS</strong> buttons for instant decisions. No typing needed.",
    target: '#mgrid', // rsb removed, tour targets center grid
    mode: 'status',
    placement: 'left',
  },
  {
    title: "FIELD MODE",
    body: "Switch to the <strong> Field</strong> tab for a simplified, touch-friendly interface designed for job sites. Log production, take photos, generate quick estimates without internet.",
    target: '#btn-field',
    mode: 'status',
    placement: 'bottom',
  },
  {
    title: "MODEL TAB",
    body: "The new <strong>MODEL</strong> tab is your 3D viewer + bid documents folder. When you drop a structural drawing PDF in CHAT, the system auto-extracts members from AISC and saves everything to <kbd>Documents/Your Company Bids/</kbd>.<br><br>Click any recent bid to load its 3D model.",
    target: '#btn-model',
    mode: 'status',
    placement: 'bottom',
  },
  {
    title: "SETTINGS",
    body: "The <strong> Settings</strong> tab lets you configure API keys, edit bid rates, manage integrations, export data backups, and switch bid output templates.<br><br>Find the <strong>Restart Tour</strong> button here anytime.",
    target: '#btn-settings',
    mode: 'status',
    placement: 'bottom',
  },
  {
    title: "YOU'RE READY",
    body: "Start by typing <kbd>morning brief</kbd> to see your daily intelligence report. Steel prices, pipeline, compliance, blockers, and shop status all in one view.<br><br><strong>Welcome to Your Company Virtual Office.</strong>",
    target: null,    // centered finish
  },
];

let tourStep = 0;
let tourOverlay = null;
let tourSpotlight = null;
let tourCard = null;

function renderTourStep() {
  // Lazy-create overlay + spotlight + card on first render
  if (!tourOverlay) {
    tourOverlay = document.createElement('div');
    tourOverlay.className = 'tour-overlay';
    document.body.appendChild(tourOverlay);
  }
  if (!tourSpotlight) {
    tourSpotlight = document.createElement('div');
    tourSpotlight.className = 'tour-spotlight';
    tourSpotlight.style.display = 'none';
    document.body.appendChild(tourSpotlight);
  }
  if (!tourCard) {
    tourCard = document.createElement('div');
    tourCard.className = 'tour-card';
    document.body.appendChild(tourCard);
  }

  const s = TOUR_STEPS[tourStep];
  const total = TOUR_STEPS.length;
  const isLast = tourStep === total - 1;

  // Build dots
  let dots = '<div class="tour-dots">';
  for (let i = 0; i < total; i++) {
    const cls = i < tourStep ? 'done' : i === tourStep ? 'active' : '';
    dots += `<div class="tour-dot ${cls}"></div>`;
  }
  dots += '</div>';

  // Build card content (arrow added later based on placement)
  tourCard.innerHTML = `
    <div class="tour-step-num">STEP ${tourStep + 1} OF ${total}</div>
    ${dots}
    <div class="tour-title">${s.title}</div>
    <div class="tour-body">${s.body}</div>
    <div class="tour-btns">
      <button class="tour-btn ghost" onclick="endTour()">${isLast ? 'CLOSE' : 'SKIP TOUR'}</button>
      ${!isLast
        ? `<button class="tour-btn primary" onclick="nextTourStep()">NEXT →</button>`
        : `<button class="tour-btn primary" onclick="endTour()">GET STARTED</button>`}
    </div>
  `;

  // If the step calls for a different mode, switch to it before measuring
  // (e.g., the CHAT step needs CHAT mode visible). Skip if already there.
  if (s.mode && document.getElementById('shell').dataset.mode !== s.mode) {
    setMode(s.mode);
  }

  // Show overlay
  tourOverlay.classList.add('active');

  // Position spotlight + card based on target
  const target = s.target ? document.querySelector(s.target) : null;
  if (target) {
    tourOverlay.classList.remove('no-target');
    positionSpotlight(target, s.placement || 'auto');
  } else {
    // Centered welcome/finish - no spotlight, card centered
    tourOverlay.classList.add('no-target');
    tourSpotlight.style.display = 'none';
    tourCard.style.position = 'fixed';
    tourCard.style.top  = '50%';
    tourCard.style.left = '50%';
    tourCard.style.transform = 'translate(-50%, -50%)';
  }
}

function positionSpotlight(target, placement) {
  // Get target bounding rect (in viewport coordinates)
  const rect = target.getBoundingClientRect();
  const pad = 8;  // breathing room around the target

  // Position the spotlight rectangle around the target
  tourSpotlight.style.display = 'block';
  tourSpotlight.style.top    = (rect.top - pad) + 'px';
  tourSpotlight.style.left   = (rect.left - pad) + 'px';
  tourSpotlight.style.width  = (rect.width  + pad * 2) + 'px';
  tourSpotlight.style.height = (rect.height + pad * 2) + 'px';

  // Decide where to place the card relative to the spotlight
  // Auto-pick best side based on available space
  const cardW = 380, cardH = 240;  // approximate card size
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let side = placement;
  if (side === 'auto') {
    const spaceBelow = vh - rect.bottom;
    const spaceAbove = rect.top;
    const spaceRight = vw - rect.right;
    const spaceLeft  = rect.left;
    if      (spaceBelow >= cardH + 30) side = 'bottom';
    else if (spaceAbove >= cardH + 30) side = 'top';
    else if (spaceRight >= cardW + 30) side = 'right';
    else if (spaceLeft  >= cardW + 30) side = 'left';
    else                                side = 'bottom';   // best-effort
  }

  tourCard.style.position = 'fixed';
  tourCard.style.transform = 'none';
  let top, left;
  switch (side) {
    case 'bottom':
      top  = Math.min(rect.bottom + 16, vh - cardH - 12);
      left = Math.max(12, Math.min(rect.left + rect.width / 2 - cardW / 2, vw - cardW - 12));
      break;
    case 'top':
      top  = Math.max(12, rect.top - cardH - 16);
      left = Math.max(12, Math.min(rect.left + rect.width / 2 - cardW / 2, vw - cardW - 12));
      break;
    case 'right':
      top  = Math.max(12, Math.min(rect.top + rect.height / 2 - cardH / 2, vh - cardH - 12));
      left = Math.min(rect.right + 16, vw - cardW - 12);
      break;
    case 'left':
      top  = Math.max(12, Math.min(rect.top + rect.height / 2 - cardH / 2, vh - cardH - 12));
      left = Math.max(12, rect.left - cardW - 16);
      break;
  }
  tourCard.style.top  = top  + 'px';
  tourCard.style.left = left + 'px';

  // Add an arrow pointing back at the highlighted element
  // (remove any existing arrow first)
  const existing = tourCard.querySelector('.tour-arrow');
  if (existing) existing.remove();
  const arrow = document.createElement('div');
  arrow.className = 'tour-arrow ' + (
    side === 'bottom' ? 'up' :
    side === 'top'    ? 'down' :
    side === 'right'  ? 'left' :
                        'right'
  );
  tourCard.appendChild(arrow);

  // If the target is offscreen (e.g., needs scroll), bring it into view
  if (rect.top < 0 || rect.bottom > vh) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function endTour() {
  // Three elements live as siblings of body: overlay, spotlight, card.
  // Explicitly hide all three - relying on .active class alone is not enough
  // because .no-target (added on the last step) outranks .tour-overlay's
  // default display:none via CSS specificity, and the spotlight + card are
  // separate elements with their own state.
  if (tourOverlay) {
    tourOverlay.classList.remove('active');
    tourOverlay.classList.remove('no-target');
    tourOverlay.style.display = 'none';
  }
  if (tourSpotlight) {
    tourSpotlight.style.display = 'none';
  }
  if (tourCard) {
    tourCard.style.display = 'none';
  }
  // Save "tour completed" to persistent storage via bridge
  const a = api();
  if (a) { a.set_user_pref('tour_completed', 'true').catch(()=>{}); }
}

function nextTourStep() {
  tourStep++;
  if (tourStep >= TOUR_STEPS.length) { endTour(); return; }
  renderTourStep();
}

function startTour() {
  tourStep = 0;
  // If a prior endTour() forced display:none inline, clear it so the
  // CSS class rules drive visibility again.
  if (tourOverlay) tourOverlay.style.display = '';
  if (tourCard)    tourCard.style.display = '';
  // tourSpotlight is intentionally left hidden here - renderTourStep
  // and positionSpotlight will show it again when there's a target.
  renderTourStep();
}

async function checkFirstLaunchTour() {
  const a = api();
  if (!a) { setTimeout(checkFirstLaunchTour, 2000); return; }
  try {
    // "Run tour on next startup" toggle overrides tour_completed
    const rNext = await a.get_user_pref('run_tour_next_launch');
    if (rNext && rNext.ok && rNext.data && rNext.data.value === 'true') {
      // Reset immediately so it only fires once; checkbox will reflect false
      a.set_user_pref('run_tour_next_launch', 'false').catch(()=>{});
      setTimeout(startTour, 1500);
      return;
    }
    const r = await a.get_user_pref('tour_completed');
    if (r && r.ok && r.data && r.data.value === 'true') {
      return; // Already completed - skip
    }
    // First launch
    setTimeout(startTour, 1500);
  } catch(e) {
    setTimeout(startTour, 2000);
  }
}

async function loadTourToggle() {
  const a = api(); if (!a) return;
  try {
    const r = await a.get_user_pref('run_tour_next_launch');
    const cb = document.getElementById('sd-tour-next');
    if (cb && r && r.ok && r.data) cb.checked = r.data.value === 'true';
  } catch(e) {}
}

async function saveTourToggle(checked) {
  const a = api(); if (!a) return;
  try {
    await a.set_user_pref('run_tour_next_launch', checked ? 'true' : 'false');
    showToast(checked ? 'Tour runs on next startup' : 'Tour startup disabled', 'info', 2000);
  } catch(e) { showToast('Pref save error', 'error'); }
}

// P11.3: debug health-card stress-test (only visible when DEBUG_MODE=1)
async function simulateHandlerError() {
  const a = api(); if (!a) return;
  try {
    const r = await a.debug_force_handler_error();
    appendMsg('ai', (r && r.error) || 'Error simulated. Health card should flip yellow within 60s.', null, 'LOCAL/debug');
    setTimeout(updateHealthCard, 2000);
  } catch(e) { showToast('Simulate failed: ' + e, 'error'); }
}

async function loadDebugPanel() {
  const a = api(); if (!a) return;
  try {
    const r = await a.is_debug_mode();
    if (r && r.ok && r.data && r.data.debug) {
      const el = document.getElementById('debug-health-row');
      if (el) el.style.display = '';
    }
  } catch(e) { /* best-effort */ }
}

// ── BID OUTPUT TEMPLATE SYSTEM ───────────────────────────────────
// Templates define the output format for generated bid proposals.
// Switchable via chat ("switch to formal template") or Settings button.

const BID_TEMPLATES = {
  STANDARD: {
    name: "Standard",
    desc: "Professional bid with scope, pricing table, terms. Your Company letterhead",
    sections: ["header","scope","member_schedule","pricing_table","exclusions","terms","signature"],
  },
  SIMPLE: {
    name: "Simple Quote",
    desc: "One-page budget quote. Tonnage, rate, total, timeline",
    sections: ["header","summary_line","total","timeline","signature"],
  },
  DETAILED: {
    name: "Detailed Estimate",
    desc: "Full breakdown: member-by-member weights, labor hours, material costs, markups",
    sections: ["header","scope","member_schedule","weight_summary","labor_breakdown","material_costs","equipment","markup_table","exclusions","alternates","terms","signature"],
  },
  REFINERY: {
    name: "Refinery / Industrial",
    desc: "PLA-compliant with safety plan reference, DISA/ISN compliance, prevailing wage",
    sections: ["header","scope","compliance_matrix","member_schedule","pricing_table","safety_reference","pla_terms","insurance_certs","signature"],
  },
};

let activeBidTemplate = 'STANDARD';

function cycleBidTemplate() {
  const keys = Object.keys(BID_TEMPLATES);
  const idx = keys.indexOf(activeBidTemplate);
  activeBidTemplate = keys[(idx + 1) % keys.length];
  const tpl = BID_TEMPLATES[activeBidTemplate];
  document.getElementById('tpl-active').textContent = tpl.name.toUpperCase();
  showToast(`Bid template: ${tpl.name} | ${tpl.desc}`, 'success', 3000);
  // Save preference
  const a = api();
  if (a) { a.set_user_pref('bid_template', activeBidTemplate).catch(()=>{}); }
}

async function loadBidTemplate() {
  const a = api();
  if (!a) return;
  try {
    const r = await a.get_user_pref('bid_template');
    if (r && r.ok && r.data && r.data.value && BID_TEMPLATES[r.data.value]) {
      activeBidTemplate = r.data.value;
      const el = document.getElementById('tpl-active');
      if (el) el.textContent = BID_TEMPLATES[activeBidTemplate].name.toUpperCase();
    }
  } catch(e) {}
}

// ── BOOT ─────────────────────────────────────────────────────────
startClock();
populateExtras();
populateKPIs();
updateAddictionKPIs();
init().catch(()=>{populateKPIs();loadSmsStatus();});
setTimeout(loadSmsStatus,1500);
setTimeout(loadBidTemplate,2000);
setTimeout(checkFirstLaunchTour,3000);

// Pull version from the bridge so Settings always reflects the build
// (otherwise stale strings drift across releases - caught by Joseph's audit).
async function loadAppVersion(){
  const a = api(); if (!a) { setTimeout(loadAppVersion, 2000); return; }
  try {
    const r = await a.version();
    const el = document.getElementById('sd-version');
    if (el && r && r.ok && r.data && r.data.version) {
      el.textContent = 'v' + r.data.version;
    }
  } catch(e) { /* best-effort */ }
}
async function loadFredStatus(){
  const a = api(); if (!a) { setTimeout(loadFredStatus, 2000); return; }
  try {
    const r = await a.fred_key_status();
    const el = document.getElementById('ss-fred');
    if (el && r && r.ok) {
      el.className = 'set-status ' + (r.data && r.data.has_key ? 'ok' : 'no');
    }
  } catch(e) { /* best-effort */ }
}
setTimeout(loadAppVersion, 1000);
setTimeout(loadFredStatus, 1200);
setTimeout(checkApiKeyStatus, 1300);
setTimeout(updateHealthCard, 1500);
setTimeout(loadBidRatesDisplay, 1600);
setTimeout(loadTourToggle, 1800);
setTimeout(loadDebugPanel, 1900);
setTimeout(loadTunnelStatus, 2500);

// ── BID CARD CLICK EXPAND ────────────────────────────────────────
document.querySelectorAll('.bcard').forEach(c=>{
  c.addEventListener('click',function(e){
    if(e.target.tagName==='BUTTON')return; // Don't toggle when clicking PURSUE/PASS
    this.classList.toggle('expanded');
  });
});
// == PROJECT CONTROLS VIEW (PC4+PC5) ==============================
// SPI/CPI dashboard fed by get_spi_cpi / get_forecast_to_complete /
// get_variance_by_cost_code. CONFIDENTIAL - INTERNAL, never client-facing.

function pcEsc(s){
  return String(s==null?'':s).replace(/[&<>"']/g,
    c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function pcMoney(v){
  if(v==null)return '-';
  const r=Math.round(v);
  return (r<0?'-$':'$')+Math.abs(r).toLocaleString('en-US');
}
function pcIdx(v){
  if(v==null)return '<span class="pc-na">-</span>';
  // Three decimals to match the backend rounding; two would display a
  // flagged 0.949 as "0.95" right beside a "below 0.95" reason line.
  const cls=v<0.95?'pc-bad':(v<1?'pc-warn':'pc-good');
  return '<span class="'+cls+'">'+v.toFixed(3)+'</span>';
}

let _pcReqSeq=0;
async function refreshControls(){
  const empty=document.getElementById('pc-empty');
  const body=document.getElementById('pc-body');
  const a=api();
  if(!a){
    // Say so: a silent return left the view header-only blank when
    // pywebview had not attached yet.
    empty.style.display='block'; body.style.display='none';
    empty.innerHTML='<div class="pc-empty-title">BRIDGE NOT CONNECTED</div>'+
      '<div class="pc-empty-sub">pywebview has not attached yet. Press '+
      'Enter on the project code to retry.</div>';
    return;
  }
  // In-flight guard: only the most recent load may touch the DOM, or a
  // slow response for project A overwrites a newer load of project B.
  const seq=++_pcReqSeq;
  const pid=(document.getElementById('pc-project-id').value||'').trim();
  if(!pid){
    empty.style.display='block'; body.style.display='none';
    empty.innerHTML='<div class="pc-empty-title">ENTER A PROJECT CODE</div>'+
      '<div class="pc-empty-sub">Awarded project code, for example PRJ-2026-ACP-001.</div>';
    return;
  }
  empty.style.display='block'; body.style.display='none';
  empty.innerHTML='<div class="pc-empty-title">LOADING '+pcEsc(pid)+'...</div>';
  let spi,ftc,vbc;
  try{
    [spi,ftc,vbc]=await Promise.all([
      a.get_spi_cpi(pid), a.get_forecast_to_complete(pid),
      a.get_variance_by_cost_code(pid)]);
  }catch(e){
    if(seq!==_pcReqSeq)return;
    empty.innerHTML='<div class="pc-empty-title">BRIDGE ERROR</div>'+
      '<div class="pc-empty-sub">'+pcEsc(e.message)+'</div>';
    return;
  }
  if(seq!==_pcReqSeq)return;
  if(!spi||!spi.ok){
    const err=(spi&&spi.error)||'no response';
    empty.innerHTML='<div class="pc-empty-title">NO CONTROLS DATA YET</div>'+
      '<div class="pc-empty-sub">'+pcEsc(err)+'</div>'+
      '<div class="pc-empty-note">SPI/CPI needs the PC1 frozen baseline xlsx '+
      '(award-to-budget) and the PC3 shop progress log. Both are read-only '+
      'inputs; this screen never invents numbers.</div>';
    return;
  }
  empty.style.display='none'; body.style.display='flex';
  // The PC6 hierarchy beside the flags comes from the backend payload so
  // the screen cannot drift from bridge/project_controls.py; the static
  // index.html text is only the pre-load fallback.
  const hier=spi.data.pc6_hierarchy||'';
  const hierEl=document.getElementById('pc-pc6-static');
  if(hierEl&&hier)hierEl.textContent=hier;
  renderControlsKpis(spi.data, ftc);
  renderControlsWarnings(spi.data, ftc, vbc);
  drawScurve(spi.data.scurve||[]);
  renderControlsFlags(spi.data.flags||[], hier);
  renderVarianceTable(vbc);
  const src=document.getElementById('pc-sources');
  const ds=spi.data.data_sources||{};
  src.innerHTML='SOURCES · baseline: '+pcEsc(ds.pc1_baseline_xlsx||'-')+
    ' · progress: '+pcEsc(ds.pc3_progress_db||'-')+
    ' · cost basis: '+pcEsc(ds.cost_basis||'-')+
    ' · as of '+pcEsc(spi.data.as_of||'-');
}

function renderControlsKpis(d, ftcEnv){
  const p=d.project||{};
  const cells=[
    ['PROJECT SPI', pcIdx(p.spi)],
    ['PROJECT CPI', pcIdx(p.cpi)],
    ['EARNED', pcMoney(p.ev)],
    ['PLANNED TO DATE', pcMoney(p.pv)],
    ['ACTUAL (HRS BASIS)', pcMoney(p.ac)],
    ['BUDGET (BAC)', pcMoney(p.bac)],
  ];
  document.getElementById('pc-kpis').innerHTML=cells.map(c=>
    '<div class="pc-kpi"><div class="pc-kpi-v">'+c[1]+'</div>'+
    '<div class="pc-kpi-l">'+c[0]+'</div></div>').join('');
  const fc=document.getElementById('pc-forecast');
  if(ftcEnv&&!ftcEnv.ok){
    // Surface the backend's error and fix text instead of swallowing it.
    fc.innerHTML='<span class="pc-band pc-band-bad">FORECAST UNAVAILABLE</span> '+
      pcEsc(ftcEnv.error||'no response');
    return;
  }
  const f=ftcEnv&&ftcEnv.ok?ftcEnv.data:null;
  if(!f||!f.project){ fc.innerHTML=''; return; }
  const fp=f.project;
  const inv=fp.status==='INVESTIGATE';
  fc.innerHTML='<span class="pc-band '+(inv?'pc-band-bad':'pc-band-ok')+'">'+
    'FORECAST '+pcEsc(fp.status)+'</span> EAC '+pcMoney(fp.eac)+
    ' vs BAC '+pcMoney(fp.bac)+' · variance '+
    (fp.forecast_variance_pct>0?'+':'')+fp.forecast_variance_pct+
    '% · control limits '+fp.control_limits.low_pct+'% / +'+
    fp.control_limits.high_pct+'% (Section 07)'+
    (inv?'<div class="pc-pc6" style="margin-top:6px">'+pcEsc(fp.action||'')+'</div>':'');
}

function renderControlsWarnings(spiD, ftcEnv, vbcEnv){
  // All three Bridge methods return a warnings array naming excluded
  // lines and data gaps. Dropping them hides exactly what the backend
  // promises never to drop silently, so they render here, deduplicated.
  const host=document.getElementById('pc-warnings');
  if(!host)return;
  const seen=new Set(), all=[];
  [(spiD&&spiD.warnings)||[],
   (ftcEnv&&ftcEnv.ok&&ftcEnv.data&&ftcEnv.data.warnings)||[],
   (vbcEnv&&vbcEnv.ok&&vbcEnv.data&&vbcEnv.data.warnings)||[]]
    .flat().forEach(w=>{if(w&&!seen.has(w)){seen.add(w);all.push(w);}});
  if(!all.length){host.style.display='none';host.innerHTML='';return;}
  host.style.display='block';
  host.innerHTML='<div class="pc-warn-title">DATA WARNINGS ('+all.length+')</div>'+
    all.map(w=>'<div class="pc-warn-item">'+pcEsc(w)+'</div>').join('');
}

function drawScurve(series){
  const host=document.getElementById('pc-scurve-host');
  if(!series.length){
    host.innerHTML='<div class="pc-empty-sub">No dated baseline lines yet; '+
      'the S-curve needs start and end dates per WBS line.</div>';
    return;
  }
  const W=560,H=240,PL=58,PR=12,PT=12,PB=30;
  const max=Math.max(1,...series.map(p=>Math.max(p.planned||0,p.earned||0,p.actual||0)));
  const xs=i=>PL+(W-PL-PR)*(series.length===1?0.5:i/(series.length-1));
  const ys=v=>PT+(H-PT-PB)*(1-v/max);
  const line=(key,color,dash)=>{
    const coords=series.map((p,i)=>p[key]==null?null:xs(i).toFixed(1)+','+ys(p[key]).toFixed(1))
      .filter(Boolean);
    if(!coords.length)return '';
    if(coords.length===1){
      // A one-point polyline draws nothing; show week one as a dot.
      const c=coords[0].split(',');
      return '<circle cx="'+c[0]+'" cy="'+c[1]+'" r="3" fill="'+color+'"/>';
    }
    return '<polyline points="'+coords.join(' ')+'" fill="none" stroke="'+color+
      '" stroke-width="2"'+(dash?' stroke-dasharray="5 4"':'')+'/>';
  };
  let grid='';
  for(let g=0;g<=4;g++){
    const v=max*g/4, y=ys(v).toFixed(1);
    grid+='<line x1="'+PL+'" y1="'+y+'" x2="'+(W-PR)+'" y2="'+y+
      '" stroke="rgba(255,255,255,0.07)"/>'+
      '<text x="'+(PL-6)+'" y="'+(+y+3)+'" text-anchor="end" class="pc-ax">$'+
      Math.round(v/1000).toLocaleString('en-US')+'k</text>';
  }
  const first=series[0].week_ending, last=series[series.length-1].week_ending;
  host.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" class="pc-svg">'+grid+
    line('planned','#4FC3F7',true)+line('earned','#34d399',false)+
    line('actual','#ff5f00',false)+
    '<text x="'+PL+'" y="'+(H-8)+'" class="pc-ax">'+pcEsc(first)+'</text>'+
    '<text x="'+(W-PR)+'" y="'+(H-8)+'" text-anchor="end" class="pc-ax">'+
    pcEsc(last)+'</text></svg>'+
    '<div class="pc-legend">'+
    '<span><i style="background:#4FC3F7"></i>PLANNED</span>'+
    '<span><i style="background:#34d399"></i>EARNED</span>'+
    '<span><i style="background:#ff5f00"></i>ACTUAL (HRS BASIS)</span></div>';
}

function renderControlsFlags(flags, hier){
  const host=document.getElementById('pc-flags');
  if(!flags.length){
    host.innerHTML='<div class="pc-empty-sub">No flags. All computable lines '+
      'are at or above 0.95 on both indexes.</div>';
    return;
  }
  host.innerHTML=flags.map(f=>{
    const cls=f.type==='performance'?'pc-flag-perf':'pc-flag-data';
    // Backend notes minus the hierarchy line already shown above the
    // list; the literal is only the fallback if notes are absent.
    const notice=(f.notes||[]).filter(n=>n&&n!==hier).join(' ')||
      'Client-caused variance: consider notice per the contract-admin workflow.';
    return '<div class="pc-flag '+cls+'">'+
      '<div class="pc-flag-hd"><b>'+pcEsc(f.wbs_line)+'</b> · '+
      pcEsc(f.cost_code)+' · SPI '+(f.spi==null?'-':f.spi.toFixed(3))+
      ' · CPI '+(f.cpi==null?'-':f.cpi.toFixed(3))+
      ' <span class="pc-conf pc-conf-'+pcEsc(f.confidence)+'">'+
      pcEsc(f.confidence).toUpperCase()+'</span>'+
      (f.client_caused?' <span class="pc-client">CLIENT-CAUSED</span>':'')+
      '</div>'+
      '<div class="pc-flag-why">'+pcEsc(f.reason)+'</div>'+
      (f.client_caused?'<div class="pc-flag-notice">'+pcEsc(notice)+'</div>':'')+
      '</div>';
  }).join('');
}

function renderVarianceTable(vbcEnv){
  const host=document.getElementById('pc-variance');
  if(vbcEnv&&!vbcEnv.ok){
    host.innerHTML='<div class="pc-empty-sub">'+pcEsc(vbcEnv.error||'no response')+'</div>';
    return;
  }
  const d=vbcEnv&&vbcEnv.ok?vbcEnv.data:null;
  if(!d||!d.codes||!d.codes.length){
    host.innerHTML='<div class="pc-empty-sub">No cost code data.</div>';
    return;
  }
  const rows=d.codes.map(c=>{
    let h='<tr class="'+(c.flagged?'pc-row-flag':'')+'">'+
      '<td>'+pcEsc(c.cost_code)+(c.client_caused?' <span class="pc-client">CLIENT-CAUSED</span>':'')+'</td>'+
      '<td>'+pcMoney(c.bac)+'</td><td>'+pcMoney(c.pv)+'</td>'+
      '<td>'+pcMoney(c.ev)+'</td><td>'+pcMoney(c.ac)+'</td>'+
      '<td>'+pcMoney(c.schedule_variance)+'</td>'+
      '<td>'+pcMoney(c.cost_variance)+'</td>'+
      '<td>'+pcIdx(c.spi)+'</td><td>'+pcIdx(c.cpi)+'</td></tr>';
    if(c.client_caused){
      // The notice note must show even when the code is not flagged;
      // the flags panel only carries below-0.95 and low-confidence lines.
      h+='<tr class="pc-note-row"><td colspan="9">'+
        pcEsc((c.notes&&c.notes.length)?c.notes.join(' '):
          'Client-caused variance: consider notice per the contract-admin workflow.')+
        '</td></tr>';
    }
    return h;
  }).join('');
  host.innerHTML='<table class="pc-table"><thead><tr>'+
    '<th>COST CODE</th><th>BAC</th><th>PV</th><th>EV</th><th>AC</th>'+
    '<th>SV</th><th>CV</th><th>SPI</th><th>CPI</th></tr></thead>'+
    '<tbody>'+rows+'</tbody></table>';
}
