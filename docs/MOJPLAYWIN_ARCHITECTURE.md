# MojPlayWin multi-brand architecture

## Boundary
MojPlayWin is a distinct global gaming brand served by the shared Saeit/Django engine. It must keep independent presentation, canonical domain, SEO, content, game catalog and future commerce/community configuration.

## Request path
Internet -> Nginx host routing -> shared Gunicorn/Django -> brand_for_request(host) -> MojPlayWin templates/services.

## Brand rules
- mojplaywin.com: English-first, LTR, gaming visual system.
- zomorodmelal.ir: existing company experience remains unchanged.
- No duplicated canonical URLs across brands.
- Brand presentation must never determine authorization, payments, treasury or Factory governance.
- New domains are added as explicit Brand entries, never wildcard-trusted hosts.

## Production activation checklist
1. Isolated VPS staging passes Django checks/tests.
2. ALLOWED_HOSTS explicitly includes mojplaywin.com and www.mojplaywin.com.
3. DNS A/AAAA records point to the verified VPS only after staging acceptance.
4. Install the Nginx virtual host and verify Host forwarding.
5. Issue independent TLS certificate for both MojPlayWin hosts.
6. Enable HTTPS redirect/HSTS only after HTTPS verification.
7. Verify canonical, robots.txt, sitemap.xml, mobile layout and error pages.
8. Keep publication/payment features fail-closed until their owner gates are separately approved.

## Future expansion
Persist Brand/Site configuration in the database when administration is required. Games, localization, SEO, pricing and market eligibility should reference brand/site identity while Factory execution remains shared.
