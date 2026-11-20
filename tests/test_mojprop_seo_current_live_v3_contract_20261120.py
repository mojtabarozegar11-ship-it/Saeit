import unittest
from unittest.mock import patch
from scripts import mojprop_seo_current_live_v3_contract_20261120 as mod

class CurrentLiveContractTests(unittest.TestCase):
    def test_scope_and_external_gates(self):
        self.assertEqual(set(mod.CHANGED), {"index.html","catalog/index.html","payment/index.html"})
        self.assertEqual(len(mod.PINS),5)
        self.assertEqual(len(mod.REQUIRED_ATTESTATIONS),4)
        for k,(before,after) in mod.PINS.items():
            self.assertEqual(before != after,k in mod.CHANGED)

    def test_missing_extra_or_bad_input_rejected(self):
        fixtures = dict.fromkeys(mod.PINS,b"<head></head><body>fixture</body>")
        for invalid in ({}, {**fixtures,"signals/index.html":b"x"}, fixtures):
            with self.subTest(count=len(invalid)), self.assertRaises(ValueError):
                mod.build_v3(fixtures,invalid)

    def test_bad_boundary_rejected(self):
        for bad in ("text",b"missing",b"</head></head>",b"x"*512001):
            with self.subTest(kind=type(bad)), self.assertRaises(ValueError):
                mod._parts(bad)

    def test_pure_exact_scope_and_head_preservation(self):
        old={k:b"<head>historical</head><body>unchanged</body>" for k in mod.PINS}
        live={k:b"<head>current</head><body>unchanged</body>" for k in mod.PINS}
        candidate = {}
        for k in mod.PINS:
            h = b"<head>new" if k=="catalog/index.html" else b"<head>current"
            body = b"<body>changed</body>" if k in mod.CHANGED else b"<body>unchanged</body>"
            candidate[k] = h+b"</head>"+body
        pins={k:(mod.sha(live[k]),mod.sha(candidate[k])) for k in mod.PINS}
        historical={k:(mod.sha(old[k]),) for k in mod.PINS}
        with patch.object(mod,"PINS",pins),patch.object(mod,"PAGES",historical),patch.object(mod,"reconcile_candidate",side_effect=lambda k,b:(candidate[k],{})):
            result,receipt=mod.build_v3(old,live)
        self.assertEqual(result,candidate)
        self.assertFalse(receipt["deployment_authorized"])
        self.assertEqual(receipt["write_scope"],list(mod.CHANGED))
