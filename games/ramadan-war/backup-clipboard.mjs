// Local-only user-initiated fallback when mobile browsers cannot download a Blob.
// Returns a truthful success boolean; never writes the save to a server.
export async function copyCampaignBackupToClipboard(backup, nav, doc) {
  if (typeof backup !== 'string' || !backup || !doc?.body || doc.hidden === true) return false;
  if (typeof nav?.clipboard?.writeText === 'function') {
    try { await nav.clipboard.writeText(backup); return true; } catch { /* fallback */ }
  }
  // Permission prompts can outlive the visible tab; never trigger a legacy
  // private-data copy after the user has switched away.
  if (doc.hidden === true || typeof doc.createElement !== 'function' ||
      typeof doc.execCommand !== 'function') return false;
  const priorFocus = doc.activeElement;
  let area;
  try {
    area=doc.createElement('textarea');
    area.value=backup;
    area.setAttribute('readonly','');
    area.setAttribute('aria-hidden','true');
    area.style.cssText='position:fixed;left:-9999px;top:0;opacity:0';
    doc.body.appendChild(area);
    area.focus();area.select();
    if (doc.hidden === true) return false;
    return doc.execCommand('copy') === true;
  } catch { return false; }
  finally {
    area?.remove?.();
    // Removing the temporary textarea must not strand keyboard/gamepad users
    // on the document body. Focus restoration is best-effort and never copies.
    if (priorFocus?.isConnected !== false && typeof priorFocus?.focus === 'function') {
      try { priorFocus.focus({preventScroll:true}); } catch { /* detached control */ }
    }
  }
}
