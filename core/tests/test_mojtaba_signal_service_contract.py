import unittest
from decimal import Decimal

try:
    from mojtaba_signal_service_contract import (
        BOT_IDENTITY,
        SignalContractError,
        SignalOffer,
        SignalServiceKind,
        SignalTenantRoute,
        validate_offer,
        validate_request,
        validate_route,
        validate_route_offer_alignment,
        validate_route_registry,
    )
except ModuleNotFoundError:
    from core.mojtaba_signal_service_contract import (
        BOT_IDENTITY,
        SignalContractError,
        SignalOffer,
        SignalServiceKind,
        SignalTenantRoute,
        validate_offer,
        validate_request,
        validate_route,
        validate_route_offer_alignment,
        validate_route_registry,
    )


class MojtabaSignalContractTests(unittest.TestCase):
    def route(self, **changes):
        values = {
            "tenant_id": "mojplaywin",
            "canonical_host": "mojplaywin.com",
            "path_prefix": "/signals/",
            "language": "en",
        }
        values.update(changes)
        return SignalTenantRoute(**values)

    def offer(self, **changes):
        values = {
            "offer_id": "research-001",
            "tenant_id": "mojplaywin",
            "bot_identity": BOT_IDENTITY,
            "language": "en",
            "service_kind": SignalServiceKind.RESEARCH_SUMMARY,
            "price": Decimal("10"),
            "currency": "TRX",
        }
        values.update(changes)
        return SignalOffer(**values)

    def test_valid_route(self):
        validate_route(self.route())

    def test_active_route_requires_owner_and_legal_gates(self):
        with self.assertRaisesRegex(SignalContractError, "active_route_gates_incomplete"):
            validate_route(self.route(active=True))

    def test_active_route_with_gates_is_valid(self):
        validate_route(self.route(active=True, owner_approved=True, legal_reviewed=True))

    def test_route_rejects_other_bot_identity(self):
        with self.assertRaisesRegex(SignalContractError, "independent_bot_identity_prohibited"):
            validate_route(self.route(bot_identity="other.bot.ai"))

    def test_route_rejects_scheme(self):
        with self.assertRaisesRegex(SignalContractError, "canonical_host_invalid"):
            validate_route(self.route(canonical_host="https://mojplaywin.com"))

    def test_route_rejects_path_traversal(self):
        with self.assertRaisesRegex(SignalContractError, "path_prefix_invalid"):
            validate_route(self.route(path_prefix="/signals/../private/"))

    def test_route_rejects_unknown_language(self):
        with self.assertRaisesRegex(SignalContractError, "language_not_supported"):
            validate_route(self.route(language="de"))

    def test_registry_rejects_duplicate_tenant(self):
        with self.assertRaisesRegex(SignalContractError, "duplicate_tenant_route"):
            validate_route_registry((self.route(), self.route(path_prefix="/briefs/")))

    def test_registry_rejects_duplicate_endpoint(self):
        with self.assertRaisesRegex(SignalContractError, "duplicate_signal_endpoint"):
            validate_route_registry((self.route(tenant_id="first"), self.route(tenant_id="second")))

    def test_registry_sorts_routes_deterministically(self):
        result = validate_route_registry((self.route(tenant_id="zeta", canonical_host="zeta.example"), self.route(tenant_id="alpha", canonical_host="alpha.example")))
        self.assertEqual(result[0].tenant_id, "alpha")

    def test_valid_offer(self):
        validate_offer(self.offer())

    def test_offer_rejects_other_identity(self):
        with self.assertRaisesRegex(SignalContractError, "independent_bot_identity_prohibited"):
            validate_offer(self.offer(bot_identity="signal.bot.ai"))

    def test_offer_rejects_financial_calls(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_offer(self.offer(financial_calls_enabled=True))

    def test_offer_rejects_guaranteed_profit(self):
        with self.assertRaisesRegex(SignalContractError, "guaranteed_profit_prohibited"):
            validate_offer(self.offer(guaranteed_profit_promised=True))

    def test_active_offer_requires_all_gates(self):
        with self.assertRaisesRegex(SignalContractError, "active_offer_gates_incomplete"):
            validate_offer(self.offer(active=True))

    def test_active_offer_with_gates_is_valid(self):
        validate_offer(self.offer(active=True, owner_approved=True, legal_reviewed=True, rights_cleared=True))

    def test_offer_rejects_float_price(self):
        with self.assertRaisesRegex(SignalContractError, "price_must_be_decimal_like"):
            validate_offer(self.offer(price=10.0))

    def test_offer_rejects_unknown_currency(self):
        with self.assertRaisesRegex(SignalContractError, "currency_not_supported"):
            validate_offer(self.offer(currency="EUR"))

    def test_research_request_is_allowed(self):
        validate_request(request_text="Summarize the latest irrigation economics research.")

    def test_empty_request_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "request_text_required"):
            validate_request(request_text="")

    def test_buy_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_request(request_text="buy BTC now")

    def test_sell_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_request(request_text="sell gold")

    def test_long_and_short_are_rejected(self):
        for text in ("go long", "go short"):
            with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
                validate_request(request_text=text)

    def test_entry_and_exit_are_rejected(self):
        for text in ("entry at 2000", "exit at 2100"):
            with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
                validate_request(request_text=text)

    def test_persian_financial_language_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_request(request_text="الان خرید کن")

    def test_guaranteed_profit_language_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_request(request_text="guaranteed profit this week")

    def test_financial_authorization_flag_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_signal_disabled"):
            validate_request(request_text="market education", financial_authorized=True)

    def test_non_boolean_authorization_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "financial_authorized_must_be_boolean"):
            validate_request(request_text="market education", financial_authorized=1)

    def test_route_offer_tenant_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "route_offer_tenant_mismatch"):
            validate_route_offer_alignment(self.route(), self.offer(tenant_id="other"))

    def test_route_offer_language_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SignalContractError, "route_offer_language_mismatch"):
            validate_route_offer_alignment(self.route(), self.offer(language="fa"))

    def test_route_offer_alignment_is_valid(self):
        validate_route_offer_alignment(self.route(), self.offer())


if __name__ == "__main__":
    unittest.main()
