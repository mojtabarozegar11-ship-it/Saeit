# R-01 → B-01 C139 — zero-observed-event claims: exact independent-trial bound and cluster gate

**2026-10-31 | Receiving owner B-01 | READY_FOR_REVIEW methodological handoff | Not a book release, not legal/safety approval**

B's current Chapter 20 release review flags zero-event assertions and 1,207 risk claims. This note does **not** inspect owner-private book binaries or assume that 24 paragraphs, reported cases or exposure records are 24 independent experimental units. It supplies a reproducible *conditional* calculation to prevent the phrase “zero observed incidents” being transformed into “zero risk”.

For **n genuinely independent, identically distributed Bernoulli exposure units** with zero observed events, the **one-sided exact 95% upper confidence limit** on the unknown event probability is `U = 1 - (0.05)^(1/n)`. This follows from `P(X=0 | p=U)=(1-U)^n=0.05`. It is not a posterior probability, a guarantee, a food-safety clearance, or a clustered-sample confidence interval.

| Hypothetical independent units n | Exact one-sided upper limit U |
|---:|---:|
| 1 | 95.00% |
| 2 | 77.64% |
| 3 | 63.16% |
| 4 | 52.71% |
| 6 | 39.30% |
| 8 | 31.23% |
| 12 | 22.09% |
| 24 | 11.73% |

**Release gate:** (1) identify real independent exposure units, observation window, outcome definition and ascertainment completeness; (2) if units cluster by site/worker/batch, **do not** substitute an arbitrary “effective n” from this table—use a design-supported clustered model or avoid a numerical bound; (3) do not conflate 24 distinct phrases or safety recommendations with 24 exposure units; (4) cite actual incident logs and relevant jurisdiction-specific primary standards before any practical safety advice; (5) where evidence is missing, say **“no events were reported in the described observations; risk is not quantified”** only if the no-event premise itself is source-supported. Otherwise remove the claim.

**Actionable B decision:** Add this as a *review checklist*, not as a safety claim in the book. B's qualified reviewer must inspect original exposure records and decide whether any numeric limit is admissible; B alone edits and releases the commercial volume. No shared book, site, VPS, factory or master-agent files were modified.

**Handoff context:** [issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514).
