/**
 * Your Company Site Diary - one-run sandbox provisioning.
 *
 * Run setupSandbox() once from the Apps Script editor before the first
 * web app deployment. It does the whole Google-side spin-up:
 *
 *   1. Creates the spreadsheet "NC Site Diary SANDBOX" with the 8 tabs
 *      and exact columns from CLAUDE_CODE_HANDOFF.md section 7, plus
 *      the ERRORS tab.
 *   2. Seeds COST_CODES with the 6 codes. FAB carries budget_hours 11
 *      (11 hr/ton reference baseline).
 *   3. Creates Drive folder /Site Diary with Photos, Voice Notes, and
 *      Chat Exports subfolders. Reuses them if they already exist.
 *   4. Generates a 48-character SHARED_SECRET.
 *   5. Stores script properties SHEET_ID, SHARED_SECRET, DRIVE_FOLDER.
 *   6. Logs every id. Paste SHEET_ID into CLAUDE_CODE_HANDOFF.md and
 *      the secret plus /exec URL into diary.js at deploy time.
 *
 * setupSandbox() refuses to run twice. To redo a broken setup, run
 * resetSandboxProperties() first (it only clears the script properties,
 * it deletes nothing in Drive), then run setupSandbox() again.
 *
 * selfCheck() verifies an existing setup: properties present, all tabs
 * present with exact headers, Drive folders reachable.
 */

var SANDBOX_SHEET_NAME = 'NC Site Diary SANDBOX';
var DRIVE_ROOT_NAME = 'Site Diary';
var DRIVE_SUBFOLDERS = ['Photos', 'Voice Notes', 'Chat Exports'];

// Section 7 schema, verbatim. ERRORS is the on-demand log tab.
var SCHEMA = [
  ['RAW_MESSAGES', ['msg_id', 'timestamp', 'source', 'chat_name_or_user', 'sender', 'body', 'media_link', 'processed']],
  ['DIARY',        ['date', 'project', 'supervisor', 'weather', 'work_summary', 'safety_notes', 'photos_link', 'approved', 'approved_ts']],
  ['LABOR',        ['date', 'project', 'employee', 'hours', 'cost_code']],
  ['QUANTITIES',   ['date', 'project', 'cost_code', 'qty', 'unit']],
  ['DELIVERIES',   ['date', 'project', 'supplier_internal', 'item', 'docket_link']],
  ['DELAYS',       ['date', 'project', 'type', 'hours_lost', 'notes']],
  ['TASKS',        ['created', 'project', 'task', 'owner', 'due', 'status', 'source_msg_id']],
  ['COST_CODES',   ['code', 'activity', 'unit', 'budget_qty', 'budget_hours']],
  ['ERRORS',       ['timestamp', 'error']]
];

var COST_CODES_SEED = [
  ['FAB',    'Shop fabrication', 'ton',   '', 11],
  ['ERECT',  'Field erection',   'ton',   '', ''],
  ['DECK',   'Deck install',     'SF',    '', ''],
  ['DETAIL', 'Detailing',        'sheet', '', ''],
  ['MOB',    'Mobilization',     'LS',    '', ''],
  ['PUNCH',  'Punch list',       'hr',    '', '']
];

function setupSandbox() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('SHEET_ID')) {
    Logger.log('Already configured. SHEET_ID = %s', props.getProperty('SHEET_ID'));
    Logger.log('Run resetSandboxProperties() first if you need a fresh setup.');
    return;
  }

  // 1 + 2: spreadsheet, tabs, headers, seed.
  var ss = SpreadsheetApp.create(SANDBOX_SHEET_NAME);
  var first = ss.getSheets()[0];
  for (var i = 0; i < SCHEMA.length; i++) {
    var name = SCHEMA[i][0];
    var headers = SCHEMA[i][1];
    var sheet = (i === 0) ? first.setName(name) : ss.insertSheet(name);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  var cc = ss.getSheetByName('COST_CODES');
  cc.getRange(2, 1, COST_CODES_SEED.length, 5).setValues(COST_CODES_SEED);

  // 3: Drive folders.
  var root = folderByName_(DriveApp.getRootFolder(), DRIVE_ROOT_NAME);
  for (var j = 0; j < DRIVE_SUBFOLDERS.length; j++) {
    folderByName_(root, DRIVE_SUBFOLDERS[j]);
  }

  // 4: shared secret, 48 chars.
  var secret = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '').slice(0, 48);

  // 5: script properties.
  props.setProperties({
    SHEET_ID: ss.getId(),
    SHARED_SECRET: secret,
    DRIVE_FOLDER: root.getId()
  });

  // 6: report.
  Logger.log('SANDBOX READY');
  Logger.log('SHEET_ID      = %s', ss.getId());
  Logger.log('Sheet URL     = %s', ss.getUrl());
  Logger.log('DRIVE_FOLDER  = %s', root.getId());
  Logger.log('SHARED_SECRET = %s', secret);
  Logger.log('Next: paste SHEET_ID into CLAUDE_CODE_HANDOFF.md, deploy the');
  Logger.log('web app, then put the /exec URL and the secret into diary.js.');
}

function resetSandboxProperties() {
  // Clears config only. The spreadsheet and Drive folders are untouched.
  PropertiesService.getScriptProperties()
    .deleteProperty('SHEET_ID')
    .deleteProperty('SHARED_SECRET')
    .deleteProperty('DRIVE_FOLDER');
  Logger.log('Script properties cleared. Run setupSandbox() to provision again.');
}

function selfCheck() {
  var problems = [];
  var props = PropertiesService.getScriptProperties();
  ['SHEET_ID', 'SHARED_SECRET', 'DRIVE_FOLDER'].forEach(function (k) {
    if (!props.getProperty(k)) problems.push('missing script property ' + k);
  });

  if (props.getProperty('SHEET_ID')) {
    var ss = SpreadsheetApp.openById(props.getProperty('SHEET_ID'));
    SCHEMA.forEach(function (spec) {
      var sheet = ss.getSheetByName(spec[0]);
      if (!sheet) { problems.push('missing tab ' + spec[0]); return; }
      var got = sheet.getRange(1, 1, 1, spec[1].length).getValues()[0].join(',');
      if (got !== spec[1].join(',')) {
        problems.push('tab ' + spec[0] + ' headers are [' + got + '], expected [' + spec[1].join(',') + ']');
      }
    });
    var ccRows = ss.getSheetByName('COST_CODES');
    if (ccRows && ccRows.getLastRow() < 7) problems.push('COST_CODES seed incomplete: expected 6 code rows');
  }

  if (props.getProperty('DRIVE_FOLDER')) {
    var root = DriveApp.getFolderById(props.getProperty('DRIVE_FOLDER'));
    DRIVE_SUBFOLDERS.forEach(function (n) {
      if (!root.getFoldersByName(n).hasNext()) problems.push('missing Drive subfolder ' + n);
    });
  }

  if (problems.length) {
    Logger.log('SELF CHECK FAILED (%s problems):', problems.length);
    problems.forEach(function (p) { Logger.log('  - ' + p); });
  } else {
    Logger.log('SELF CHECK PASSED. Tabs, headers, seed, folders, properties all good.');
  }
  return problems;
}

function folderByName_(parent, name) {
  var it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}
