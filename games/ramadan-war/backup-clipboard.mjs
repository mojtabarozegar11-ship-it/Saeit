// Local-only user-initiated fallback when mobile browsers cannot download a Blob.
// Returns a truthful success boolean; never writes the save to a server.
export async function copyCampaignBackupToClipboard(backup, nav, doc) {
  if (typeof backup !== 'string' || !backup || !doc?.body) return false;
  if (typeof nav?.clipboard?.writeText === 'function') {
    try { await nav.clipboard.writeText(backup); return true; } catch { /* fallback */ }
  }
  if (typeof doc.createElement !== 'function' || typeof doc.execCommand !== 'function') return false;
  let area;
  try {
    area=doc.createElement('textarea');
    area.value=backup;
    area.setAttribute('readonly','');
    area.setAttribute('aria-hidden','true');
    area.style.cssText='position:fixed;left:-9999px;top:0;opacity:0';
    doc.body.appendChild(area);
    area.focus();area.select();
    return doc.execCommand('copy') === true;
  } catch { return false; }
  finally { area?.remove?.(); }
}
