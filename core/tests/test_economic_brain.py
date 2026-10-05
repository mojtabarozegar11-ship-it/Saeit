from core.autonomous_brain import AutonomousBrain


def test_market_research_and_scoring_are_verified_before_offer_design():
    brain = AutonomousBrain()
    state = {
        "unfinished_tasks": 0,
        "failed_tasks": 0,
        "market_research_complete": False,
        "opportunity_scored": False,
        "active_products": 0,
        "offer_designed": 0,
        "mvp_built": 0,
        "growth_ready": 0,
        "orders": 0,
        "paid_orders": 0,
    }

    assert brain.candidates(state)[0].action == "income_market_research"

    state["market_research_complete"] = True
    assert brain.candidates(state)[0].action == "income_opportunity_score"

    state["opportunity_scored"] = True
    assert brain.candidates(state)[0].action == "income_offer_design"
