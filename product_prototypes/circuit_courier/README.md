# Circuit Courier — original offline logic-route game (Astra Game Lab)

**Private research prototype, not a verified commercial release.** A playable
HTML/CSS/JavaScript game with 36 deterministically generated puzzle stages.
It is unrelated to the three Astra farm decision calculators: it is the
first game-oriented specialist builder candidate. No real money, ads,
tracking, accounts, payment flow, or external dependencies.

## Play

Unzip the product locally and open **index.html** in a browser. Works with
keyboard arrow keys and on-screen directional controls; status messages,
named grid cells and focus-visible controls support basic accessibility.
This interface has **not** yet been evaluated by independent assistive-
technology users.

Each 6×6 level contains **three signal beacons**, blockers and an exit.
Collect all three and reach the exit within the energy budget. The puzzle
generator uses a fixed seeded PRNG with different seeds per stage; the
solution length is determined by exhaustive BFS over *(location, collected
beacon mask)*. A hint uses the same exact shortest-path algorithm but limits
the game award to one star. Best performance is three stars.

Progress is stored **only** in this browser's localStorage and is never
uploaded. Clearing browser storage removes it. There is no login or prize.
The game renders user-independent fixed symbols and text-safe DOM nodes.
No third-party fonts, music, branding, APIs, or copyrighted game levels are
packaged. All code and 36 procedural boards are independently authored here.

## Verify build

```bash
python3 self_test.py
# Optional if Node.js is installed:
node test_engine.js
```

Product QA independently walks the shortest solution for each of the 36
levels, checks their different board layouts, game win states, hint behavior,
bounds, disabled illegal actions and deterministic reproducibility. A
successful numerical QA is **not** independent user experience, creativity,
retention or demand validation.

## Selection rationale, differentiation hypotheses and doubts

The original factory was concentrated in agricultural auditing. A free,
offline game is a distinct *type* of digital artifact and explores a different
user interest (self-contained logic/puzzle play for English-language users).
The game combines (1) collecting three objectives in any order, (2) a limited
movement budget and (3) a verifiable hint based on an exact shortest route.
This is **a proposed combination**, not proof of novelty or competitive
advantage. The market has many free puzzle games, and **a paid market price
cannot be justified from this prototype alone**. In particular, the recent
competing financial planning products surveyed below show why simply cloning
another game revenue calculator was rejected as an idea:

- Existing indie game revenue tools: https://nirox123.itch.io/indie-game-revenue-calculator
- Existing browser-based financial simulator: https://betterbasis.itch.io/indie-game-profit-planner
- Existing launch net revenue calculator: https://theluckyduck666.itch.io/launchsmith-pro

These **are alternatives to a rejected *financial-tool* idea, not competitors
for Circuit Courier's actual puzzle gameplay**. Game-puzzle competitor
research and direct user demand study have **not** been completed; no claim
of competitive product positioning is implied by those URLs.

## Hard release blockers

1. Real independent puzzle-player trials: enjoyment, difficulty curve,
   successful tutorial comprehension, controls and accessibility.
2. Originality and licensing/security reviews against direct puzzle games.
3. Independent product QA on mobile browsers, keyboard navigation and
   screen readers, plus real retention and voluntary willingness-to-pay data.
4. Competitive differentiation with evidence from relevant *games*.
5. Marketplace policy and storefront compatibility, user support, pricing,
   marketing rights and payment-fulfilment review.

A technically passing reference build remains private. **No external
publishing, real payments or sale authorization are enabled**. The Astra
factory queue can build this approved source revision independently of
customer orders only after explicit private-only scheduling is enabled in
a separately reviewed environment.
