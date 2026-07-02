/**
 * Your Company Site Diary - Track B backend (SANDBOX).
 * Apps Script web app. Receives diary entries from diary.html and
 * appends them to RAW_MESSAGES. Saves photo and voice uploads to Drive.
 *
 * Hardening in this revision:
 *   1. Per-file upload cap: 25 MB decoded. Requests over the cap are
 *      rejected before anything is written.
 *   2. MIME allowlist: images and audio only. Kind must match type
 *      (photo uploads must be image/*, voice uploads must be audio/*).
 *   3. LockService wraps the dedupe check plus appendRow so two
 *      concurrent submits of the same entry write exactly 1 row.
 *   4. Approve verifies the supervisor owns the row before setting
 *      approved. A row number alone is not enough.
 *
 * Deploy: see DEPLOY.md in this folder. Run setupSandbox() in Setup.gs
 * once before the first deployment. It creates the sandbox sheet, the
 * Drive folders, and the shared secret, and stores all three script
 * properties this file reads:
 *   SHEET_ID      - sandbox spreadsheet id (NEVER the live sheet until
 *                   the verification gate passes)
 *   SHARED_SECRET - random string, must match the value in diary.js
 *   DRIVE_FOLDER  - id of Drive folder /Site Diary
 */

var TABS = {
  RAW: 'RAW_MESSAGES',
  DIARY: 'DIARY',
  ERR: 'ERRORS'
};

var MAX_UPLOAD_BYTES = 25 * 1024 * 1024;   // 25 MB per file, decoded
var MAX_UPLOADS_PER_REQUEST = 12;
// Whole-entry cap. Apps Script rejects POST bodies around 50 MB before
// doPost runs, so the per-file cap alone would let a request die at the
// platform layer with an HTML error the page cannot parse. 30 MB
// decoded is about 40 MB as base64 JSON, safely under that limit.
var MAX_TOTAL_UPLOAD_BYTES = 30 * 1024 * 1024;
var MAX_BODY_CHARS = 20000;

var ALLOWED_IMAGE_MIME = [
  'image/jpeg', 'image/png', 'image/gif', 'image/webp',
  'image/heic', 'image/heif'
];
var ALLOWED_AUDIO_MIME = [
  'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/m4a', 'audio/aac',
  'audio/ogg', 'audio/opus', 'audio/wav', 'audio/x-wav', 'audio/webm',
  'audio/3gpp', 'audio/amr', 'audio/flac'
];

function doGet(e) {
  // Health check plus the supervisor approval feed.
  var p = (e && e.parameter) || {};
  if (!checkSecret_(p.secret)) return json_({ ok: false, error: 'denied' });
  if (p.action === 'pending') return pendingApproval_(p.supervisor || '');
  return json_({ ok: true, service: 'nc-site-diary', ts: nowIso_() });
}

function doPost(e) {
  try {
    var body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (!checkSecret_(body.secret)) return json_({ ok: false, error: 'denied' });

    if (body.action === 'approve') return approveDiary_(body);
    return newEntry_(body);
  } catch (err) {
    logError_(err);
    return json_({ ok: false, error: String(err) });
  }
}

function newEntry_(body) {
  var text = String(body.body || '');
  if (text.length > MAX_BODY_CHARS) {
    return json_({ ok: false, error: 'update text too long (max ' + MAX_BODY_CHARS + ' characters)' });
  }

  var uploads = body.uploads || [];
  var validationError = validateUploads_(uploads);
  if (validationError) return json_({ ok: false, error: validationError });

  // Dedupe key covers everything the crew can change on the form.
  // A pure retry (lost response, same form state) dedupes to zero new
  // rows. Resubmitting the same text with new photos or a corrected
  // weather value is a different entry and must not be dropped.
  var msgId = 'portal-' + sha1Hex_([
    body.sender, body.date, text, String(body.weather || ''), uploadsDigest_(uploads)
  ].join('|')).slice(0, 16);
  var sheet = sheet_(TABS.RAW);

  // Fast path: identical resubmission returns before any Drive write.
  if (alreadyLogged_(sheet, msgId)) {
    return json_({ ok: true, dedupe: true, msg_id: msgId });
  }

  var mediaLinks = [];
  for (var i = 0; i < uploads.length; i++) {
    mediaLinks.push(saveUpload_(uploads[i]));
  }

  // Atomic check-then-append. Without the lock, two concurrent submits
  // of the same entry can both pass the check above and write 2 rows.
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    if (alreadyLogged_(sheet, msgId)) {
      return json_({ ok: true, dedupe: true, msg_id: msgId });
    }
    sheet.appendRow([
      msgId,
      nowIso_(),
      'portal',
      body.project || '',
      body.sender || '',
      buildBody_(body),
      mediaLinks.join(' '),
      'FALSE'
    ]);
  } finally {
    lock.releaseLock();
  }
  return json_({ ok: true, msg_id: msgId, media: mediaLinks.length });
}

