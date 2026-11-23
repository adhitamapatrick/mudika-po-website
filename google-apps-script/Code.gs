/**
 * Mudika PO -> Google Sheet
 *
 * Paste this into the spreadsheet's Apps Script editor
 * (Extensions > Apps Script), then deploy it as a Web app.
 * Full steps are in the README ("Connect the Google Sheet").
 *
 * The website sends new orders here, and this script adds them as rows.
 */

// Must match SHEETS_WEBHOOK_SECRET on the website. Use a long random phrase.
const SECRET = 'PASTE-THE-SAME-SECRET-HERE';

// Tab to write to. Leave '' to use the first tab.
const SHEET_NAME = '';

// Column L holds the order reference; used to avoid adding the same order twice.
const REFERENCE_COLUMN = 12;

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000); // one order at a time, so rows never overlap
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.secret !== SECRET) {
      return reply({ ok: false, error: 'wrong secret' });
    }

    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = SHEET_NAME ? spreadsheet.getSheetByName(SHEET_NAME) : spreadsheet.getSheets()[0];

    // Skip orders that are already in the sheet (e.g. when an admin presses "Copy missing orders" twice)
    const lastRow = sheet.getLastRow();
    const existing = new Set(
      lastRow > 0
        ? sheet.getRange(1, REFERENCE_COLUMN, lastRow, 1).getValues().map((row) => String(row[0]))
        : []
    );
    const rows = (body.rows || []).filter((row) => !existing.has(String(row[REFERENCE_COLUMN - 1])));

    if (rows.length > 0) {
      sheet.getRange(lastRow + 1, 1, rows.length, rows[0].length).setValues(rows);
    }
    return reply({ ok: true, added: rows.length });
  } finally {
    lock.releaseLock();
  }
}

function reply(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
