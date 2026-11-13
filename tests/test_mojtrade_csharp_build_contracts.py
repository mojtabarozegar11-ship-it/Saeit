"""Fail closed if the official .NET build contract stops compiling safely."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    "MojTradeOmegaXDemoBot": "MojTradeOmegaXDemoBot.cs",
    "MojTradeDemoHistoryAuditBot": "MojTradeDemoHistoryAuditBot.cs",
}


def test_both_native_ctrader_cbot_projects_are_pinned_to_official_api():
    for project, source in PROJECTS.items():
        folder = ROOT / "trading" / "ctrader-build" / project
        xml = ET.parse(folder / (project + ".csproj")).getroot()
        def get(path):
            node = xml.find(path)
            assert node is not None, (project, path)
            return node
        assert get(".//TargetFramework").text == "net8.0"
        assert get(".//AlgoBuild").text == "false"
        assert get(".//AlgoPublish").text == "false"
        assert get(".//EnableDefaultCompileItems").text == "false"
        package = get(".//PackageReference")
        assert package.attrib == {"Include": "cTrader.Automate", "Version": "1.0.21"}
        compile_tag = get(".//Compile")
        assert compile_tag.attrib["Include"] == "../../" + source
        assert (folder / compile_tag.attrib["Include"]).resolve() == (
            ROOT / "trading" / source
        ).resolve()


def test_both_ctrader_bots_are_demo_only_with_no_external_access():
    for source in PROJECTS.values():
        code = (ROOT / "trading" / source).read_text(encoding="utf-8")
        assert "if (Account.IsLive)" in code
        assert "AccessRights = AccessRights.None" in code
    history_code = (ROOT / "trading" / PROJECTS["MojTradeDemoHistoryAuditBot"]).read_text()
    for forbidden in (
        "ExecuteMarketOrder(", "PlaceLimitOrder(", "PlaceStopOrder(",
        "ModifyPosition(", "ClosePosition(", "HttpClient(",
    ):
        assert forbidden not in history_code


def test_github_csharp_compilation_is_not_removed_or_silently_skipped():
    workflow = (ROOT / ".github/workflows/mojtaba-one-bot-review-ci.yml").read_text()
    assert "ctrader-csharp-compile:" in workflow
    assert "actions/setup-dotnet@v4" in workflow
    assert workflow.count("dotnet build trading/ctrader-build/") == 2
    assert "-p:AlgoPublish=false" in workflow
    assert "-p:AlgoBuild=false" in workflow
    assert "continue-on-error: true" not in workflow



def test_demo_execution_adapter_enforces_warmup_accountwide_cap_and_utc_loss():
    code = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")
    assert "Math.Max(SlowEmaPeriod + 5, 22)" in code
    assert "Math.Max(AtrPeriod + 2, RsiPeriod + 2)" in code
    assert "for (var candle = index - 20; candle < index; candle++)" in code
    assert code.count("Positions.FindAll(Label)") >= 2
    assert "Positions.FindAll(Label, SymbolName)" in code
    assert "position.StopLoss.HasValue || !position.TakeProfit.HasValue" in code
    assert "Server.Time.Date" in code
    assert "_dayStartEquity" in code
    assert "_sessionStartEquity" not in code
    assert "if (Account.IsLive)" in code
    assert "Enable Demo Trading\", DefaultValue = false" in code
    assert "AccessRights = AccessRights.None" in code



def test_demo_order_reconciles_protective_fills_and_blocks_ambiguous_retry():
    source = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")
    assert 'private const string Label = "MojTrade-OMEGA-X-DEMO";' in source
    assert "AccessRights = AccessRights.None" in source
    assert "if (Account.IsLive)" in source
    assert "[Parameter(\"Enable Demo Trading\", DefaultValue = false)]" in source
    assert "_lastAttemptedSignalKey = signalKey;" in source
    assert "foreach (var position in Positions.FindAll(Label))" in source
    assert "foreach (var closedTrade in History.FindAll(Label))" in source
    assert "closedTrade.Comment == signalKey" in source
    assert "closedBarTime.ToString" in source
    assert "ExecuteMarketOrder(" in source
    assert "stopPips, takePips, signalKey" in source
    assert "var opened = result.Position;" in source
    assert "!opened.StopLoss.HasValue || !opened.TakeProfit.HasValue" in source
    assert "var closed = ClosePosition(opened);" in source
    assert "_orderReconciliationHold = true;" in source
    assert "if (!result.IsSuccessful)" in source


def test_demo_restart_does_not_reset_daily_risk_or_loss_streak():
    source = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")
    assert "foreach (var trade in History)" in source
    assert "accountNetToday += trade.NetProfit;" in source
    assert "Array.Sort(owned" in source
    assert "History.FindAll(Label)" in source
    assert "_dayStartEquity = Account.Balance - accountNetToday;" in source
    assert "if (trade.NetProfit < 0)" in source
    assert "if (trade.NetProfit > 0)" in source
    assert "catch (Exception)" in source
    assert "broker history was not reconciled" in source
    assert "_dayStartEquity = Account.Equity;" not in source
    assert "_consecutiveLosses = 0;" not in source
    assert "Account.IsLive || !EnableDemoTrading || _orderReconciliationHold" in source



def test_demo_portfolio_gate_includes_all_account_positions_and_margin():
    """Reject new risk when unrelated positions exhaust the account budget."""
    source = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")
    assert 'Aggregate Stop Risk %", DefaultValue = 1.0, MinValue = 0.25, MaxValue = 1.0' in source
    assert "Positions.Count >= MaxPositions" in source
    assert "foreach (var current in Positions)" in source
    assert "if (PendingOrders.Count != 0)" in source
    assert "current.Symbol" in source
    assert "current.StopLoss.HasValue || !current.TakeProfit.HasValue" in source
    assert "current.TradeType == TradeType.Buy" in source
    assert "current.VolumeInUnits" in source
    assert "instrument.AmountRisked(" in source
    assert "Symbol.AmountRisked(volume, stopPips)" in source
    assert "Symbol.GetEstimatedMargin(side, volume)" in source
    assert "Account.FreeMargin" in source
    assert "portfolioRisk > budget" in source
    assert "portfolioRisk += existingRisk;" in source


def test_portfolio_risk_checks_precede_any_demo_execution_attempt():
    source = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")
    start = source.index("private void SubmitDemoOrder(")
    end = source.index("private bool PortfolioRiskAllows(", start)
    order = source[start:end]
    assert "if (Account.IsLive" in order
    assert "Positions.Count >= MaxPositions" in order
    assert "if (!PortfolioRiskAllows(tradeType, volume, stopPips))" in order
    assert order.index("PortfolioRiskAllows(tradeType, volume, stopPips)") < order.index("ExecuteMarketOrder(")
    assert "Enable Demo Trading\", DefaultValue = false" in source
    assert "AccessRights = AccessRights.None" in source
