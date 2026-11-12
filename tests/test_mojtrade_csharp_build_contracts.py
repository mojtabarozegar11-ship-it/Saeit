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
