"use strict";
const UI_REVISION = '20261019-r19';
let revisionWarning = null;

function updateRevisionWarning(serverRevision, target) {
  if (serverRevision !== UI_REVISION) {
    revisionWarning = `Interface/server version mismatch (page ${UI_REVISION}, server ${serverRevision || 'older version'}). Refresh this page with Ctrl+F5. If the warning remains, stop/unload operations and restart Start_24well.vbs.`;
    target.textContent = revisionWarning;
  } else if (revisionWarning !== null) {
    // Clear only our own stale warning; retain unrelated operation errors.
    if (target.textContent === revisionWarning) target.textContent = '';
    revisionWarning = null;
  }
}
