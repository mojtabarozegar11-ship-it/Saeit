"""No-secret regression of the one-use private RSA owner-password receiver."""
from pathlib import Path
import base64
import json
import os
import runpy
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/zomorod_owner_sealed_rotate.py"
ns=runpy.run_path(str(SCRIPT))
validate=ns["validate_payload"]
PURPOSE=ns["PURPOSE"]


def fixture(now=1770000000):
    return {"v":1,"purpose":PURPOSE,"nonce":"a"*32,
            "issued_at":now,"password":"SyntheticStrong2026!OnlyQA"}


def test_valid_16_and_200_byte_payloads():
    obj=fixture()
    obj["password"]="A"*16
    assert validate(obj,now=obj["issued_at"])==("a"*32,"A"*16)
    obj["password"]="Z"*200
    assert validate(obj,now=obj["issued_at"])[0]=="a"*32


def test_reject_short_expired_wrong_scope_and_control():
    cases=[]
    x=fixture();x["password"]="short";cases.append(x)
    x=fixture();x["issued_at"]-=3601;cases.append(x)
    x=fixture();x["purpose"]="other";cases.append(x)
    x=fixture();x["nonce"]="bad";cases.append(x)
    x=fixture();x["password"]="A"*16+"\n";cases.append(x)
    x=fixture();x["other"]="x";cases.append(x)
    for obj in cases:
        try:
            validate(obj,now=1770000000)
        except ValueError: pass
        else: raise AssertionError("unsafe payload accepted")


def test_openssl_rsa_oaep_sha256_roundtrip_without_production_keys():
    with tempfile.TemporaryDirectory(prefix="zm-owner-crypto-synthetic-") as tmp:
        root=Path(tmp);priv=root/"key.pem";pub=root/"pub.pem"
        make=subprocess.run(["openssl","genpkey","-algorithm","RSA",
            "-pkeyopt","rsa_keygen_bits:3072","-out",str(priv)],
            capture_output=True,timeout=30)
        assert make.returncode==0
        public=subprocess.run(["openssl","pkey","-in",str(priv),
            "-pubout","-out",str(pub)],capture_output=True,timeout=10)
        assert public.returncode==0
        obj=fixture(now=int(time.time()))
        raw=json.dumps(obj,separators=(",",":")).encode()
        assert len(raw)<310
        enc=subprocess.run(["openssl","pkeyutl","-encrypt","-pubin",
            "-inkey",str(pub),"-pkeyopt","rsa_padding_mode:oaep",
            "-pkeyopt","rsa_oaep_md:sha256","-pkeyopt","rsa_mgf1_md:sha256"],
            input=raw,capture_output=True,timeout=10)
        assert enc.returncode==0
        decrypt=ns["decrypt_payload"]
        decrypt.__globals__["KEY"]=priv
        opened=decrypt(base64.b64encode(enc.stdout))
        assert opened==obj
        assert validate(opened)[1]==obj["password"]


def test_no_plaintext_logging_or_unsafe_paths():
    s=SCRIPT.read_text(encoding="utf-8")
    assert 'PRIVATE = Path("/home/zomorod2/.private/zomorod-business")' in s
    assert 'if CONSUMED.exists()' in s
    assert '"rsa_padding_mode:oaep"' in s and '"rsa_oaep_md:sha256"' in s
    assert 'input=(password + "\\n").encode("utf-8")' in s
    assert 'PRIVATE_SQLITE_BACKUP=VERIFIED' in s
    assert 'SESSION_REVOCATION=NOT_VERIFIED' in s
    assert "print(password)" not in s
    assert "print(username)" not in s
    assert "password_hash" not in s