function validateUploads_(uploads) {
  if (!Array.isArray(uploads)) return 'uploads must be a list';
  if (uploads.length > MAX_UPLOADS_PER_REQUEST) {
    return 'too many files (max ' + MAX_UPLOADS_PER_REQUEST + ' per entry)';
  }
  var totalBytes = 0;
  for (var i = 0; i < uploads.length; i++) {
    var u = uploads[i] || {};
    var name = String(u.name || 'file');
    var mime = String(u.mime || '').toLowerCase().split(';')[0].trim();
    var allowed = u.kind === 'voice' ? ALLOWED_AUDIO_MIME : ALLOWED_IMAGE_MIME;
    if (allowed.indexOf(mime) === -1) {
      return 'file type not allowed for ' + name + ' (' + (mime || 'unknown') +
        '). Photos must be images, voice notes must be audio.';
    }
    var b64 = String(u.data_b64 || '');
    if (!b64) return 'empty file: ' + name;
    var approxBytes = Math.floor(b64.length * 3 / 4);
    if (approxBytes > MAX_UPLOAD_BYTES) {
      return name + ' is over the 25 MB limit';
    }
    totalBytes += approxBytes;
  }
  if (totalBytes > MAX_TOTAL_UPLOAD_BYTES) {
    return 'attachments total over the 30 MB per-entry limit. Send some now and the rest in a second entry.';
  }
  return '';
}

function uploadsDigest_(uploads) {
  return (uploads || []).map(function (u) {
    u = u || {};
    return [u.kind, u.name, String(u.data_b64 || '').length].join(':');
  }).join(',');
}

function buildBody_(b) {
  // One text blob for the Cowork extractor. Weather and date ride along.
  var parts = [];
  if (b.date) parts.push('DATE: ' + b.date);
  if (b.weather) parts.push('WEATHER: ' + b.weather);
  if (b.body) parts.push(String(b.body));
  if (b.voice_note) parts.push('VOICE NOTE UPLOADED');
  return parts.join('\n');
}

function saveUpload_(u) {
  var folder = DriveApp.getFolderById(prop_('DRIVE_FOLDER'));
  var sub = u.kind === 'voice' ? 'Voice Notes' : 'Photos';
  var it = folder.getFoldersByName(sub);
  var target = it.hasNext() ? it.next() : folder.createFolder(sub);
  var name = cleanFileName_(u.name);
  var blob = Utilities.newBlob(Utilities.base64Decode(u.data_b64), u.mime, name);
  return target.createFile(blob).getUrl();
}

function cleanFileName_(name) {
  var n = String(name || 'upload').replace(/[\\\/\x00-\x1f]/g, '_');
  return n.length > 120 ? n.slice(n.length - 120) : n;
}

function pendingApproval_(supervisor) {
  // Latest unapproved DIARY row for this supervisor, for the portal page.
  // DIARY columns: date, project, supervisor, weather, work_summary,
  // safety_notes, photos_link, approved, approved_ts
  if (!supervisor) return json_({ ok: true, row: 0 });
  var sheet = sheet_(TABS.DIARY);
  var rows = sheet.getDataRange().getValues();
  for (var i = rows.length - 1; i > 0; i--) {
    if (String(rows[i][2]) === supervisor && String(rows[i][7]).toUpperCase() !== 'TRUE') {
      return json_({
        ok: true, row: i + 1,
        date: cellDate_(rows[i][0]),
        project: String(rows[i][1]),
        supervisor: String(rows[i][2]),
        weather: String(rows[i][3]),
        summary: String(rows[i][4])
      });
    }
  }
  return json_({ ok: true, row: 0 });
}

function approveDiary_(body) {
  var row = Number(body.row || 0);
  var sheet = sheet_(TABS.DIARY);
  if (!(row >= 2 && row <= sheet.getLastRow())) {
    return json_({ ok: false, error: 'bad row' });
  }
  var supervisor = String(body.supervisor || '');
  var rowVals = sheet.getRange(row, 1, 1, 9).getValues()[0];
  var owner = String(rowVals[2]);
  if (!supervisor || owner !== supervisor) {
    return json_({ ok: false, error: 'not your row' });
  }
  sheet.getRange(row, 8).setValue('TRUE');          // approved
  sheet.getRange(row, 9).setValue(nowIso_());       // approved_ts
  return json_({ ok: true, approved_row: row });
}

function alreadyLogged_(sheet, msgId) {
  var last = sheet.getLastRow();
  if (last < 1) return false;
  var ids = sheet.getRange(1, 1, last, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === msgId) return true;
  }
  return false;
}

function logError_(err) {
  try {
    var sheet = sheet_(TABS.ERR);
    sheet.appendRow([nowIso_(), String(err && err.stack ? err.stack : err)]);
  } catch (e) {
    // ERRORS tab unavailable. Nothing else to do from here.
  }
}

function cellDate_(v) {
  if (v instanceof Date) {
    return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  return String(v);
}

function checkSecret_(s) {
  return !!s && s === prop_('SHARED_SECRET');
}

function sha1Hex_(str) {
  var bytes = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_1, String(str), Utilities.Charset.UTF_8);
  var hex = '';
  for (var i = 0; i < bytes.length; i++) {
    var b = (bytes[i] + 256) % 256;       // GAS returns signed bytes
    hex += (b < 16 ? '0' : '') + b.toString(16);
  }
  return hex;
}

function sheet_(name) {
  return SpreadsheetApp.openById(prop_('SHEET_ID')).getSheetByName(name);
}

function prop_(k) {
  return PropertiesService.getScriptProperties().getProperty(k);
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function nowIso_() {
  return new Date().toISOString();
}
