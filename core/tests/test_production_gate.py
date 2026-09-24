from unittest.mock import patch

from django.test import override_settings

from core.health_gate import HealthResult
from core.production_gate import ProductionGate


class StubHealthGate:
    def __init__(self, result=None):
        self.result = result or HealthResult(True, True, ())

    def evaluate(self, **kwargs):
        return self.result


@override_settings(DEBUG=False, SECRET_KEY="test-production-secret", ALLOWED_HOSTS=["example.com"])
def test_production_gate_passes_when_ready():
    gate = ProductionGate(StubHealthGate())
    with patch("core.production_gate.connection.ensure_connection"), patch("core.production_gate.MigrationExecutor") as executor_cls:
        executor_cls.return_value.migration_plan.return_value = []
        result = gate.evaluate()
    assert result.ready is True
    assert all(result.checks.values())


@override_settings(DEBUG=True, SECRET_KEY="test-production-secret", ALLOWED_HOSTS=["example.com"])
def test_production_gate_blocks_debug():
    gate = ProductionGate(StubHealthGate())
    with patch("core.production_gate.connection.ensure_connection"), patch("core.production_gate.MigrationExecutor") as executor_cls:
        executor_cls.return_value.migration_plan.return_value = []
        result = gate.evaluate()
    assert result.ready is False
    assert "DEBUG must be False" in result.reasons


@override_settings(DEBUG=False, SECRET_KEY="test-production-secret", ALLOWED_HOSTS=["example.com"])
def test_production_gate_blocks_pending_migrations():
    gate = ProductionGate(StubHealthGate())
    with patch("core.production_gate.connection.ensure_connection"), patch("core.production_gate.MigrationExecutor") as executor_cls:
        executor_cls.return_value.migration_plan.return_value = [("pending", object())]
        result = gate.evaluate()
    assert result.ready is False
    assert result.checks["migrations_current"] is False


@override_settings(DEBUG=False, SECRET_KEY="test-production-secret", ALLOWED_HOSTS=["example.com"])
def test_production_gate_blocks_database_failure():
    gate = ProductionGate(StubHealthGate())
    with patch("core.production_gate.connection.ensure_connection", side_effect=Exception("db down")):
        result = gate.evaluate()
    assert result.ready is False
    assert result.checks["database"] is False
    assert result.checks["migrations_current"] is False
