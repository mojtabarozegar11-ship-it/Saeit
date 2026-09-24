import pytest

from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec


def test_gateway_invokes_registered_tool():
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: {"echo": payload["q"]}),
    ])

    assert gateway.invoke("research", {"q": "wheat"}) == {"echo": "wheat"}


def test_gateway_rejects_unknown_tool():
    gateway = ToolGateway()

    with pytest.raises(ToolGatewayError, match="not registered"):
        gateway.invoke("research", {})


def test_gateway_requires_approval_for_sensitive_tool():
    gateway = ToolGateway([
        ToolSpec(code="deploy", handler=lambda payload: {"ok": True}, risk="high"),
    ])

    with pytest.raises(ToolGatewayError, match="approval"):
        gateway.invoke("deploy", {})

    assert gateway.invoke("deploy", {}, approved=True) == {"ok": True}


def test_gateway_rejects_invalid_payload():
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: payload),
    ])

    with pytest.raises(ToolGatewayError, match="payload"):
        gateway.invoke("research", ["invalid"])
