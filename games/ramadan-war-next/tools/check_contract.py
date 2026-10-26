#!/usr/bin/env python3
"""Cheap structural safety gate. Does not claim to compile Unity or rate gameplay."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
required = {
    "Assets/Scripts/RWBootstrap.cs": ("RuntimeInitializeOnLoadMethod", "BuildTrainingCompound", "BuildObjectives"),
    "Assets/Scripts/RWPlayerMotor.cs": ("CharacterController", "Touch.activeTouches", "Physics.Raycast", "Reload"),
    "Assets/Scripts/RWEnemyBrain.cs": ("enum RoleType", "CanSee", "Behaviour.Flank", "FireAt"),
    "Assets/Scripts/RWGameState.cs": ("MissionPhase", "TryInteract", "RWObjective.Kind.Extraction", "Lives"),
    "Assets/Editor/RWBuild.cs": ("BuildTarget.WebGL", "BuildTarget.Android", "BuildResult.Succeeded"),
    "ProjectSettings/ProjectVersion.txt": ("6000.",),
    "Assets/Art/ASSET-POLICY.md": ("license", "SHA-256", "texture"),
}
for path, tokens in required.items():
    f = root / path
    assert f.is_file(), f"missing project component: {path}"
    data = f.read_text(encoding="utf-8")
    for token in tokens:
        assert token in data, f"missing expected feature in {path}: {token}"
    if path.endswith(".cs"):
        # Conservative lexical balance guard. Unity compilation still required.
        stripped = []
        in_string = False
        escaped = False
        for char in data:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            else:
                stripped.append(char)
        clean = "".join(stripped)
        assert clean.count("{") == clean.count("}"), f"unbalanced C# braces: {path}"

# Static regression for Unity prefabs whose visible mesh is nested under the enemy root.
# This is NOT a substitute for Unity compilation or a runtime prefab test.
brain = (root / "Assets/Scripts/RWEnemyBrain.cs").read_text(encoding="utf-8")
assert "GetComponentInChildren<Renderer>()" in brain, "enemy mesh must be resolved from child prefabs"
assert "if (renderComponent != null) originalColor = renderComponent.material.color;" in brain, "renderer-less prefab must not crash AI initialization"

manifest = json.loads((root / "Packages/manifest.json").read_text())
deps = manifest["dependencies"]
for package in ("com.unity.inputsystem", "com.unity.render-pipelines.universal", "com.unity.ugui"):
    assert package in deps, f"missing package {package}"
for ext in ("*.glb", "*.fbx", "*.obj", "*.wav", "*.mp3"):
    assert not list((root/"Assets").rglob(ext)), f"unreviewed third-party asset ({ext})"
assert not (root / "Builds").exists(), "Build output must not be committed to source"
print("RAMADAN_NEXT_STRUCTURAL_CONTRACT=PASS (not a Unity compile or playtest)")
