# Checkout Version Comparator

Version 1.0.0 is a local, read-only Git snapshot comparison tool. It reports
added, removed, and modified file paths under a selected Checkout source path,
using commit IDs, Git blob IDs, and byte counts. It does not print source text,
make network requests, change refs, or modify the working tree. Files with
secret-like names are omitted.

```sh
python3 checkout_version_compare.py \
  --repo /path/to/local/repository \
  --base <base-commit-or-tag> \
  --candidate <candidate-commit-or-tag> \
  --path <repository-relative-checkout-source-path>
```

Use immutable commit IDs for repeatable comparisons. The tool only inspects
objects already present in the local repository. It does not certify that a
Checkout flow works in production, that payment succeeded, or that any source
is approved for deployment.

Tests use temporary Git repositories and synthetic source files:

```sh
python3 -m unittest -v
```
