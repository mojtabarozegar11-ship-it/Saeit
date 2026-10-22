import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"factory_six_native_independent_rework.py"
spec=importlib.util.spec_from_file_location("factory_review_under_test",str(SCRIPT))
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

def hashblob(raw):
    return hashlib.sha256(raw).hexdigest()

def zbytes(files):
    buff=io.BytesIO()
    with zipfile.ZipFile(buff,"w",zipfile.ZIP_DEFLATED) as z:
        for k,v in sorted(files.items()):
            z.writestr(k,v)
    return buff.getvalue()

def fakeexe():
    blob=bytearray(30_100)
    blob[:2]=b"MZ"
    blob[60:64]=(128).to_bytes(4,"little")
    blob[128:132]=b"PE\x00\x00"
    return bytes(blob)

def fixtures(root, labelled_accessibility=False):
    src=root/"native-candidate-evidence"/"39714521227-1"
    src.mkdir(parents=True)
    reference=[]
    for f in review.FAMILIES:
        folder=src/f
        folder.mkdir()
        if f in ("F12","F16"):
            apk=zbytes({"AndroidManifest.xml":b"manifest","classes.dex":b"dex",
                        "assets/index.html":b"app"})
            aab=zbytes({"base/manifest/AndroidManifest.xml":b"manifest",
                        "base/dex/classes.dex":b"dex",
                        "base/assets/index.html":b"app"})
            files={"app-debug.apk":apk,"app-debug.aab":aab}
        elif f in ("F13","F17"):
            files={"native-test.exe":fakeexe()}
        elif f=="F14":
            markup=('<canvas id="board" aria-label="Interactive game" role="img"></canvas>'
                    '<p id="score" role="status">Score 0</p>') if labelled_accessibility else (
                    '<canvas id="board"></canvas><p id="score">Score 0</p>')
            html=markup.encode()
            js=b"function move() {}"
            browser={"actual_chromium_executed":True,
                     "real_interactive_movement_tested":True,
                     "keyboard_and_restart_tested":True,
                     "responsive_viewports_tested":["desktop","mobile"],
                     "uncaught_js_errors":0,"external_network_requests":0,
                     "source_sha256":{"mini_game.html":hashblob(html),"game.js":hashblob(js)}}
            files={"mini_game.html":html,"game.js":js,
                   "browser-proof.json":json.dumps(browser).encode()}
        else:
            files={("model_%02d.onnx"%i):("onnx %d"%i).encode()
                   for i in range(1,49)}
            model_proofs=[{"file":k,"sha256":hashblob(v)} for k,v in sorted(files.items())]
            proof={"actual_onnxruntime_models_checked":48,"holdout_predictions_checked":192,
                   "independent_quality_1000_certified":False,"models":model_proofs}
            files["native-proof.json"]=json.dumps(proof).encode()
        archive=zbytes(files)
        (folder/"technical-native-candidate.zip").write_bytes(archive)
        receipt={"schema":"saeit.factory.private-six-native-candidate.v1",
            "family":f,"format_candidate_count":review.COUNT[f],
            "actual_native_file_format_tested_in_ci":True,
            "physical_device_matrix_verified":False,
            "independent_specialist_review_verified":False,
            "quality_1000_certified":False,"commercial_release":False,
            "public_transfer":False,"owner_signature":None,
            "archive_sha256":hashblob(archive),
            "archive_members_sha256":{k:hashblob(v) for k,v in files.items()}}
        (folder/"technical-native-receipt.json").write_text(json.dumps(receipt))
        reference.append({"family":f,"native_candidate_files":review.COUNT[f],
                          "verified_on_vps":True,"archive_sha256":hashblob(archive)})
    aggregate={"schema":"saeit.factory.native-six-vps-aggregate.v1",
        "six_families_verified":6,"candidate_native_file_count":56,
        "private_only":True,"production_release_authorized":False,
        "independent_specialist_quality_1000_certified":0,
        "sites_modified":0,"files":reference}
    (src/"verified-six-private-native.json").write_text(json.dumps(aggregate))
    return src

class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)

    def test_six_real_format_trust_chain_and_immutable_dispatch(self):
        fixtures(self.root)
        data=review.run(self.root,"39714521227-1")
        self.assertEqual(data["verified_native_candidate_files"],56)
        self.assertEqual(data["reviewed_families"],6)
        self.assertEqual(data["source_rework_needed"],1)
        self.assertFalse(data["master_controller_connected_to_this_queue"])
        self.assertEqual(data["completed_professional_quality_1000_certifications"],0)
        f14=next(x for x in data["families"] if x["family_id"]=="F14")
        self.assertEqual(f14["remediable_source_defects"],
                         ["canvas_accessible_name_missing","score_live_region_missing"])
        self.assertEqual(f14["producer_adapter"],"game_web_build")
        self.assertFalse(f14["commercial_release_authorized"])
        self.assertEqual(review.run(self.root,"39714521227-1"),data)

    def test_f14_fixes_remove_true_machine_findings(self):
        fixtures(self.root,labelled_accessibility=True)
        data=review.run(self.root,"39714521227-1")
        self.assertEqual(data["source_rework_needed"],0)
        f14=next(x for x in data["families"] if x["family_id"]=="F14")
        self.assertEqual(f14["remediable_source_defects"],[])
        self.assertEqual(f14["status"],"awaiting_independent_professional_validation")
        self.assertFalse(f14["quality_1000_certified"])

    def test_member_tamper_fails_and_does_not_create_review(self):
        source=fixtures(self.root)
        p=source/"F26"/"technical-native-candidate.zip"
        p.write_bytes(p.read_bytes()+b"TAMPER")
        with self.assertRaisesRegex(RuntimeError,"REVIEW_ARCHIVE_HASH_CHANGED"):
            review.run(self.root,"39714521227-1")
        self.assertFalse((self.root/"quality-excellence"/"six-native-rework").exists())

    def test_false_1000_and_aggregate_hash_both_rejected(self):
        source=fixtures(self.root)
        p=source/"F12"/"technical-native-receipt.json"
        receipt=json.loads(p.read_text())
        receipt["quality_1000_certified"]=True
        p.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(RuntimeError,"REVIEW_RECEIPT_PROVENANCE_POLICY_FAILED"):
            review.run(self.root,"39714521227-1")
        with self.assertRaisesRegex(RuntimeError,"REVIEW_EXPECTED_AGGREGATE_HASH_MISMATCH"):
            review.run(self.root,"39714521227-1","0"*64)

if __name__=="__main__":
    unittest.main()
