from abc import ABC, abstractmethod
from fastapi import HTTPException


class FiscalProvider(ABC):
    @abstractmethod
    def issue_invoice(self, *args, **kwargs) -> dict: ...


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, *args, **kwargs) -> dict: ...


class NotConfiguredFiscalProvider(FiscalProvider):
    def issue_invoice(self, *args, **kwargs):
        raise HTTPException(503, "Fiscal billing provider is not configured")


class NotConfiguredNotificationProvider(NotificationProvider):
    def send(self, *args, **kwargs):
        raise HTTPException(503, "Notification provider is not configured")


def get_fiscal_provider() -> FiscalProvider:
    return NotConfiguredFiscalProvider()


def get_notification_provider() -> NotificationProvider:
    return NotConfiguredNotificationProvider()
