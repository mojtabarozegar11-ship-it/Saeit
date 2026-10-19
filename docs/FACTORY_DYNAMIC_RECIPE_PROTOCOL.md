# Dynamic product recipe contract

The VPS product factory discovers every immediate directory under `product_recipes/`.
Adding a product family no longer requires editing a Python registry or deployment
installer.

## Add a recipe

1. Create a lowercase slug directory, for example `product_recipes/home_energy_audit/`.
2. Add a `README.md` whose first Markdown heading is the product name.
3. Add the complete product source and at least one `test_*.py` test file. Nested
   assets and source files are included in the private package.
4. Run the recipe tests with Python's standard-library `unittest` runner.
5. Push the change through GitHub. CI discovers, tests, and packages every recipe;
   the VPS deployment ships the complete recipe catalog automatically.

CI validates the recipe runner on Python 3.8, 3.11 and 3.13. Every recipe must
execute at least one unittest case; the minimum is enforced in code and the actual
count is recorded in its manufacturing manifest. The suite must complete within
60 seconds on the VPS Python runtime.
Symlinks, malformed folder names, missing documentation, or missing tests stop
catalog discovery. A failing test blocks that recipe's package. Each package is
written privately and reproducibly. VPS catalog sync replaces stale files exactly;
recipes removed from GitHub are moved to a private retired-recipes archive. Existing
product packages and research ledgers are preserved. Discovery never publishes products or sets a
price. Commercial review and owner approval remain separate gates.

The build queue has no fixed recipe-count ceiling and runs sequentially to fit VPS
resources. An optional CLI limit can be used for a diagnostic run. API and token
usage remain zero for deterministic local manufacturing.

## Capability boundary and quality meaning

Recipe discovery and build instruction creation are automatic after authored source
is added. The factory does not autonomously invent product concepts or write new
product source files from a blank directory. Automatic product invention is
`not_implemented`; the current zero-token design does not call a generative model.
A new recipe still requires a human-authored implementation and tests.

A passing test suite and ZIP check certify only software-level behavior and package
integrity. They do not certify scientific correctness, economic value, originality,
commercial suitability, or legal safety. Those gates remain pending independent
domain review and owner approval. The live VPS research correction queue remains
durable; its 209 unresolved dossiers must be resolved with source-backed research,
not marked complete by the package builder.
