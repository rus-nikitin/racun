from typing import List

from src.schemas import RacunBase


class CompanyTotal(RacunBase):
    name: str
    total: float


class ItemTotal(CompanyTotal):
    ...


class GetAnalyticsResponse(RacunBase):
    total: float
    companies: List[CompanyTotal]
    items: List[ItemTotal]
