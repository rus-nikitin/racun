from typing import List
from datetime import datetime

from src.schemas import RacunBase


class CostItem(RacunBase):
    name: str
    total: float


class CostSellerInfo(RacunBase):
    company: str


class CostCreate(RacunBase):
    dt: datetime

    items: List[CostItem]
    seller_info: CostSellerInfo

    category: str = "Other"


class CostUpdate(CostCreate):
    cost_id: str


class CostDocument(CostUpdate):
    cost_id: str
    user_name: str
