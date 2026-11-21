# Ramadan War — Unity 6 reconstruction (isolated development)

This is a **new game project**, not an update of `games/ramadan-war`. Nothing here is linked to the live site. The production card stays unchanged until a human-approved promotion.

## Goal

Create a focused, playable first-person 3D vertical slice. One complete mission comes before additional stages or 30 playable characters. This first engineering milestone supplies combat, AI, objective sequencing, responsive controls, and build automation. **It is not AAA art, commercial-ready content, or 100/100 quality.**

## Mission 01 — Defensive Relay

A 180×180 m fictional military training compound with an elevated approach, radar station, intelligence cache, cover, and extraction site:

1. Disable two relay nodes (interact at close range).
2. Recover three intelligence caches.
3. Survive hostile reinforcements and reach extraction after neutralizing at least four enemies.

The mission shows a compass/objective readout, health and ammunition, reloading, recoil, sprinting, hits, enemy states, respawning and victory. Keys: WASD movement, mouse look, Left Shift sprint, mouse click shoot, right click aim, R reload, G interact, Esc cursor toggle. Touch: left 42% of the screen to move, right area drag to aim, lower-right FIRE, upper-right INTERACT, second action lower-right RELOAD.

## Open in Unity

* Install **Unity 6.0** editor (version in `ProjectSettings/ProjectVersion.txt`), Web Build Support and Android Build Support modules.
* Open this folder as a **separate Unity project**. No third-party 3D model is required for the mechanics prototype; blockout primitives are intentionally used while licensed assets are sourced.
* Enter Play Mode in any empty scene. `RWBootstrap` creates the entire test world.
* Build from `Tools → Ramadan War Next → Build Web` or `Build Android`. The editor tool creates a temporary generated scene automatically and builds to `Builds/Web` or `Builds/Android/RamadanWarNext.apk`.
* Android build requires installed SDK/NDK and device testing. Web build requires a WebGL2-capable browser. Neither target has been built or visually tested in this environment.

## Quality gates before promotion

- **Asset gate:** license file, original model provenance, texture completeness, rig/animation checks. A 3 MB expected model replaced by a truncated GLB is an automatic fail.
- **Gameplay gate:** complete mission playable and enjoyable for independent testers, functional touch/controller and mouse, responsive firing/aiming, nontrivial enemy movement.
- **Performance gate:** measure steady 30 FPS on actual mid-range Android and 60 FPS on a nominated desktop, with meaningful settings; these are targets, not verified results.
- **Release gate:** QA video and cold-start gameplay evidence on real GPU, passing Web/Android builds, smoke test at staging URL, backup and rollback verified. Keep `/ramadan-war/` and IT cards 1/3 unchanged.
- **Content gate:** all public figures and real military references require an explicit editorial review. This test mission uses fictional opponents and placeholder blockout art.

## Separation

The existing Django/cPanel deployment, GitHub Actions relay, and live `/ramadan-war/` route are untouched. Do not add this project's build output to production until the gates above pass.
