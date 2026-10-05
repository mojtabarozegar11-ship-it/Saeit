
"""Workspace-confined immutable artifact builder for the static research brief product."""
import hashlib
import html
import json
import os
from pathlib import Path

from django.conf import settings


class FactoryBuildError(RuntimeError):
    pass


class StaticResearchBriefBuilder:
    product_type = "static_research_brief"

    def __init__(self, workspace_root=None):
        configured = workspace_root or getattr(settings, "FACTORY_WORKSPACE_ROOT", None)
        if not configured:
            configured = Path(settings.BASE_DIR) / "factory-workspace"
        self.root = Path(configured).resolve()

    def build(self, *, run_id, product_id, version, spec, evidence):
        if not run_id or any(part in str(run_id) for part in ("/", "\\", "..")):
            raise FactoryBuildError("Invalid Factory Run identifier.")
        if not isinstance(spec, dict) or not isinstance(spec.get("acceptance_criteria"), list):
            raise FactoryBuildError("A versioned Product spec is required.")
        records = []
        for item in evidence:
            if not isinstance(item, dict) or not item.get("passage") or not item.get("source"):
                raise FactoryBuildError("Builder requires persisted source-backed evidence.")
            records.append(
                "<li><a href=\"{}\">{}</a>: {}</li>".format(
                    html.escape(str(item["source"]), quote=True),
                    html.escape(str(item.get("title") or item["source"])),
                    html.escape(str(item["passage"])),
                )
            )
        body = (
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>{}</title><main><h1>{}</h1><p>{}</p><ul>{}</ul></main></html>"
        ).format(
            html.escape(str(spec.get("title") or "Research brief")),
            html.escape(str(spec.get("title") or "Research brief")),
            html.escape(str(spec.get("problem") or "")),
            "".join(records),
        )
        content = body.encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        destination = (self.root / str(run_id) / str(product_id) / f"v{int(version)}" / "index.html").resolve()
        if destination != self.root and self.root not in destination.parents:
            raise FactoryBuildError("Artifact path escapes the configured Factory workspace.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = destination.read_bytes()
            if hashlib.sha256(existing).hexdigest() != digest:
                raise FactoryBuildError("Immutable artifact version already exists with different content.")
        else:
            temporary = destination.with_suffix(".html.tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
                destination.chmod(0o444)
            except FileExistsError as exc:
                raise FactoryBuildError("Artifact version is already being written.") from exc
            finally:
                if temporary.exists():
                    temporary.unlink()
        return {
            "ref": str(destination),
            "sha256": digest,
            "version": int(version),
            "product_type": self.product_type,
            "spec_version": int(spec.get("version") or 1),
        }
