#!/usr/bin/env python3
"""Build authentic format candidates from the six source-proofed factory lines.

Never implies native device QA, human specialist review or quality 1000.
The preceding source manufacturer and its SHA-bound receipt MUST pass before
anything is prepared. Native artifacts are produced and tested by separate CI.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
FAMILIES = ("F12", "F13", "F14", "F16", "F17", "F26")
SLUGS = {"F12": "mobile_puzzle_game", "F13": "desktop_puzzle_game",
         "F16": "mobile_inventory_app", "F17": "desktop_inventory_software",
         "F26": "machine_learning_model"}

def module(filename):
    p = HERE / filename
    if p.is_symlink() or not p.is_file():
        raise RuntimeError("NATIVE_MISSING_PINNED_SOURCE")
    spec = importlib.util.spec_from_file_location("factory_source_proof", str(p))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inputs(root, family, dest):
    """Select exact receipt-backed source version; never arbitrary newest paths."""
    if family not in FAMILIES:
        raise ValueError("NATIVE_UNKNOWN_FAMILY")
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("NATIVE_OUTPUT_MUST_BE_NEW")
    agent = module("factory_six_specialist_executors.py")
    state = agent.read(root / "quality-excellence" / "six-agent-supervisor" /
                       "last-full-six-execution.json")
    if state.get("schema") != agent.SCHEMA or set(state.get("selected", [])) != set(FAMILIES):
        raise RuntimeError("NATIVE_SIX_SOURCE_PROOF_MISSING")
    row = next((x for x in state.get("outcomes", []) if x.get("family") == family), None)
    if (not row or row.get("technical_candidate_hash_verified") is not True
            or row.get("quality_1000_certified") is not False):
        raise RuntimeError("NATIVE_SOURCE_NOT_PROVEN")
    digest = row["archive_sha256"]
    if family == "F14":
        parent = root / "engineering-gaps" / "six-missing-executors" / "F14"
        matches = []
        if parent.is_dir() and not parent.is_symlink():
            for folder in parent.iterdir():
                if folder.is_dir() and not folder.is_symlink():
                    receipt = agent.read(folder / "technical_receipt.json")
                    if receipt.get("artifact_sha256") == digest:
                        expected = receipt.get("source_files", {})
                        if (receipt.get("schema") != agent.SCHEMA + ".f14-private-pilot"
                                or receipt.get("quality_1000_certified") is not False
                                or receipt.get("commercial_release") is not False
                                or not isinstance(expected, dict)
                                or set(expected) != {"mini_game.html", "game.js", "browser_game.zip"}):
                            raise RuntimeError("NATIVE_F14_PROOF_INVALID")
                        if any(sha(folder / name) != value for name, value in expected.items()):
                            raise RuntimeError("NATIVE_F14_HASH_MISMATCH")
                        agent.inspect_zip(folder / "browser_game.zip", "",
                                          {"mini_game.html", "game.js"})
                        matches.append(folder)
        if len(matches) != 1:
            raise RuntimeError("NATIVE_F14_UNIQUE_SOURCE_NOT_FOUND")
        original = matches[0]
        files = ("mini_game.html", "game.js", "browser_game.zip")
    else:
        result = {"family_id": family, "private_archive_sha256": digest}
        agent.verify_five(root, family, result)
        name = "fieldwork_" + SLUGS[family] + "_pilot"
        original = (root / "engineering-gaps" / "seven-builders" /
                    name / digest[:20] / name)
        files = tuple(sorted(agent.REQUIRED[family]))
    dest.mkdir(parents=True, mode=0o700)
    for filename in files:
        src = original / filename
        if src.is_symlink() or not src.is_file():
            raise RuntimeError("NATIVE_SOURCE_FILE_UNSAFE")
        shutil.copyfile(src, dest / filename)
        if sha(src) != sha(dest / filename):
            raise RuntimeError("NATIVE_SOURCE_TRANSFER_HASH_MISMATCH")
    return {filename: sha(dest / filename) for filename in files}

def windows_source_inputs(root, family, dest):
    """Native Windows runner: independently revalidate its original producer.

    The Linux factory supervisor uses fcntl and cannot run on Windows; this
    does not weaken the source proof, as archive/member/source hashes are
    checked again here and the exact builder family IDs are constrained.
    """
    import zipfile
    if family not in ("F13", "F17"):
        raise RuntimeError("NATIVE_WINDOWS_ONLY_SPECIALIST")
    builder = module("factory_seven_missing_builders.py")
    candidate = builder.create(root, family)
    if candidate.get("family_id") != family:
        raise RuntimeError("NATIVE_WIN_BUILDER_WRONG_FAMILY")
    digest = candidate.get("private_archive_sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError("NATIVE_WIN_INVALID_VERSION")
    name = "fieldwork_" + SLUGS[family] + "_pilot"
    folder = root / "engineering-gaps" / "seven-builders" / name / digest[:20]
    receipt = json.loads((folder / "technical_receipt.json").read_text(encoding="utf8"))
    if (receipt.get("schema") != "zomorodmelal.factory.seven-gap-private.v1"
            or receipt.get("family_id") != family
            or receipt.get("commercial_release_allowed") is not False
            or receipt.get("independent_quality_1000_passed") is not False
            or receipt.get("native_distribution_verified") is not False
            or receipt.get("private_archive_sha256") != digest):
        raise RuntimeError("NATIVE_WIN_RECEIPT_POLICY_FAILED")
    zipped = folder / (name + "-internal-qa.zip")
    if sha(zipped) != digest:
        raise RuntimeError("NATIVE_WIN_ZIP_HASH_MISMATCH")
    recorded = receipt.get("source_files", {})
    required = ({"game.py", "levels.json", "README.txt"} if family == "F13"
                else {"desktop.py", "sample.csv", "cases.json", "README.txt"})
    if not isinstance(recorded, dict) or not required.issubset(recorded):
        raise RuntimeError("NATIVE_WIN_SOURCE_CONTRACT_BROKEN")
    with zipfile.ZipFile(zipped) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {
                name + "/" + x for x in recorded}:
            raise RuntimeError("NATIVE_WIN_ZIP_MEMBERS_INVALID")
        for filename, expected in recorded.items():
            src = folder / name / filename
            if (src.is_symlink() or not src.is_file()
                    or sha(src) != expected
                    or hashlib.sha256(archive.read(name + "/" + filename)).hexdigest() != expected):
                raise RuntimeError("NATIVE_WIN_SOURCE_HASH_FAIL")
    dest.mkdir(parents=True, mode=0o700)
    for filename in sorted(recorded):
        shutil.copyfile(folder / name / filename, dest / filename)
    return {filename: sha(dest / filename) for filename in recorded}


def android_project(out, family):
    """Offline asset-only Android WebView, with no network permissions."""
    if family not in ("F12", "F16"):
        raise ValueError("NATIVE_NOT_ANDROID")
    package = "com.zomorodmelal.factory." + family.lower()
    root = out / "android"
    app = root / "app"
    assets = app / "src" / "main" / "assets"
    java = app / "src" / "main" / "java" / Path(*package.split("."))
    assets.mkdir(parents=True)
    java.mkdir(parents=True)
    for name in (("index.html", "game.js", "levels.json") if family == "F12"
                 else ("index.html", "app.js", "examples.json")):
        shutil.copyfile(out / "source" / name, assets / name)
    (root / "settings.gradle").write_text("""pluginManagement {
  repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
  repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
  repositories { google(); mavenCentral() }
}
rootProject.name = 'FactoryPrivateNativePilot'
include ':app'
""", encoding="utf8")
    (root / "build.gradle").write_text(
        "plugins { id 'com.android.application' version '8.7.3' apply false }\n",
        encoding="utf8")
    (app / "build.gradle").write_text(
        """plugins { id 'com.android.application' }
