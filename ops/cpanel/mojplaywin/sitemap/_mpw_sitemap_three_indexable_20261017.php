<?php
declare(strict_types=1);
/**
 * Moj Play Win public sitemap live augmentation, isolated from shared Django.
 * It fetches the existing MojPlayWin sitemap via a strictly same-origin HTTPS
 * bypass, then adds only market, industry and economy URLs when absent.
 * The original dynamic sitemap entries remain byte-for-byte unchanged.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
$host = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
if (!in_array($host, ['mojplaywin.com', 'www.mojplaywin.com'], true)
    || strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? '')) !== 'GET') {
    http_response_code(404);
    exit('Not found');
}
header('X-Content-Type-Options: nosniff');
header('Cache-Control: public, max-age=300');
function fallbackSitemap(): never {
    header('Location: /sitemap.xml?__mpw_sitemap_passthru=1', true, 307);
    exit;
}
$curl = curl_init('https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1');
if ($curl === false) fallbackSitemap();
curl_setopt_array($curl, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADER => true,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_CONNECTTIMEOUT => 4,
    CURLOPT_TIMEOUT => 12,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
    CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
    CURLOPT_ENCODING => 'identity',
    CURLOPT_HTTPHEADER => ['Accept: application/xml,text/xml,*/*', 'Cache-Control: no-cache', 'Accept-Encoding: identity'],
    CURLOPT_USERAGENT => 'MojPlayWin-main-only-dynamic-sitemap/1.0',
]);
$result = curl_exec($curl);
$code = (int)curl_getinfo($curl, CURLINFO_HTTP_CODE);
$type = (string)curl_getinfo($curl, CURLINFO_CONTENT_TYPE);
$headSize = curl_getinfo($curl, CURLINFO_HEADER_SIZE);
$err = curl_errno($curl);
curl_close($curl);
if (!is_string($result) || $code !== 200 || $err !== 0
    || !is_int($headSize) || $headSize < 1
    || (stripos($type, 'xml') === false)) fallbackSitemap();
$original = substr($result, $headSize);
if (strlen($original) < 250 || strlen($original) > 950000
    || substr_count($original, '</urlset>') !== 1
    || substr_count($original, '<urlset') !== 1
    || substr_count($original, '<loc>') < 4
    || substr_count($original, '<loc>') > 3000
    || strpos($original, 'https://mojplaywin.com/') === false
    || strpos($original, 'https://zomorodmelal.ir/') !== false) fallbackSitemap();
