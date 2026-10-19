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

The recipe test suite must complete within 60 seconds on the VPS Python runtime.
Symlinks, malformed folder names, missing documentation, or missing tests stop
catalog discovery. A failing test blocks that recipe's package. Each package is
written privately and reproducibly; discovery never publishes products or sets a
price. Commercial review and owner approval remain separate gates.

The build queue has no fixed recipe-count ceiling and runs sequentially to fit VPS
resources. An optional CLI limit can be used for a diagnostic run. API and token
usage remain zero for deterministic local manufacturing.