android {
  namespace '""" + package + """'
  compileSdk 35
  defaultConfig {
    applicationId '""" + package + """'
    minSdk 24
    targetSdk 35
    versionCode 1
    versionName '0.1.0-technical-pilot'
  }
  buildTypes { release { minifyEnabled false } }
}
""", encoding="utf8")
    manifest = app / "src" / "main" / "AndroidManifest.xml"
    manifest.write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
        '<application android:label="Factory ' + family +
        ' Technical Pilot" android:usesCleartextTraffic="false"'
        ' android:allowBackup="false" android:theme="@android:style/Theme.Material.Light.NoActionBar">'
        '<activity android:name=".MainActivity" android:exported="true">'
        '<intent-filter><action android:name="android.intent.action.MAIN"/>'
        '<category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
        '</activity></application></manifest>\n', encoding="utf8")
    (java / "MainActivity.java").write_text(
        """package """ + package + """;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

public final class MainActivity extends Activity {
  private WebView view;
  private static final String HOST = "appassets.androidplatform.net";
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    view = new WebView(this);
    WebSettings s = view.getSettings();
    s.setJavaScriptEnabled(true);
    // Local DevTools is enabled only for debug APKs used by isolated CI.
    if ((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
      WebView.setWebContentsDebuggingEnabled(true);
    }
    s.setDomStorageEnabled(true);
    s.setAllowFileAccess(false);
    s.setAllowContentAccess(false);
    s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    view.setWebViewClient(new WebViewClient() {
      @Override public boolean shouldOverrideUrlLoading(WebView w, WebResourceRequest r) {
        return !("https".equals(r.getUrl().getScheme()) &&
                 HOST.equals(r.getUrl().getHost()) &&
                 r.getUrl().getPath().startsWith("/assets/"));
      }
      @Override public WebResourceResponse shouldInterceptRequest(WebView w, WebResourceRequest r) {
        String path = r.getUrl().getPath();
        if (!"https".equals(r.getUrl().getScheme()) ||
            !HOST.equals(r.getUrl().getHost()) || !path.startsWith("/assets/")) {
          return denied();
        }
        String filename = path.substring("/assets/".length());
        if (!filename.matches("[a-zA-Z0-9_.-]{1,64}") || filename.contains("..")) {
          return denied();
        }
        try {
          InputStream stream = getAssets().open(filename);
          String mime = filename.endsWith(".js") ? "text/javascript" :
                        filename.endsWith(".json") ? "application/json" : "text/html";
          return new WebResourceResponse(mime, "UTF-8", stream);
        } catch (IOException error) {
          return denied();
        }
      }
      private WebResourceResponse denied() {
        return new WebResourceResponse("text/plain", "UTF-8",
          new ByteArrayInputStream(new byte[0]));
      }
    });
    setContentView(view);
    view.loadUrl("https://" + HOST + "/assets/index.html");
  }
  @Override protected void onDestroy() {
    if (view != null) view.destroy();
    super.onDestroy();
  }
}
""", encoding="utf8")
    return root

def prepare(root, out, family):
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("NATIVE_FACTORY_ROOT_UNSAFE")
    if out.is_symlink() or out.exists():
        raise RuntimeError("NATIVE_OUTPUT_ALREADY_EXISTS")
    out.mkdir(mode=0o700, parents=True)
    hashes = (windows_source_inputs(root, family, out / "source")
              if sys.platform == "win32" and family in ("F13", "F17")
              else inputs(root, family, out / "source"))
    if family in ("F12", "F16"):
        android_project(out, family)
    (out / "preparation-receipt.json").write_text(
        json.dumps({"schema": "saeit.factory.native-prep.v1",
                    "family": family, "source_file_sha256": hashes,
                    "independent_quality_1000_certified": False,
                    "commercial_release": False,
                    "native_format_build_finished": False},
                   sort_keys=True, indent=2) + "\n", encoding="utf8")
    print("NATIVE_SOURCE_PREPARATION=" + json.dumps(
        {"family": family, "files": len(hashes), "sha256_verified": True},
        sort_keys=True))

def export_onnx(out):
    """Serialize and execute 48 actual ONNX graphs from 48 synthetic baselines."""
    import numpy as np
    import onnx
    from onnx import helper, TensorProto
    import onnxruntime as ort
    src = out / "source"
    rows = json.loads((src / "models.json").read_text(encoding="utf8"))
    if len(rows) != 48 or len({r["id"] for r in rows}) != 48:
        raise RuntimeError("NATIVE_F26_WRONG_MODEL_COUNT")
    target = out / "native"
    target.mkdir()
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    checked = []
    holdouts = ((-0.6, 0.9), (2.0, -0.5), (0.0, 0.0), (1.3, 2.7))
    for index, row in enumerate(rows):
        expected_id = "model_%02d" % (index + 1)
        if row["id"] != expected_id or len(row["weights"]) != 2:
            raise RuntimeError("NATIVE_F26_ID_OR_WEIGHTS_MISMATCH")
        weights = np.array(row["weights"], dtype=np.float32).reshape((2, 1))
        bias = np.array([row["bias"]], dtype=np.float32)
        graph = helper.make_graph(
            [helper.make_node("MatMul", ["features", "W"], ["pred0"]),
             helper.make_node("Add", ["pred0", "B"], ["prediction"])],
            expected_id,
            [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 2])],
            [helper.make_tensor_value_info("prediction", TensorProto.FLOAT, [1, 1])],
            initializer=[
                helper.make_tensor("W", TensorProto.FLOAT, [2, 1], weights.flatten()),
                helper.make_tensor("B", TensorProto.FLOAT, [1], bias)])
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
        model.ir_version = min(model.ir_version, 9)
        onnx.checker.check_model(model)
        destination = target / (expected_id + ".onnx")
        onnx.save(model, str(destination))
        session = ort.InferenceSession(str(destination), sess_options=opts,
                                       providers=["CPUExecutionProvider"])
        for x, y in holdouts:
            prediction = float(session.run(None, {"features": np.array([[x, y]],
                                                    dtype=np.float32)})[0][0][0])
            expected = row["weights"][0] * x + row["weights"][1] * y + row["bias"]
            if abs(prediction - expected) > 0.00003:
                raise RuntimeError("NATIVE_F26_ONNX_HOLDOUT_MISMATCH")
        checked.append({"file":destination.name,"sha256":sha(destination)})
    proof = {"schema":"saeit.factory.native-f26-proof.v1",
             "family":"F26", "format":"onnx", "serialized_models":len(checked),
             "actual_onnxruntime_models_checked":len(checked),
             "holdout_predictions_checked":len(checked) * len(holdouts),
             "models": checked, "representative_real_data_tested":False,
             "independent_quality_1000_certified":False, "commercial_release":False}
    (out / "native-proof.json").write_text(
        json.dumps(proof, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print("NATIVE_F26_ONNX_PROOF=" + json.dumps(
        {"models":len(checked),"holdouts":len(checked)*len(holdouts),
         "real_data_verified":False}, sort_keys=True))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--family", required=True, choices=FAMILIES)
    p.add_argument("--onnx", action="store_true")
    a = p.parse_args()
    out = Path(a.output)
    if a.onnx:
        if a.family != "F26" or not out.is_dir():
            raise RuntimeError("NATIVE_F26_PREP_REQUIRED")
        export_onnx(out)
    else:
        prepare(Path(a.factory_private), out, a.family)

if __name__ == "__main__":
    main()
