/**
 * Local logic tests for Code.gs and Setup.gs. No Google account needed.
 * Run: node test/run_tests.js (from the appsscript folder)
 *
 * Loads the .gs sources into a Node vm context with mocked GAS services
 * (SpreadsheetApp, DriveApp, Utilities, LockService, PropertiesService,
 * ContentService, Session, Logger) and exercises the web app handlers
 * against the Step 1 acceptance checklist items that are testable
 * without a deployment.
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = path.dirname(__dirname === '.' ? process.cwd() : __dirname);
const CODE = fs.readFileSync(path.join(HERE, 'Code.gs'), 'utf8');
const SETUP = fs.readFileSync(path.join(HERE, 'Setup.gs'), 'utf8');

/* ---------------- GAS service mocks ---------------- */

class MockRange {
  constructor(sheet, row, col, numRows, numCols) {
    this.sheet = sheet; this.row = row; this.col = col;
    this.numRows = numRows; this.numCols = numCols;
  }
  getValues() {
    const out = [];
    for (let r = 0; r < this.numRows; r++) {
      const src = this.sheet.rows[this.row - 1 + r] || [];
      const line = [];
      for (let c = 0; c < this.numCols; c++) {
        const v = src[this.col - 1 + c];
        line.push(v === undefined ? '' : v);
      }
      out.push(line);
    }
    return out;
  }
  setValues(vals) {
    for (let r = 0; r < vals.length; r++) {
      for (let c = 0; c < vals[r].length; c++) {
        this.sheet.put(this.row + r, this.col + c, vals[r][c]);
      }
    }
    return this;
  }
  setValue(v) { this.sheet.put(this.row, this.col, v); return this; }
  setFontWeight() { return this; }
}

// Real Sheets parses values written via appendRow and setValue the way
// typing into a cell would: 'TRUE'/'FALSE' strings become booleans and
// bare yyyy-mm-dd strings become Date objects at midnight in the
// spreadsheet timezone. Without this coercion the harness tests a
// string-typed world that never exists after deployment, and the
// String(...).toUpperCase() and instanceof Date defenses in Code.gs
// would be dead code under test.
function sheetsCoerce(v) {
  if (typeof v !== 'string') return v;
  if (/^true$/i.test(v)) return true;
  if (/^false$/i.test(v)) return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return v;
}

class MockSheet {
  constructor(name) { this.name = name; this.rows = []; this.frozen = 0; }
  getName() { return this.name; }
  setName(n) { this.name = n; return this; }
  put(row, col, v) {
    while (this.rows.length < row) this.rows.push([]);
    const line = this.rows[row - 1];
    while (line.length < col) line.push('');
    line[col - 1] = sheetsCoerce(v);
  }
  appendRow(r) { this.rows.push(r.map(sheetsCoerce)); return this; }
  getLastRow() { return this.rows.length; }
  getDataRange() {
    const w = Math.max(1, ...this.rows.map(r => r.length));
    return new MockRange(this, 1, 1, Math.max(this.rows.length, 1), w);
  }
  getRange(row, col, numRows, numCols) {
    return new MockRange(this, row, col, numRows || 1, numCols || 1);
  }
  setFrozenRows(n) { this.frozen = n; return this; }
}

class MockSpreadsheet {
  constructor(name, id) {
    this.name = name; this.id = id || 'ss-' + name.replace(/\W+/g, '-');
    this.sheets = [new MockSheet('Sheet1')];
  }
  getSheets() { return this.sheets; }
  getSheetByName(n) { return this.sheets.find(s => s.name === n) || null; }
  insertSheet(n) { const s = new MockSheet(n); this.sheets.push(s); return s; }
  getId() { return this.id; }
  getUrl() { return 'https://sheets.mock/' + this.id; }
}

class MockFolder {
  constructor(name, id) {
    this.name = name; this.id = id || 'folder-' + name.replace(/\W+/g, '-');
    this.folders = []; this.files = [];
  }
  getFoldersByName(n) {
    const m = this.folders.filter(f => f.name === n); let i = 0;
    return { hasNext: () => i < m.length, next: () => m[i++] };
  }
  createFolder(n) { const f = new MockFolder(n); this.folders.push(f); return f; }
  createFile(blob) {
    const folder = this;
    const file = { blob, getUrl: () => 'https://drive.mock/' + folder.name + '/' + encodeURIComponent(blob.name) };
    this.files.push(file);
    return file;
  }
  getId() { return this.id; }
}

