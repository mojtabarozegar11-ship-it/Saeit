# Air Supremacy: gameplay and art reconstruction

The owner rated the previous release 10/100. This release does not claim a 100/100 quality score. It replaces the primitive space scene with detailed aerial environments and raster aircraft, reduces cockpit clutter, and improves combat continuity and controls.

## Delivered

- Ten optimized WebP assets: a detailed maritime fortress background a command-aircraft boss and eight distinct top-down aircraft sprites with transparency. Total transfer is about 0.76 MB, served from the existing origin without CDN dependencies.
- Original generated source assets were created using the built-in image-generation tool, then cropped into sprites and encoded for runtime use. The exact terrain and sprite prompts are retained below. Existing vector art remains as a loading/failure fallback.
- Cached reflected environment tiles avoid abrupt scrolling seams; moving fog, aircraft ground shadows, live exhaust, muzzle flashes, hit flashes, blast rings, smoke, debris and score popups. Particle and effect lists remain bounded.
- Enemy aircraft replace polygon icons; boss encounters use a multi-turret command aircraft with attack telegraphs and a phase/health display.
- A compact cockpit and simplified launch screen replace the large pre-game dashboard. Charge percentages are visible on touch abilities.
- Pointer steering uses a relative drag anchor, preventing the aircraft from jumping to the initial finger position. The player stays above the ability controls.
- Simulation uses bounded 1/60-second substeps, with a maximum 100 ms catch-up, to keep movement consistent during short frame hitches.
- Wave completion no longer forces the hangar open every three waves. Earned upgrades remain available through manual hangar access.
- An EMP that finishes a wave safely stops reading enemies cleared by wave advancement. A regression test reproduces the former undefined-enemy error.
- Boss contact no longer removes a living boss from the encounter. The existing 100 starting lives, progression, account ownership API and payment gates are preserved.

## Verification and limits

The Node harness runs both decoded-bitmap and missing-asset fallback paths. It checks finite draw arguments, 100 starting lives, boss contact retention, uninterrupted wave advancement, credit debit idempotence, trial ownership isolation, verified account restore and fail-closed offline behavior. Browser checks cover launch, steering, scoring, pause, fleet selection and Boss Rush.

This is a scoped static-game release. It does not edit core, configuration, payment logic, runtime settings or databases. Private backups and exact hashes protect the old game and versioned asset installation. The release verifies all ten public image responses and the protected-route status baseline, with rollback on a failed public smoke test.

It does not certify commercial readiness, Android-device frame rate, a 100/100 subjective score, or twenty independently tested evolutionary generations. The five cosmetic purchases remain unavailable until the separate real checkout integration is validated.

## Asset provenance

Built-in image generation; no CLI/API-key workflow. Runtime assets: `games/crown-defender/assets/air-supremacy/`. Terrain source: `exec-bd2eeb5b-2721-4a2c-9e77-188ad2266a29.png`. Sprite source: `exec-8662cb77-ab2c-4fed-add3-fb58a15d0b1c.png`.

Terrain prompt: “Use case: stylized-concept. Asset type: production-ready scrolling background texture for a polished premium top-down aircraft arcade game, NOT a screenshot or poster. Create a richly detailed 9:16 portrait, orthographic straight-down aerial view of a tropical maritime military archipelago. Sophisticated realistic hand-painted 3D game environment, ultra detailed vegetation, cliffs, teal deep sea, turquoise reef shallows, fine white shoreline foam, a few island airbases with concrete runway and aircraft shelters near left and right outer edges. Leave the central 55% mostly dark teal open ocean for high-contrast playable aircraft. Tiny oil platforms, docks, warehouses, roads, antennas subtly in environment. Cool cinematic daylight with warm subtle sun highlights, atmospheric depth, natural textures. Water at both top and bottom edges so the image can loop vertically without an abrupt land seam. Absolutely NO aircraft, NO ships in the central flight path, NO UI, NO borders, NO letters or text, NO watermark. Must look like actual high-quality game terrain, not flat vector shapes.”

Sprite prompt: “Use case: stylized-concept. Asset type: game sprite atlas with EIGHT different original futuristic military jets, each viewed STRICTLY ORTHOGRAPHIC DIRECTLY FROM ABOVE, nose points straight UP. Landscape image arranged exactly FOUR COLUMNS by TWO ROWS of equally-sized cells. One aircraft centered perfectly in each cell, all the same approximate size, comfortably separated by generous transparent padding. Absolutely no cell lines, no text, no labels. Transparent background and NO ground shadows. Premium realistic 3D pre-rendered game sprites, detailed layered metallic armor, panel seams, realistic intake vents, dark blue glass canopy with reflections, engine nozzles, wing-mounted little missiles, thin subtle navigation lights. Neutral cool daylight from upper left. Original designs: top row respectively narrow multirole swept wing silver fighter, twin-engine swept wing gunmetal interceptor, broad crescent flying wing stealth bomber, angular diamond stealth jet. Bottom row respectively elegant canard delta fighter, aggressive forward swept wing fighter, twin-boom heavy three-engine interceptor, majestic broad-wing command fighter with gold trim. Palette gunmetal silver with restrained teal or orange markings, realistic dimensional materials and believable aircraft construction. Not neon outlines, not flat vector icons, not wireframe, no perspective views. All eight noses must point UP; show the entire aircraft in every cell. No exhaust flames baked into sprites.”

Boss source: `exec-2148d641-a2e7-412a-a7e1-95d9f89974e2.png`. Built-in generation prompt: a transparent, strict top-down enemy command aircraft facing down, broad swept wings, layered gunmetal armor, four articulated cannon turrets, missile pods, amber markings and a blue glass bridge; realistic pre-rendered game sprite with no text, shadow or baked exhaust.
