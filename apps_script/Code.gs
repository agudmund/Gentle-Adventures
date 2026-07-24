// -Gentle Adventures - Code.gs the Apps Script proxy, the Ledger's cloud-side half
// -The last of the unversioned cloud dwellers steps out of the browser and into the record, For Enjoying
// -Built using a single shared braincell by Yours Truly and various Intelligences

// SOURCE OF RECORD for the Sheet-bound Apps Script project (the GA_WebApp proxy).
// The browser project should always match this file — edit here, paste there.
//
// Deploy ritual (web-app half): paste the whole file over the project's Code.gs,
// save, then Deploy -> Manage deployments -> edit -> New version. The /exec URL
// (GA_WebApp) never changes. The onEdit simple trigger is the exception: it runs
// from the saved head script immediately, no redeploy needed.
//
// The shared token lives in Script Properties, never in this file: Project
// Settings -> Script Properties -> add GA_TOKEN with the same value as the
// GA_Ledger environment variable. Rotation is a one-property flip on each side.
//
// Contract (mirrors shared_braincell.sheets, the family's raw-urllib courier):
//   - Always answers HTTP 200 JSON; errors arrive in the body as {"error": ...}.
//     doGet is wrapped so even a missing tab answers JSON, never Google's HTML
//     error page (which the client can only classify as auth trouble —
//     the 2026-07-23 finding).
//   - GET  ?token=&sheet=            -> {sheet, values, version}
//   - GET  ?token=&op=list           -> {sheets: [names]}
//   - GET  ?token=&op=version        -> {version}   (cheap heartbeat token)
//   - POST {token, sheet, rows}      -> bulk replace below the header
//   - POST {token, sheet, updates}   -> Player_State-style key-value upsert
//   - POST {token, sheet, append}    -> stamped single-row append (the intercom)
//   - POST ... with create:true      -> missing tab is created first (optional
//                                       header: [...] sets row 1 on creation)
//   - doPost mutations serialize under LockService (one writer at a time at
//     the seam) and write through the _scalar/_literal guards: non-scalar
//     values store as JSON text, leading-'=' strings store as literal text,
//     and the rows path carries the same '@' type-fidelity guard as updates
//     (the 2026-07-24 scope pass, Sakura-rail lessons applied).

function _auth(t) {
  // Lazy read so the simple trigger below never depends on property machinery.
  const tok = PropertiesService.getScriptProperties().getProperty('GA_TOKEN');
  return !!tok && t === tok;
}

function _version(ss) {
  const meta = ss.getSheetByName('_meta');
  if (!meta) return null;
  const rows = meta.getDataRange().getValues();
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][0]).trim().toLowerCase() === 'version') return Number(rows[i][1] || 0);
  }
  return null;
}

function doGet(e) {
  try {
    if (!_auth(e && e.parameter && e.parameter.token)) return _json({error: 'unauthorized'});
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const op = (e.parameter.op || '');
    if (op === 'list') {
      return _json({sheets: ss.getSheets().map(function(s) { return s.getName(); })});
    }
    if (op === 'version') {
      return _json({version: _version(ss)});
    }
    const name = e.parameter.sheet || 'Quest_Log';
    const sheet = ss.getSheetByName(name);
    if (!sheet) return _json({error: 'no such sheet: ' + name});
    return _json({sheet: name, values: sheet.getDataRange().getValues(), version: _version(ss)});
  } catch (err) {
    return _json({error: String(err)});
  }
}

function _scalar(v) {
  // A non-scalar value (array/object) handed to setValues is mangled by the
  // grid — visited_scenes' list lives in Player_State as a bare comma-join
  // today (live evidence, 2026-07-24). JSON text is the deterministic form;
  // Date objects are exempt because getValues hands them back on rewrite and
  // the grid stores them natively.
  return (v !== null && typeof v === 'object' && !(v instanceof Date)) ? JSON.stringify(v) : v;
}

function _literal(v) {
  // A string cell starting with '=' EXECUTES as a formula under setValues /
  // appendRow — and the '@' text format does NOT suppress that (live-proven
  // 2026-07-24: '=1+1' evaluated to 2 inside a '@'-formatted cell). The
  // leading apostrophe is the sheet's own literal marker: stored invisibly,
  // getValues returns the bare string, so the round-trip stays byte-exact.
  return (typeof v === 'string' && v.charAt(0) === '=') ? "'" + v : v;
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (!_auth(body.token)) return _json({error: 'unauthorized'});
    // Serialize the seam (the one-delegation-at-a-time lesson): every mutation
    // below is a read-modify-write, and two unlocked writers silently revert
    // each other — the loser's stale snapshot wins the whole-matrix write-back
    // while both callers are told ok:true. One writer at a time, kindly.
    const lock = LockService.getScriptLock();
    lock.waitLock(20000);   // a timeout throws -> the JSON error envelope
    try {
      return _mutate(body);
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return _json({error: String(err)});
  }
}