function buildContext() {
  const env = {
    spreadsheets: {},
    folders: {},
    props: {},
    lock: { acquired: 0, released: 0 },
    logs: []
  };
  const ctx = {
    Array, JSON, Math, Number, String, Date, Error, Object, RegExp,
    SpreadsheetApp: {
      create: (name) => {
        const ss = new MockSpreadsheet(name);
        env.spreadsheets[ss.getId()] = ss;
        return ss;
      },
      openById: (id) => {
        if (!env.spreadsheets[id]) throw new Error('no spreadsheet ' + id);
        return env.spreadsheets[id];
      }
    },
    DriveApp: {
      getRootFolder: () => {
        if (!env.folders.root) env.folders.root = new MockFolder('My Drive', 'root');
        return env.folders.root;
      },
      getFolderById: (id) => {
        const all = [];
        const walk = (f) => { all.push(f); f.folders.forEach(walk); };
        if (env.folders.root) walk(env.folders.root);
        Object.values(env.folders).forEach(f => { if (f !== env.folders.root) walk(f); });
        const hit = all.find(f => f.getId() === id);
        if (!hit) throw new Error('no folder ' + id);
        return hit;
      }
    },
    Utilities: {
      DigestAlgorithm: { SHA_1: 'sha1' },
      Charset: { UTF_8: 'utf8' },
      computeDigest: (alg, val) => Array.from(crypto.createHash('sha1').update(val, 'utf8').digest()),
      base64Decode: (s) => Buffer.from(s, 'base64'),
      newBlob: (bytes, mime, name) => ({ bytes, mime, name }),
      getUuid: () => crypto.randomUUID(),
      formatDate: (d, tz, fmt) => {
        if (fmt !== 'yyyy-MM-dd') throw new Error('mock formatDate only supports yyyy-MM-dd, got ' + fmt);
        // Local components, matching a sheet whose timezone equals the
        // machine timezone. Coerced date cells are local midnight, so
        // UTC-based formatting would be off by one day.
        return d.getFullYear() + '-' +
          String(d.getMonth() + 1).padStart(2, '0') + '-' +
          String(d.getDate()).padStart(2, '0');
      }
    },
    LockService: {
      getScriptLock: () => ({
        waitLock: () => { env.lock.acquired++; },
        releaseLock: () => { env.lock.released++; }
      })
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (k) => (k in env.props ? env.props[k] : null),
        setProperties: (obj) => Object.assign(env.props, obj),
        deleteProperty(k) { delete env.props[k]; return this; }
      })
    },
    ContentService: {
      MimeType: { JSON: 'application/json' },
      createTextOutput: (s) => ({
        _content: s, _mime: '',
        setMimeType(m) { this._mime = m; return this; },
        getContent() { return this._content; }
      })
    },
    Session: { getScriptTimeZone: () => 'America/Chicago' },
    Logger: { log: (...a) => env.logs.push(a.map(String).join(' ')) }
  };
  vm.createContext(ctx);
  return { ctx, env };
}

/* ---------------- harness ---------------- */

const FAILS = [];
function check(name, cond, detail) {
  const status = cond ? 'PASS' : 'FAIL';
  console.log(`  [${status}] ${name}${detail ? ' ' + detail : ''}`);
  if (!cond) FAILS.push(name);
}

function post(ctx, payload) {
  const out = ctx.doPost({ postData: { contents: JSON.stringify(payload) } });
  return JSON.parse(out.getContent());
}
function get(ctx, params) {
  const out = ctx.doGet({ parameter: params });
  return JSON.parse(out.getContent());
}

const SECRET = 'test-secret-0123456789abcdef0123456789abcdef0123';

function freshWebApp() {
  const { ctx, env } = buildContext();
  vm.runInContext(CODE, ctx);
  const ss = new MockSpreadsheet('NC Site Diary SANDBOX', 'ss-sandbox');
  ss.sheets = [];
  ['RAW_MESSAGES', 'DIARY', 'ERRORS'].forEach(n => ss.insertSheet(n));
  ss.getSheetByName('RAW_MESSAGES').appendRow(
    ['msg_id', 'timestamp', 'source', 'chat_name_or_user', 'sender', 'body', 'media_link', 'processed']);
  ss.getSheetByName('DIARY').appendRow(
    ['date', 'project', 'supervisor', 'weather', 'work_summary', 'safety_notes', 'photos_link', 'approved', 'approved_ts']);
  ss.getSheetByName('ERRORS').appendRow(['timestamp', 'error']);
  env.spreadsheets['ss-sandbox'] = ss;
  const root = new MockFolder('Site Diary', 'drive-root');
  env.folders.root = root;
  env.props.SHEET_ID = 'ss-sandbox';
  env.props.SHARED_SECRET = SECRET;
  env.props.DRIVE_FOLDER = 'drive-root';
  return { ctx, env, ss, root };
}

