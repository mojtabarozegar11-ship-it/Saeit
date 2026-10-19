from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
from master_gen28 import Generation28ProofGate

@dataclass(frozen=True)
class PreservationProof:
    passed: bool
    checked: int
    mismatches: tuple[str,...]

class LegacyManifestVerifier:
    """Verifies a sha256sum manifest so additive releases can prove legacy bytes were preserved."""
    def verify(self,root,manifest):
        root=Path(root); mismatches=[]; checked=0
        for line in Path(manifest).read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            digest,rel=line.split(None,1); rel=rel.strip().lstrip('*'); p=root/rel
            checked+=1
            actual=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
            if actual!=digest: mismatches.append(rel)
        return PreservationProof(not mismatches,checked,tuple(mismatches))

class Generation32ProofGate(Generation28ProofGate):
    """Gen32 keeps the >=40% stratified performance gate and requires byte-preservation evidence."""
    def compare_with_preservation(self,baseline,candidate,strata,preservation:PreservationProof):
        return self.compare(baseline,candidate,strata,preservation.passed)