function _mutate(body) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const name = body.sheet || 'Player_State';
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    // Opt-in creation only — a typo'd tab name must stay an error, not a tab.
    // The reserved intercom socket (_signals) is the one self-creating tab.
    if (body.create === true || (Array.isArray(body.append) && name === '_signals')) {
      sheet = ss.insertSheet(name);
      const header = Array.isArray(body.header) && body.header.length
        ? body.header
        : (name === '_signals' ? ['When', 'Kind', 'Detail'] : null);
      if (header) sheet.getRange(1, 1, 1, header.length).setValues([header]);
    } else {
      return _json({error: 'no such sheet: ' + name});
    }
  }

  // Intercom append — one stamped row, no other cells touched. The game
  // informs; the operator authors (State Sync v2).
  if (Array.isArray(body.append)) {
    sheet.appendRow([new Date().toISOString()].concat(
      body.append.map(function(v) { return _literal(_scalar(v)); })));
    return _json({ok: true, appended: body.append.length});
  }

  // Bulk row replace (e.g. re-seeding Quest_Log) — already one setValues.
  if (Array.isArray(body.rows)) {
    const last = sheet.getLastRow();
    if (last > 1) sheet.getRange(2, 1, last - 1, sheet.getMaxColumns()).clearContent();
    if (body.rows.length) {
      const range = sheet.getRange(2, 1, body.rows.length, body.rows[0].length);
      // Type-fidelity guard, rows edition — the 2026-06-03 fix covered only
      // the updates path; on a virgin column this path coerced '03:00:33'
      // onto the 1899 epoch and ate a '3-1' Scene_ID as March 1st (both
      // live-proven 2026-07-24). Numbers still round-trip as numbers under
      // '@' (same live evidence). Format first, then values.
      range.setNumberFormat('@');
      range.setValues(body.rows.map(function(r) {
        return r.map(function(v) { return _literal(_scalar(v)); });
      }));
    }
    return _json({ok: true, wrote: body.rows.length});
  }

  // Player_State upsert by Variable_Name — BATCHED: mutate in memory, then
  // write the whole block back in one setValues (vs a setValue per cell).
  const data = sheet.getDataRange().getValues();
  const width = data[0].length;            // header width — keep rows uniform
  const now = new Date().toISOString();
  (body.updates || []).forEach(function(u) {
    let found = false;
    for (let i = 1; i < data.length; i++) {
      // String() both sides: column 1 is never '@'-forced, so a numeric- or
      // date-shaped variable name arrives typed from getValues and a strict
      // === would never match its own row — every flush then appends a
      // fresh duplicate.
      if (String(data[i][0]) === String(u.variable)) {
        data[i][1] = _scalar(u.value);
        if (width > 2) data[i][2] = now;
        found = true;
        break;
      }
    }
    if (!found) {
      const row = [u.variable, _scalar(u.value), now];
      while (row.length < width) row.push('');   // pad to header width
      data.push(row.slice(0, width));            // …and never exceed it
    }
  });
  // Type-fidelity guard (the 2026-06-03 finding): force the value column to
  // plain text BEFORE writing, so a time-shaped string ('03:00:33') is never
  // coerced onto the 1899 spreadsheet epoch. Format first, then values.
  if (width > 1) sheet.getRange(1, 2, data.length, 1).setNumberFormat('@');
  // _literal over the WHOLE matrix, not just touched cells: the upsert writes
  // every row back, so a previously-stored literal '=' string would execute
  // on the next unrelated flush without it.
  sheet.getRange(1, 1, data.length, width).setValues(
    data.map(function(r) { return r.map(_literal); }));
  return _json({ok: true, wrote: (body.updates || []).length});
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function onEdit(e) {
  if (!e || !e.range) return;
  const name = e.range.getSheet().getName();
  // Content tabs only: state, signals, and the meta tab itself never bump.
  if (name === '_meta' || name === 'Player_State' || name === '_signals') return;
  const ss = e.source;
  let meta = ss.getSheetByName('_meta');
  if (!meta) {
    meta = ss.insertSheet('_meta');
    meta.getRange(1, 1, 1, 2).setValues([['key', 'value']]);
    // insertSheet makes the new tab active — hand the view straight back to the
    // sheet the human was editing, so arming never yanks them off their cell.
    e.range.getSheet().activate();
  }
  const rows = meta.getDataRange().getValues();
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][0]).trim().toLowerCase() === 'version') {
      meta.getRange(i + 1, 2).setValue(Number(rows[i][1] || 0) + 1);
      return;
    }
  }
  meta.appendRow(['version', 1]);
}