const ENTRY = {
  secret: SECRET,
  sender: 'mario@yourcompany.example.com',
  project: 'Genius Kids STEM Academy (Katy)',
  date: '2026-06-10',
  weather: 'Clear',
  body: 'Set 8 of 12 columns line A. 6 guys. Lost 0 hours.'
};

/* ---------------- web app tests ---------------- */

console.log('secret gate:');
{
  const { ctx, ss } = freshWebApp();
  const r1 = get(ctx, { secret: 'wrong' });
  check('doGet wrong secret denied', r1.ok === false && r1.error === 'denied');
  const r2 = post(ctx, Object.assign({}, ENTRY, { secret: 'wrong' }));
  check('doPost wrong secret denied', r2.ok === false && r2.error === 'denied');
  check('wrong secret writes nothing', ss.getSheetByName('RAW_MESSAGES').getLastRow() === 1);
  const r3 = get(ctx, { secret: SECRET });
  check('health check ok with right secret', r3.ok === true && r3.service === 'nc-site-diary');
}

console.log('entry ingestion:');
{
  const { ctx, env, ss } = freshWebApp();
  const r = post(ctx, ENTRY);
  const raw = ss.getSheetByName('RAW_MESSAGES');
  check('submit ok', r.ok === true);
  check('exactly 1 row written', raw.getLastRow() === 2);
  const row = raw.rows[1];
  check('source = portal', row[2] === 'portal');
  check('sender is the email', row[4] === 'mario@yourcompany.example.com');
  check('timestamp is ISO', /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(row[1]));
  check('processed = FALSE (boolean on a real sheet)', row[7] === false);
  check('body carries DATE and WEATHER', row[5].includes('DATE: 2026-06-10') && row[5].includes('WEATHER: Clear'));
  const expectId = 'portal-' + crypto.createHash('sha1')
    .update([ENTRY.sender, ENTRY.date, ENTRY.body, ENTRY.weather, ''].join('|'), 'utf8').digest('hex').slice(0, 16);
  check('msg_id is sha1(sender|date|body|weather|uploadsDigest)', r.msg_id === expectId, `(${r.msg_id})`);
  check('lock acquired and released', env.lock.acquired === 1 && env.lock.released === 1);

  const r2 = post(ctx, ENTRY);
  check('identical resubmit returns dedupe', r2.ok === true && r2.dedupe === true);
  check('resubmit writes zero new rows', raw.getLastRow() === 2);
}

console.log('uploads:');
{
  const { ctx, ss, root } = freshWebApp();
  const photo = { name: 'col-line-a.jpg', mime: 'image/jpeg', kind: 'photo', data_b64: Buffer.from('fakejpg').toString('base64') };
  const voice = { name: 'memo.m4a', mime: 'audio/mp4', kind: 'voice', data_b64: Buffer.from('fakeaudio').toString('base64') };
  const r = post(ctx, Object.assign({}, ENTRY, { body: 'photo and voice run', voice_note: true, uploads: [photo, voice] }));
  check('upload submit ok', r.ok === true && r.media === 2);
  const photos = root.folders.find(f => f.name === 'Photos');
  const notes = root.folders.find(f => f.name === 'Voice Notes');
  check('photo landed in Photos', !!photos && photos.files.length === 1);
  check('voice landed in Voice Notes', !!notes && notes.files.length === 1);
  const mediaCell = ss.getSheetByName('RAW_MESSAGES').rows[1][6];
  check('media_link holds both Drive URLs', mediaCell.includes('drive.mock/Photos/') && mediaCell.includes('drive.mock/Voice Notes/'));

  const pdf = { name: 'doc.pdf', mime: 'application/pdf', kind: 'photo', data_b64: 'aGk=' };
  const r2 = post(ctx, Object.assign({}, ENTRY, { body: 'pdf try', uploads: [pdf] }));
  check('non-image non-audio MIME rejected', r2.ok === false && /not allowed/.test(r2.error));
  const sneaky = { name: 'note.jpg', mime: 'image/jpeg', kind: 'voice', data_b64: 'aGk=' };
  const r3 = post(ctx, Object.assign({}, ENTRY, { body: 'kind mismatch', uploads: [sneaky] }));
  check('voice upload with image MIME rejected', r3.ok === false);
  const big = { name: 'huge.jpg', mime: 'image/jpeg', kind: 'photo', data_b64: 'A'.repeat(Math.ceil(25 * 1024 * 1024 * 4 / 3) + 8) };
  const r4 = post(ctx, Object.assign({}, ENTRY, { body: 'oversize try', uploads: [big] }));
  check('over 25 MB rejected', r4.ok === false && /25 MB/.test(r4.error));
  const many = Array.from({ length: 13 }, (_, i) => ({ name: 'p' + i + '.jpg', mime: 'image/jpeg', kind: 'photo', data_b64: 'aGk=' }));
  const r5 = post(ctx, Object.assign({}, ENTRY, { body: 'too many', uploads: many }));
  check('more than 12 files rejected', r5.ok === false && /too many/.test(r5.error));
  const twelveMb = 'A'.repeat(16 * 1024 * 1024); // 12 MB decoded per file
  const trio = Array.from({ length: 3 }, (_, i) => ({ name: 'big' + i + '.jpg', mime: 'image/jpeg', kind: 'photo', data_b64: twelveMb }));
  const r6 = post(ctx, Object.assign({}, ENTRY, { body: 'aggregate try', uploads: trio }));
  check('36 MB total rejected even with each file under 25 MB', r6.ok === false && /30 MB/.test(r6.error));
  check('rejected requests wrote no rows', ss.getSheetByName('RAW_MESSAGES').getLastRow() === 2);
  check('rejected requests saved no files', photos.files.length === 1 && notes.files.length === 1);
}

