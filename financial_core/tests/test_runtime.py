from financial_core.runtime import FinancialRuntime, RuntimeHealth


def test_runtime_is_guarded_when_dependencies_are_missing():
    runtime = FinancialRuntime(lambda: RuntimeHealth(False,False,False,False,False,False,False), lambda req:(True,''), lambda *args:None)
    status=runtime.status()
    assert status['financial_core']=='guarded'
    assert status['agent_read_access'] is True
    assert status['agent_real_execution'] is False
    assert status['custody_keys_exposed_to_agents'] is False


def test_runtime_enables_agent_execution_only_when_every_gate_is_green():
    runtime = FinancialRuntime(lambda: RuntimeHealth(True,True,True,True,True,True,True), lambda req:(True,''), lambda *args:None)
    status=runtime.status()
    assert status['financial_core']=='ready'
    assert status['agent_real_execution'] is True
