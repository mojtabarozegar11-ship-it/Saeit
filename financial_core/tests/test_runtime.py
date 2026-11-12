from financial_core.runtime import FinancialRuntime, RuntimeHealth


def test_runtime_is_guarded_when_dependencies_are_missing():
    runtime = FinancialRuntime(lambda: RuntimeHealth(False,False,False,False,False,False,False), lambda req:(True,''), lambda *args:None)
    status=runtime.status()
    assert status['financial_core']=='guarded'
    assert status['agent_read_access'] is True
    assert status['agent_real_execution'] is False
    assert status['custody_keys_exposed_to_agents'] is False


def test_runtime_cannot_advertise_real_execution_without_approval_verifier():
    runtime = FinancialRuntime(lambda: RuntimeHealth(True,True,True,True,True,True,True), lambda req:(True,''), lambda *args:None)
    status=runtime.status()
    assert status['financial_core']=='ready'
    assert status['agent_real_execution'] is False


def test_runtime_can_advertise_guarded_real_execution_with_verifier():
    runtime = FinancialRuntime(lambda: RuntimeHealth(True,True,True,True,True,True,True),
                               lambda req:(True,''), lambda *args:None,
                               owner_approval_verifier=lambda req: False)
    status=runtime.status()
    assert status['financial_core']=='ready'
    assert status['agent_real_execution'] is True
