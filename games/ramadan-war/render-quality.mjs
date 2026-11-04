// R58 mobile-first rendering policy: bounded pixel work without persistent settings.
export function selectRenderQuality(width, height, requestedDpr, coarsePointer = false, softwareRenderer = false) {
  const w = Number.isFinite(width) && width > 0 ? width : 1;
  const h = Number.isFinite(height) && height > 0 ? height : 1;
  const nativeDpr = Number.isFinite(requestedDpr) && requestedDpr > 0 ? requestedDpr : 1;
  // The budget is for physical render pixels, not CSS layout pixels.
  const maxDpr = coarsePointer ? 1.1 : 1.35;
  const pixelBudget = coarsePointer ? 900000 : 2250000;
  const budgetDpr = Math.sqrt(pixelBudget / (w * h));
  const softwareCap = softwareRenderer ? 0.78 : maxDpr;
  const pixelRatio = Math.max(0.5, Math.min(nativeDpr, maxDpr, budgetDpr, softwareCap));
  return { pixelRatio, shadows: !softwareRenderer && !coarsePointer };
}
