// G-01 -> S-01 handoff: anonymous public-page accessibility/hit-target audit.
// No network, cookies, storage, customer content, URL or text extraction.
// Run only on a public/staging page explicitly authorized by S-01.
export function auditPublicAnchorTargets(doc) {
  if (!doc || typeof doc.querySelectorAll !== 'function' ||
      typeof doc.elementFromPoint !== 'function') throw new TypeError('DOM document required');
  const anchors = [...doc.querySelectorAll('a[href]')].slice(0, 1000);
  const issues = [];
  let visible = 0;
  for (const [index, anchor] of anchors.entries()) {
    const style = doc.defaultView?.getComputedStyle?.(anchor);
    if (style?.display === 'none' || style?.visibility === 'hidden' ||
        !anchor.getClientRects?.().length) continue;
    const r = anchor.getBoundingClientRect?.();
    if (!r || !Number.isFinite(r.width) || !Number.isFinite(r.height) ||
        r.width <= 0 || r.height <= 0) continue;
    visible++;
    const named = [
      anchor.getAttribute?.('aria-label'), anchor.getAttribute?.('title'),
      anchor.innerText, anchor.textContent,
      ...[...anchor.querySelectorAll('img')].map(img => img.getAttribute('alt'))
    ].some(value => typeof value === 'string' && value.trim().length > 0);
    if (!named) issues.push({index, kind:'unnamed'});
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const hit = doc.elementFromPoint(x, y);
    if (!hit || (hit !== anchor && !anchor.contains(hit)))
      issues.push({index, kind:'center_obstructed'});
  }
  return {
    scanned: anchors.length, visible,
    unnamed: issues.filter(x => x.kind === 'unnamed').length,
    center_obstructed: issues.filter(x => x.kind === 'center_obstructed').length,
    issues
  };
}
// Example in an authorized browser console after loading this module:
// auditPublicAnchorTargets(document)
// Output contains indices/reason codes only; never URLs, labels, or private DOM text.