$mojPropPaths = ['/moj-prop/rules/', '/moj-prop/signals/', '/moj-prop/payment/', '/moj-prop/contact/', '/moj-prop/selected-traders/', '/moj-prop/education/', '/moj-prop/education/risk-management/', '/moj-prop/education/drawdown-and-position-sizing/', '/moj-prop/education/sixty-day-simulated-challenge/', '/moj-prop/education/best-day-consistency/', '/moj-prop/education/simulated-versus-live/', '/moj-prop/catalog/'];
$locCount = substr_count($original, '<loc>');
if ($locCount < 20) {
    preg_match_all('~<loc>([^<]+)</loc>~', $original, $matchedLocs);
    $existingLocs = $matchedLocs[1] ?? [];
    if (count($existingLocs) !== $locCount || count(array_unique($existingLocs)) !== $locCount) fallbackSitemap();
    foreach ($existingLocs as $existingLoc) {
        if (strpos($existingLoc, 'https://mojplaywin.com/') !== 0) fallbackSitemap();
    }
    $extra = '';
    foreach ($mojPropPaths as $path) {
        $loc = '<loc>https://mojplaywin.com' . $path . '</loc>';
        $seen = substr_count($original, $loc);
        if ($seen > 1) fallbackSitemap();
        if ($seen === 0) $extra .= '<url>' . $loc . '</url>';
    }
    $closing = strrpos($original, '</urlset>');
    if ($closing === false) fallbackSitemap();
    $body = substr($original, 0, $closing) . $extra . substr($original, $closing);
    header('Content-Type: application/xml; charset=utf-8');
    header('X-MPW-Sitemap-Augmentation: moj-prop-only-low-count');
    echo $body;
    exit;
}
$paths = ['/market/', '/industry/', '/economy/'];
$paths = array_merge($paths, $mojPropPaths);
$extra = '';
// MPW_REVENUE_SITEMAP_LINKS_20261020 -- 13 additional verified indexable main-domain pages
$mpwRevenuePages20261020 = ['/mpw-editorial/revenue/index.html','/mpw-editorial/revenue/website-doctor/index.html','/mpw-editorial/revenue/landing-page-studio/index.html','/mpw-editorial/revenue/ai-automation/index.html','/mpw-editorial/revenue/business-spreadsheets/index.html','/mpw-editorial/revenue/website-templates/index.html','/mpw-editorial/revenue/social-media-kits/index.html','/mpw-editorial/revenue/resume-builder/index.html','/mpw-editorial/revenue/logo-studio/index.html','/mpw-editorial/revenue/browser-games/index.html','/mpw-editorial/revenue/marketing-ai/index.html','/mpw-editorial/revenue/business-calculators/index.html','/mpw-editorial/revenue/website-care/index.html'];
if (count($mpwRevenuePages20261020) !== 13 || count(array_unique($mpwRevenuePages20261020)) !== 13) fallbackSitemap();
$paths = array_merge($paths, $mpwRevenuePages20261020);
// 2026-10-25: verified canonical MPW learning resources, isolated sitemap registration
// MPW_MAIN_NAV_SITEMAP_20261026: indexable navigational destinations
// MPW_EDITORIAL_COLLECTIONS_SITEMAP_20261027
// MPW_EDITORIAL_EVIDENCE_POLICY_SITEMAP_20261027
$paths = array_merge($paths, ['/mpw-editorial/editorial-standards/index.html']);
$paths = array_merge($paths, ['/mpw-editorial/collections/about/index.html', '/mpw-editorial/collections/ventures-hospitality/index.html', '/mpw-editorial/collections/agents/index.html', '/mpw-editorial/collections/ventures-agriculture/index.html', '/mpw-editorial/collections/ventures-jewelry-gold/index.html', '/mpw-editorial/collections/industry/index.html', '/mpw-editorial/collections/ventures-ecommerce/index.html', '/mpw-editorial/collections/services/index.html', '/mpw-editorial/collections/research/index.html', '/mpw-editorial/collections/ventures-currency-crypto/index.html', '/mpw-editorial/collections/ventures-carpets/index.html', '/mpw-editorial/collections/company/index.html', '/mpw-editorial/collections/studio/index.html', '/mpw-editorial/collections/ventures-cafe-restaurant/index.html', '/mpw-editorial/collections/knowledge/index.html', '/mpw-editorial/collections/ventures-fuel-station/index.html', '/mpw-editorial/collections/economy/index.html', '/mpw-editorial/collections/market/index.html']);
// MPW_12_STANDALONE_LEGACY_PAGES_20261026
$paths = array_merge($paths, ['/mpw-editorial/field-guides/original-ten/','/mpw-editorial/site-directory/','/mpw-editorial/field-guides/original-ten/vertical-slice/','/mpw-editorial/field-guides/original-ten/accessible-play/','/mpw-editorial/field-guides/original-ten/ai-workflow-risk/','/mpw-editorial/field-guides/original-ten/ai-privacy/','/mpw-editorial/field-guides/original-ten/demo-proof/','/mpw-editorial/field-guides/original-ten/product-readiness/','/mpw-editorial/field-guides/original-ten/web-discovery/','/mpw-editorial/field-guides/original-ten/support-library/','/mpw-editorial/field-guides/original-ten/vancouver-pilot-plan/','/mpw-editorial/field-guides/original-ten/agro-scenario-dashboard/','/mpw-editorial/field-guides/20261023/index.html','/mpw-editorial/field-guides/20261023/prism-relay/index.html','/mpw-editorial/field-guides/20261023/guides/accessible-action-feedback/index.html','/mpw-editorial/field-guides/20261023/guides/alt-text-game-catalog/index.html','/mpw-editorial/field-guides/20261023/guides/animated-preview-policy/index.html','/mpw-editorial/field-guides/20261023/guides/art-directed-mobile-crops/index.html','/mpw-editorial/field-guides/20261023/guides/atomic-versioned-publish/index.html','/mpw-editorial/field-guides/20261023/guides/cache-release-boundaries/index.html','/mpw-editorial/field-guides/20261023/guides/canvas-static-layers/index.html','/mpw-editorial/field-guides/20261023/guides/cls-reserved-covers/index.html','/mpw-editorial/field-guides/20261023/guides/codec-visual-comparison/index.html','/mpw-editorial/field-guides/20261023/guides/content-type-and-decoder/index.html','/mpw-editorial/field-guides/20261023/guides/csp-migration/index.html','/mpw-editorial/field-guides/20261023/guides/decode-memory/index.html','/mpw-editorial/field-guides/20261023/guides/dom-accessible-board/index.html','/mpw-editorial/field-guides/20261023/guides/dpr-render-cost/index.html','/mpw-editorial/field-guides/20261023/guides/fixed-step-physics/index.html','/mpw-editorial/field-guides/20261023/guides/focus-return-menus/index.html','/mpw-editorial/field-guides/20261023/guides/font-swap-scoreboards/index.html','/mpw-editorial/field-guides/20261023/guides/frame-time-p95/index.html','/mpw-editorial/field-guides/20261023/guides/full-match-level-codes/index.html','/mpw-editorial/field-guides/20261023/guides/image-quality-acceptance/index.html','/mpw-editorial/field-guides/20261023/guides/inp-instant-menu/index.html','/mpw-editorial/field-guides/20261023/guides/input-response-traces/index.html','/mpw-editorial/field-guides/20261023/guides/intrinsic-size-contract/index.html','/mpw-editorial/field-guides/20261023/guides/keyboard-parity-puzzles/index.html','/mpw-editorial/field-guides/20261023/guides/keyboard-trap-audit/index.html','/mpw-editorial/field-guides/20261023/guides/lcp-hero-images/index.html','/mpw-editorial/field-guides/20261023/guides/local-progress-trust/index.html','/mpw-editorial/field-guides/20261023/guides/neon-text-contrast/index.html','/mpw-editorial/field-guides/20261023/guides/paid-delivery-boundary/index.html','/mpw-editorial/field-guides/20261023/guides/pause-on-visibility/index.html','/mpw-editorial/field-guides/20261023/guides/pointer-capture-board/index.html','/mpw-editorial/field-guides/20261023/guides/polite-win-announcements/index.html','/mpw-editorial/field-guides/20261023/guides/private-photo-metadata/index.html','/mpw-editorial/field-guides/20261023/guides/public-manifest-evidence/index.html','/mpw-editorial/field-guides/20261023/guides/reduced-motion-playability/index.html','/mpw-editorial/field-guides/20261023/guides/reproducible-device-qa/index.html','/mpw-editorial/field-guides/20261023/guides/rollback-sha-verification/index.html','/mpw-editorial/field-guides/20261023/guides/safe-player-names/index.html','/mpw-editorial/field-guides/20261023/guides/script-evaluation-budget/index.html','/mpw-editorial/field-guides/20261023/guides/scroll-versus-tap/index.html','/mpw-editorial/field-guides/20261023/guides/shape-not-only-color/index.html','/mpw-editorial/field-guides/20261023/guides/sound-consent/index.html','/mpw-editorial/field-guides/20261023/guides/sprite-atlas-tradeoffs/index.html','/mpw-editorial/field-guides/20261023/guides/srcset-responsive-covers/index.html','/mpw-editorial/field-guides/20261023/guides/stable-grid-focus/index.html','/mpw-editorial/field-guides/20261023/guides/touch-controls-spacing/index.html','/mpw-editorial/field-guides/20261023/guides/two-tap-drag-fallback/index.html','/mpw-editorial/field-guides/20261023/guides/upload-errors-readable/index.html','/mpw-editorial/field-guides/20261023/guides/verify-webp-signatures/index.html','/mpw-editorial/field-guides/20261023/guides/zoom-200-percent/index.html']);
$paths = array_merge($paths, ['/knowledge/', '/research/', '/company/', '/taniya/', '/ventures/agriculture/']);
// 2026-10-25: indexable free-tool and evergreen learning hubs (18 URL two-site release)
$paths = array_merge($paths, ['/mpw-free-tools/20261025/','/mpw-free-tools/20261025/chess-calendar/','/mpw-free-tools/20261025/taniya-storytime/','/mpw-free-tools/20261025/atelier-seo/','/mpw-free-tools/20261025/atelier-contrast/','/mpw-free-tools/20261025/browser-game-qa/','/mpw-free-tools/20261025/research-evidence/','/mpw-learning/20261025/','/mpw-learning/20261025/chess-baseline/','/mpw-learning/20261025/family-storytime/','/mpw-learning/20261025/website-client-brief/','/mpw-learning/20261025/research-methods/']);
$paths = array_merge($paths, ['/mpw-learning/20261025b/chess-error-review/','/mpw-learning/20261025b/taniya-creative-retelling/','/mpw-learning/20261025b/atelier-accessibility-acceptance/','/mpw-learning/20261025b/browser-game-retention-diagnostics/','/mpw-learning/20261025b/digital-product-license-check/','/mpw-learning/20261025b/research-data-audit-trail/']);
foreach ($paths as $path) {
    $url = 'https://mojplaywin.com' . $path;
    // The original XML uses URLs under a single trusted domain.
    $loc = '<loc>' . $url . '</loc>';
    if (substr_count($original, $loc) > 1) fallbackSitemap();
    if (substr_count($original, $loc) === 0) {
        $extra .= '<url>' . $loc . '</url>';
    }
}
$closing = strrpos($original, '</urlset>');
if ($closing === false) fallbackSitemap();
$body = substr($original, 0, $closing) . $extra . substr($original, $closing);
header('Content-Type: application/xml; charset=utf-8');
header('X-MPW-Sitemap-Augmentation: three-indexable-main-pages');
echo $body;
