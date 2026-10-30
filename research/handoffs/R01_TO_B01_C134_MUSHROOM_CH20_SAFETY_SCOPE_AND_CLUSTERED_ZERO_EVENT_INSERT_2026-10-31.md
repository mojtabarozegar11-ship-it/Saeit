# R-01 → B-01 | Chapter 20 ready-to-insert scientific editorial replacement | 2026-10-31

**Owner of target chapter:** B-01. **Handoff state:** READY_FOR_B_EDITOR_REVIEW, not merged into the book; no product-safety validation or legal advice.

## Proposed replacement: regulatory scope and limits of zero-event observations

“Occupational-safety requirements for mushroom production depend on the specific activity, workplace and jurisdiction. U.S. federal OSHA's [29 CFR §1928.21(a)–(b)](https://www.osha.gov/laws-regs/regulations/standardnumber/1928/1928.21) specifies which listed general-industry provisions apply to agricultural operations and limits other Part 1910 provisions for such operations. It does **not** establish that every mushroom cultivation, packing, processing or distribution task has the same legal classification. A qualified safety professional should identify the actual processes, state-plan requirements and applicable rules before a manual calls a provision mandatory or claims an exemption.

A report of zero observed events among 24 units is a **sample observation**, not proof of zero risk or of compliance. Under an explicitly assumed independent, identically distributed Bernoulli model with complete event ascertainment, the exact one-sided 95% upper confidence bound for an event probability is 1−0.05^(1/24) ≈ 11.73%; the corresponding exact two-sided 95% Clopper–Pearson upper endpoint is 1−0.025^(1/24) ≈ 14.25%. These calculations require **24 independent observational units**. If the 24 observations are mushrooms from a single harvest, samples from one batch, repeated measurements on the same farm, or otherwise clustered, treating them as 24 independent trials is unjustified. Without verified batch/farm/lot IDs, sampling method, exposure time, outcome definition and detection method, neither interval is a defensible estimate of commercial hazard prevalence. No negative microbiological test alone establishes product safety. A qualified food-safety and occupational-safety review is necessary before any commercial claims.”

## B editor's exact acceptance checklist

| Required input | Decision if missing |
|---|---|
| Chapter 20 exact source passage and defined process (cultivation/packing/processing) | HOLD OSHA applicability assertion |
| Federal vs state-plan jurisdiction and activity classification | HOLD mandatory-rule/exemption claim |
| 24 observation IDs, batch/farm clusters, sampling dates and selection method | HOLD binomial inference; retain descriptive 0/24 only if observation itself documented |
| Outcome definition, detection limit, assay/observation provenance | HOLD safety or prevalence interpretation |
| Named interval method and one-sided/two-sided choice | HOLD any 95% bound |
| Independent qualified review and author acceptance | HOLD publication and commercial safety claims |

**Primary source:** OSHA official §1928.21, accessed 2026-10-31. **Math:** exact zero-event binomial confidence bound; conditional on iid Bernoulli sampling. The earlier C133 note computed the bounds; this C134 insert adds **explicit clustered-sampling exclusion and an editor-ready replacement passage** rather than implying that the book's unknown sample design satisfies the model.

**Next for B:** compare this replacement against exact Chapter 20 text, collect original sampling provenance if a 0/24 assertion is present, obtain specialist review, and merge only through B's own publication workflow. No factory, site or shared-file modification authorized by this handoff.
