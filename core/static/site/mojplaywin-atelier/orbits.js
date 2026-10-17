/* MojPlayWin orbital carousels: mouse drag, native touch swipe, keyboard, arrows and optional motion.
   Local script, no cookies, analytics, network access or commerce side effects. */
(() => {
  "use strict";
  const root = document.querySelector('[data-mojplaywin-orbital="v1"]');
  if (!root) return;
  const rings = [...root.querySelectorAll("[data-orbit]")];
  const toggle = root.querySelector("[data-orbit-toggle]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let timer = null;
  let visible = true;
  const speed = () => reduceMotion.matches ? "instant" : "smooth";

  function turn(ring, direction, userAction = true) {
    const track = ring.querySelector(".mpo-orbit-track");
    const card = track.querySelector(".mpo-orbit-item");
    if (!card) return;
    const step = card.getBoundingClientRect().width + 15;
    const max = Math.max(0, track.scrollWidth - track.clientWidth);
    const destination = track.scrollLeft + direction * step;
    if (destination > max - 8 && direction > 0) {
      track.scrollTo({left: 0, behavior: speed()});
    } else if (destination < 8 && direction < 0) {
      track.scrollTo({left: max, behavior: speed()});
    } else {
      track.scrollBy({left: direction * step, behavior: speed()});
    }
    if (userAction) stopRotation();
  }

  function stopRotation() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    if (toggle) {
      toggle.setAttribute("aria-pressed", "false");
      toggle.innerHTML = 'Start gentle rotation <span aria-hidden="true">▶</span>';
    }
  }

  function startRotation() {
    if (reduceMotion.matches || timer !== null) return;
    timer = window.setInterval(() => {
      if (!visible || document.hidden || root.matches(":hover") ||
          root.contains(document.activeElement)) return;
      rings.forEach(ring => turn(ring, 1, false));
    }, 5000);
    if (toggle) {
      toggle.setAttribute("aria-pressed", "true");
      toggle.innerHTML = 'Pause gentle rotation <span aria-hidden="true">Ⅱ</span>';
    }
  }

  rings.forEach(ring => {
    const track = ring.querySelector(".mpo-orbit-track");
    ring.querySelector("[data-orbit-prev]").addEventListener("click", () => turn(ring, -1));
    ring.querySelector("[data-orbit-next]").addEventListener("click", () => turn(ring, 1));
    track.addEventListener("keydown", event => {
      if (event.target !== track) return;
      if (event.key === "ArrowRight") {event.preventDefault(); turn(ring, 1);}
      if (event.key === "ArrowLeft") {event.preventDefault(); turn(ring, -1);}
    });

    // Touch and trackpad use the browser's native horizontal scroller.
    // Desktop mouse users also get controlled drag without disabling links.
    let startX = 0, startScroll = 0, moved = false, isDragging = false;
    let blockClick = false;
    track.addEventListener("pointerdown", event => {
      if (event.pointerType !== "mouse" || event.button !== 0) return;
      startX = event.clientX;
      startScroll = track.scrollLeft;
      moved = false;
      isDragging = true;
    });
    track.addEventListener("pointermove", event => {
      if (!isDragging) return;
      const delta = startX - event.clientX;
      if (Math.abs(delta) > 6) {
        moved = true;
        track.scrollLeft = startScroll + delta;
      }
    });
    window.addEventListener("pointerup", () => {
      if (isDragging && moved) {
        blockClick = true;
        stopRotation();
        // Block the synthetic link click dispatched immediately after drag.
        window.setTimeout(() => {blockClick = false;}, 0);
      }
      isDragging = false;
    });
    track.addEventListener("click", event => {
      if (blockClick && event.target.closest("a")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        blockClick = false;
      }
    }, true);
    track.addEventListener("scroll", () => {
      if (reduceMotion.matches) return;
      const railCenter = track.getBoundingClientRect().left + track.clientWidth / 2;
      for (const card of track.querySelectorAll(".mpo-orbit-item")) {
        const rect = card.getBoundingClientRect();
        const ratio = Math.max(-1, Math.min(1, (rect.left + rect.width / 2 - railCenter) / Math.max(track.clientWidth / 2, 1)));
        const surface = card.querySelector(".mpo-orbit-card");
        surface.style.setProperty("--mpo-angle", (ratio * -8).toFixed(1) + "deg");
        surface.style.setProperty("--mpo-rise", (Math.abs(ratio) * 7).toFixed(1) + "px");
      }
    }, {passive: true});
  });

  if (toggle) {
    toggle.addEventListener("click", () => {
      if (timer !== null) stopRotation();
      else startRotation();
    });
    if (reduceMotion.matches) {
      toggle.disabled = true;
      toggle.textContent = "Motion reduced in device settings";
    }
  }

  const observer = "IntersectionObserver" in window
    ? new IntersectionObserver(entries => {
        visible = entries.some(entry => entry.isIntersecting);
      }, {threshold: 0.04}) : null;
  if (observer) observer.observe(root);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && timer !== null) stopRotation();
  });
  if (typeof reduceMotion.addEventListener === "function") {
    reduceMotion.addEventListener("change", () => {
      stopRotation();
      if (toggle) {
        toggle.disabled = reduceMotion.matches;
        toggle.textContent = reduceMotion.matches
          ? "Motion reduced in device settings" : "Start gentle rotation ▶";
      }
    });
  }
  window.addEventListener("pagehide", () => {
    stopRotation();
    if (observer) observer.disconnect();
  }, {once: true});
})();
