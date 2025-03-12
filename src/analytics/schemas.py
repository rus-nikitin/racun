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


class ByCategory(RacunBase):
    category: str
    total: float = 0.0


class ByCategoriesResponse(RacunBase):
    total: float = 0.0
    categories: List[ByCategory]
