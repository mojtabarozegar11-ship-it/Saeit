/* MojPlayWin | orbital globe satellites
 * Runs on the MAIN homepage only. No network requests, private data, storage,
 * commerce actions or changes to independent subsite pages.
 *
 * Sphere surface motion is drawn within global-technology-orbit.svg while the
 * base and golden orbit rings remain fixed. These four links travel along a
 * real ellipse with perspective scaling, not independent floating jitters.
 */
(() => {
  "use strict";
  const visual = document.querySelector(
    '[data-mojplaywin-orbital="v1"] .mpo-hero-visual[data-globe-orbit]'
  );
  if (!visual) return;
  const satellites = Array.from(visual.querySelectorAll(".mpo-satellite"));
  const toggle = document.querySelector(
    '[data-mojplaywin-orbital="v1"] [data-globe-motion-toggle]'
  );
  if (satellites.length !== 4 || !toggle) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const cycleMs = 34000;
  const phases = [Math.PI, Math.PI * 1.5, 0, Math.PI * 0.5];
  let active = true;
  let visible = true;
  let hovering = false;
  let focused = false;
  let touchDown = false;
  let stopped = false;
  let raf = 0;
  let lastFrame = 0;
  let elapsed = 0;
  let observer = null;

  const canAnimate = () => active && visible && !document.hidden &&
    !hovering && !focused && !touchDown && !reduced.matches && !stopped;

  function placeSatellites() {
    const w = visual.clientWidth;
    const h = visual.clientHeight;
    if (!w || !h) return;
    // The ellipse projects in front of and behind the existing globe.
    // Coordinates are relative to the exact visual center and scale with
    // the mobile and desktop containers.
    const radiusX = w * 0.385;
    const radiusY = h * 0.205;
    const phase = (elapsed % cycleMs) * (Math.PI * 2 / cycleMs);
    satellites.forEach((card, i) => {
      const angle = phase + phases[i];
      const x = Math.cos(angle) * radiusX;
      const y = Math.sin(angle) * radiusY;
      const depth = (Math.sin(angle) + 1) / 2;
      const scale = 0.77 + 0.34 * depth;
      const tilt = -Math.cos(angle) * 14;
      card.style.transform = `translate3d(calc(-50% + ${x.toFixed(2)}px), calc(-50% + ${y.toFixed(2)}px), 0) scale(${scale.toFixed(3)}) rotateY(${tilt.toFixed(2)}deg)`;
      card.style.opacity = (0.72 + 0.28 * depth).toFixed(2);
      card.style.zIndex = depth >= 0.5 ? "4" : "1";
    });
  }

  function frame(now) {
    raf = 0;
    if (!canAnimate()) return;
    if (lastFrame) elapsed += Math.min(now - lastFrame, 80);
    lastFrame = now;
    placeSatellites();
    raf = window.requestAnimationFrame(frame);
  }

  function renderToggle() {
    toggle.disabled = reduced.matches;
    if (reduced.matches) {
      toggle.textContent = "Motion reduced in device settings";
      toggle.setAttribute("aria-pressed", "false");
      return;
    }
    toggle.textContent = active ? "Pause satellite orbit ⏸" : "Resume satellite orbit ▶";
    toggle.setAttribute("aria-pressed", String(!active));
  }

  function update() {
    if (reduced.matches) {
      if (raf) window.cancelAnimationFrame(raf);
      raf = 0;
      lastFrame = 0;
      visual.dataset.orbitMotion = "reduced";
      satellites.forEach(card => {
        card.style.removeProperty("transform");
        card.style.removeProperty("opacity");
        card.style.removeProperty("z-index");
      });
      renderToggle();
      return;
    }
    visual.dataset.orbitMotion = "active";
    if (canAnimate()) {
      if (!raf) raf = window.requestAnimationFrame(frame);
    } else {
      if (raf) window.cancelAnimationFrame(raf);
      raf = 0;
      lastFrame = 0;
    }
    renderToggle();
  }

  toggle.addEventListener("click", () => {
    active = !active;
    update();
  });
  visual.addEventListener("pointerenter", event => {
    if (event.pointerType === "touch") return;
    hovering = true;
    update();
  });
  visual.addEventListener("pointerleave", () => {
    hovering = false;
    update();
  });
  visual.addEventListener("pointerdown", event => {
    if (event.pointerType !== "touch") return;
    touchDown = true;
    update();
  });
  const touchEnd = () => {
    if (touchDown) { touchDown = false; update(); }
  };
  visual.addEventListener("pointerup", touchEnd);
  visual.addEventListener("pointercancel", touchEnd);
  visual.addEventListener("focusin", () => {
    focused = true;
    update();
  });
  visual.addEventListener("focusout", event => {
    if (event.relatedTarget && visual.contains(event.relatedTarget)) return;
    focused = false;
    update();
  });
  document.addEventListener("visibilitychange", update);
  window.addEventListener("resize", placeSatellites, {passive: true});
  if (typeof reduced.addEventListener === "function")
    reduced.addEventListener("change", update);

  if ("IntersectionObserver" in window) {
    observer = new IntersectionObserver(entries => {
      visible = entries.some(item => item.isIntersecting);
      update();
    }, {threshold: 0.04});
    observer.observe(visual);
  }

  window.addEventListener("pagehide", () => {
    stopped = true;
    if (raf) window.cancelAnimationFrame(raf);
    raf = 0;
    if (observer) observer.disconnect();
  }, {once: true});

  update();
  if (!reduced.matches) placeSatellites();
})();