console.log('resubmit with new attachments:');
{
  const { ctx, ss, root } = freshWebApp();
  const raw = ss.getSheetByName('RAW_MESSAGES');
  const textOnly = Object.assign({}, ENTRY, { body: 'forgot the pics' });
  const r1 = post(ctx, textOnly);
  check('text-only entry logged', r1.ok === true && raw.getLastRow() === 2);

  const photo = { name: 'east-edge.jpg', mime: 'image/jpeg', kind: 'photo', data_b64: Buffer.from('closure strips').toString('base64') };
  const withPhoto = Object.assign({}, textOnly, { uploads: [photo] });
  const r2 = post(ctx, withPhoto);
  check('same text plus new photo is a new entry, not a dedupe drop', r2.ok === true && !r2.dedupe && r2.media === 1);
  check('new row written for it', raw.getLastRow() === 3);
  const photosFolder = root.folders.find(f => f.name === 'Photos');
  check('the late photo reached Drive', !!photosFolder && photosFolder.files.length === 1);

  const r3 = post(ctx, withPhoto);
  check('identical retry with the same attachment dedupes', r3.ok === true && r3.dedupe === true);
  check('retry wrote zero new rows', raw.getLastRow() === 3);
}

console.log('pending feed and approve:');
{
  const { ctx, ss } = freshWebApp();
  const diary = ss.getSheetByName('DIARY');
  diary.appendRow(['2026-06-08', 'Genius Kids STEM Academy (Katy)', 'mario@yourcompany.example.com', 'Clear', 'Old summary', '', '', 'TRUE', '2026-06-09T01:00:00.000Z']);
  diary.appendRow(['2026-06-09', 'Genius Kids STEM Academy (Katy)', 'paul@yourcompany.example.com', 'Rain', 'Paul summary', '', '', 'FALSE', '']);
  diary.appendRow(['2026-06-09', 'Genius Kids STEM Academy (Katy)', 'mario@yourcompany.example.com', 'Rain', 'Mario newest summary', '', '', 'FALSE', '']);

  const p = get(ctx, { secret: SECRET, action: 'pending', supervisor: 'mario@yourcompany.example.com' });
  check('pending returns latest unapproved row for that supervisor', p.ok === true && p.row === 4 && p.summary === 'Mario newest summary');
  check('pending date is yyyy-MM-dd, not a raw Date string', p.date === '2026-06-09', `(${p.date})`);
  const pPaul = get(ctx, { secret: SECRET, action: 'pending', supervisor: 'paul@yourcompany.example.com' });
  check('other supervisor sees own row only', pPaul.row === 3 && pPaul.summary === 'Paul summary');
  const pNone = get(ctx, { secret: SECRET, action: 'pending', supervisor: 'nobody@yourcompany.example.com' });
  check('no pending row returns row 0', pNone.ok === true && pNone.row === 0);

  const aWrong = post(ctx, { secret: SECRET, action: 'approve', row: 4, supervisor: 'paul@yourcompany.example.com' });
  check('approve blocked for the wrong supervisor', aWrong.ok === false && diary.rows[3][7] === false);
  const a = post(ctx, { secret: SECRET, action: 'approve', row: 4, supervisor: 'mario@yourcompany.example.com' });
  check('approve ok for the right row', a.ok === true && a.approved_row === 4);
  check('approved set TRUE (boolean on a real sheet)', diary.rows[3][7] === true);
  check('approved_ts is ISO', /^\d{4}-\d{2}-\d{2}T/.test(diary.rows[3][8]));
  check('untouched rows stay unapproved', diary.rows[2][7] === false);
  const aBad = post(ctx, { secret: SECRET, action: 'approve', row: 99, supervisor: 'mario@yourcompany.example.com' });
  check('approve out-of-range row rejected', aBad.ok === false && aBad.error === 'bad row');
}

