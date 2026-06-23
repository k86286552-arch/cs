from __future__ import annotations

import abc
from datetime import date


class PriceProvider(abc.ABC):
    name: str = "base"

    def is_configured(self) -> bool:
        return True

    @abc.abstractmethod
    async def get_price(self, commodity: str, dt: date, benchmark: str | None = None) -> dict | None:
        ...

    @abc.abstractmethod
    async def get_trend(self, commodity: str, days: int, benchmark: str | None = None) -> dict | None:
        ...

    @abc.abstractmethod
    def supports(self, commodity: str) -> bool:
        ...
