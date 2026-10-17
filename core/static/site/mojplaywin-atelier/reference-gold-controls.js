/* Scoped home-only reference UI enhancements. Core drag/swipe/arrow/keyboard
   controller stays in orbits.js. No cookies, remote code, timers or writes. */
(() => {
  "use strict";
  const root = document.querySelector('[data-mojplaywin-orbital="v1"]');
  if (!root) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  for (const ring of root.querySelectorAll(".mpo-ring[data-orbit]")) {
    const track = ring.querySelector(".mpo-orbit-track");
    const shell = ring.querySelector(".mpo-track-shell");
    if (!track || !shell) continue;
    const cards = Array.from(track.querySelectorAll(".mpo-orbit-item"));
    if (cards.length < 2) continue;
    const dots = document.createElement("div");
    dots.className = "mpo-ring-dots";
    dots.setAttribute("role", "group");
    dots.setAttribute("aria-label", "Choose a card in this category");
    let frame = 0;
    const controls = cards.map((card, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "mpo-ring-dot";
      dot.setAttribute("aria-label", "Show card " + (index + 1) + ": " +
        (card.querySelector("strong")?.textContent || "").trim());
      dot.addEventListener("click", () => {
        const x = card.offsetLeft - track.offsetLeft -
          Math.max(0, (track.clientWidth - card.clientWidth) / 2);
        track.scrollTo({left: Math.max(0, x), behavior: reduced.matches ? "instant" : "smooth"});
        track.focus({preventScroll: true});
      });
      dots.appendChild(dot);
      return dot;
    });
    shell.insertAdjacentElement("afterend", dots);
    function sync() {
      frame = 0;
      const middle = track.getBoundingClientRect().left + track.clientWidth / 2;
      let closest = 0;
      let delta = Infinity;
      cards.forEach((card, i) => {
        const r = card.getBoundingClientRect();
        const d = Math.abs(r.left + r.width / 2 - middle);
        if (d < delta) { delta = d; closest = i; }
      });
      controls.forEach((dot, i) => {
        if (i === closest) dot.setAttribute("aria-current", "true");
        else dot.removeAttribute("aria-current");
      });
    }
    track.addEventListener("scroll", () => {
      if (!frame) frame = window.requestAnimationFrame(sync);
    }, {passive:true});
    window.addEventListener("resize", sync, {passive:true});
    sync();
  }
})();