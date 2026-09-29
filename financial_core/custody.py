from abc import ABC, abstractmethod

class CustodyConnector(ABC):
    """Private keys must live outside application code and repository secrets."""
    @abstractmethod
    def create_deposit_address(self, user_id: str, asset: str, network: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_treasury_balance(self, asset: str, network: str):
        raise NotImplementedError

    @abstractmethod
    def broadcast_approved_withdrawal(self, request, approval_token: str) -> str:
        """Return a transaction hash only after provider-side policy approval."""
        raise NotImplementedError

class DisabledCustodyConnector(CustodyConnector):
    def create_deposit_address(self, user_id, asset, network):
        raise RuntimeError('custody-not-configured')

    def get_treasury_balance(self, asset, network):
        raise RuntimeError('custody-not-configured')

    def broadcast_approved_withdrawal(self, request, approval_token):
        raise RuntimeError('custody-not-configured')