console.log('error logging:');
{
  const { ctx, ss } = freshWebApp();
  const out = ctx.doPost({ postData: { contents: '{not json' } });
  const r = JSON.parse(out.getContent());
  check('malformed JSON returns ok:false', r.ok === false);
  check('error appended to ERRORS tab', ss.getSheetByName('ERRORS').getLastRow() === 2);
}

/* ---------------- setup tests ---------------- */

console.log('setupSandbox provisioning:');
{
  const { ctx, env } = buildContext();
  vm.runInContext(SETUP, ctx);
  ctx.setupSandbox();

  const ss = Object.values(env.spreadsheets)[0];
  check('spreadsheet named NC Site Diary SANDBOX', !!ss && ss.name === 'NC Site Diary SANDBOX');

  // Independent source of truth: handoff section 7, hard-coded here.
  const SECTION7 = {
    RAW_MESSAGES: ['msg_id', 'timestamp', 'source', 'chat_name_or_user', 'sender', 'body', 'media_link', 'processed'],
    DIARY: ['date', 'project', 'supervisor', 'weather', 'work_summary', 'safety_notes', 'photos_link', 'approved', 'approved_ts'],
    LABOR: ['date', 'project', 'employee', 'hours', 'cost_code'],
    QUANTITIES: ['date', 'project', 'cost_code', 'qty', 'unit'],
    DELIVERIES: ['date', 'project', 'supplier_internal', 'item', 'docket_link'],
    DELAYS: ['date', 'project', 'type', 'hours_lost', 'notes'],
    TASKS: ['created', 'project', 'task', 'owner', 'due', 'status', 'source_msg_id'],
    COST_CODES: ['code', 'activity', 'unit', 'budget_qty', 'budget_hours'],
    ERRORS: ['timestamp', 'error']
  };
  const names = ss.sheets.map(s => s.name);
  check('tab order matches section 7 plus ERRORS', names.join(',') === Object.keys(SECTION7).join(','), `(${names.join(',')})`);
  let headersOk = true;
  for (const [tab, cols] of Object.entries(SECTION7)) {
    const sheet = ss.getSheetByName(tab);
    const got = sheet ? (sheet.rows[0] || []).join(',') : 'MISSING';
    if (got !== cols.join(',')) { headersOk = false; console.log(`    header mismatch ${tab}: ${got}`); }
  }
  check('every header row exact', headersOk);

  const cc = ss.getSheetByName('COST_CODES');
  check('COST_CODES has 6 seed rows', cc.getLastRow() === 7);
  check('FAB seeded at 11 budget_hours', cc.rows[1][0] === 'FAB' && cc.rows[1][4] === 11);
  check('codes complete', cc.rows.slice(1).map(r => r[0]).join(',') === 'FAB,ERECT,DECK,DETAIL,MOB,PUNCH');

  const root = env.folders.root.folders.find(f => f.name === 'Site Diary');
  check('Drive /Site Diary created', !!root);
  const subs = root ? root.folders.map(f => f.name).sort().join(',') : '';
  check('subfolders Photos, Voice Notes, Chat Exports', subs === 'Chat Exports,Photos,Voice Notes', `(${subs})`);

  check('SHEET_ID property set', env.props.SHEET_ID === ss.getId());
  check('DRIVE_FOLDER property set', root && env.props.DRIVE_FOLDER === root.getId());
  check('secret is 48 chars', typeof env.props.SHARED_SECRET === 'string' && env.props.SHARED_SECRET.length === 48);

  const before = Object.values(env.spreadsheets).length;
  ctx.setupSandbox();
  check('second run refuses to reprovision', Object.values(env.spreadsheets).length === before);

  const problems = ctx.selfCheck();
  check('selfCheck passes after setup', Array.isArray(problems) && problems.length === 0, problems.length ? `(${problems.join('; ')})` : '');

  ctx.resetSandboxProperties();
  check('reset clears properties only', !env.props.SHEET_ID && !!ss.getSheetByName('COST_CODES'));
}

console.log('');
if (FAILS.length) {
  console.log(`RESULT: ${FAILS.length} FAILED: ${FAILS.join(', ')}`);
  process.exit(1);
}
console.log('RESULT: ALL TESTS PASS');
