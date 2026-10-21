"""Compare our Python server verifier to independently generated official TronWeb V2 signature."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','moj_commerce.test_settings')
import django
django.setup()
from moj_commerce.wallet_proof import recover_signer_tron_hex
from moj_commerce.services import CommerceRejected
from mpw_tron_pro.core import tron_address_hex

def main():
    fixture=json.load(sys.stdin)
    actual=recover_signer_tron_hex(fixture['message'],fixture['signature'])
    expected=tron_address_hex(fixture['address'])
    if actual != expected: raise AssertionError('Official TronWeb signer does not match Python recovery')
    try:
        altered=recover_signer_tron_hex(fixture['message']+' changed',fixture['signature'])
    except CommerceRejected:
        pass
    else:
        if altered == expected: raise AssertionError('Signed message alteration preserved the verified signer')
    print('TRONWEB_V2_PYTHON_INTEROP=PASS')
if __name__=='__main__':main()