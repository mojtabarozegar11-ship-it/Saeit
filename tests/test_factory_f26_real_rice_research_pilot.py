"""Adversarial source, dedup, split and provenance tests for F26 rice pilot."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC=importlib.util.spec_from_file_location(
    "f26_real_rice_pilot",
    Path(__file__).resolve().parents[1]/"scripts"/"factory_f26_real_rice_research_pilot.py")
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

def sample():
    return "@relation rice\n"+ "\n".join(
        "@attribute "+h+" numeric" for h in m.FIELDS)+(
        "\n@attribute Class {Cammeo,Osmancik}\n@data\n")+"\n".join(
        "%s,%s,%s,%s,%s,%s,%s,%s"%(
          13000+i*3,500+i%31,200+i%23,68+i%11,
          0.5+i/11000,14600+i%53,0.7+i/10000,
          "Cammeo" if i%2 else "Osmancik")
        for i in range(400))+"\n"

class RealRicePilotTests(unittest.TestCase):
    def test_valid_shape_source_features_and_label_order(self):
        rows,y=m.parse_arff(sample())
        self.assertEqual(len(rows),400)
        self.assertEqual(set(y),{0,1})
        self.assertEqual(len(rows[0]),7)

    def test_source_mutation_and_unsafe_zip_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"uci.zip"
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,"w") as z:
                z.writestr("Rice_Cammeo_Osmancik.arff",sample())
            path.write_bytes(buf.getvalue())
            known=hashlib.sha256(buf.getvalue()).hexdigest()
            txt,got=m.read_archive(path,known)
            self.assertEqual(got,known)
            self.assertEqual(len(m.parse_arff(txt)[0]),400)
            with self.assertRaisesRegex(RuntimeError,"SHA_PIN_MISMATCH"):
                m.read_archive(path,"0"*64)
            path.write_bytes(buf.getvalue()+b"corrupted")
            with self.assertRaisesRegex(RuntimeError,"SHA_PIN_MISMATCH"):
                m.read_archive(path,known)

    def test_duplicate_feature_leakage_and_class_conflict(self):
        rows,y=m.parse_arff(sample())
        pairs,parts,removed=m.split_unique(rows+[rows[0],rows[1]],
                                            y+[y[0],y[1]])
        self.assertEqual(len(pairs),len(rows))
        self.assertEqual(removed,2)
        self.assertEqual(sum(map(len,parts)),len(rows))
        self.assertEqual(len(set(parts[0])|set(parts[1])|set(parts[2])),len(rows))
        with self.assertRaisesRegex(RuntimeError,"CONTRADICTORY_DUPLICATE"):
            m.split_unique(rows+[rows[0]],y+[1-y[0]])

    def test_no_nonnumeric_or_missing_and_no_hallucinated_class(self):
        s=sample().replace("13000,","?,",1)
        with self.assertRaisesRegex(RuntimeError,"NONNUMERIC_FEATURE"):
            m.parse_arff(s)
        with self.assertRaisesRegex(RuntimeError,"BAD_ROW_OR_LABEL"):
            m.parse_arff(sample().replace(",Cammeo\n",",Unknown\n",1))

if __name__=="__main__":
    unittest.main()
