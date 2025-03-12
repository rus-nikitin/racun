from typing import List, Literal, Dict
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.db import get_db
from src.context import get_request_id
from src.bill.views import get_bills, get_bill
from src.bill.schemas import GetBillResponse, SpecificationItem

from src.cost.views import get_costs
from src.cost.schemas import CostDocument

from .schemas import (
    CompanyTotal,
    ItemTotal,
    GetAnalyticsResponse,
    ByCategory,
    ByCategoriesResponse,
)


log = getLogger(__name__)

router = APIRouter()


def process_bill_items(items: List[SpecificationItem], total_by_item) -> float:
    total = 0.0
    for item in items:
        total += item.total
        total_by_item[item.name] += item.total

    return total


def process_bills(bills: List[GetBillResponse]) -> GetAnalyticsResponse:
    total_by_seller = defaultdict(float)
    total_by_item = defaultdict(float)
    bills_total = 0.0
    for bill in bills:
        bill_total = process_bill_items(bill.items, total_by_item)
        bills_total += bill_total
        total_by_seller[bill.seller_info.company] += bill_total

    return GetAnalyticsResponse(
        total=bills_total,
        companies=[CompanyTotal(name=k, total=v) for k, v in total_by_seller.items()],
        items=[ItemTotal(name=k, total=v) for k, v in total_by_item.items()],
    )


@router.get("", response_model=GetAnalyticsResponse)
async def get_bills_analytics(
    user_name: str = "unknown",
    from_dt: datetime = None,
    bill_id: str = None,
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    if bill_id is not None:
        bill = await get_bill(bill_id, db=db, request_id=request_id)
        bills = [bill]
        # costs = []
    else:
        bills = await get_bills(user_name, from_dt, db=db, request_id=request_id)
        # costs = await get_costs(user_name, from_dt, db=db, request_id=request_id)

    return process_bills(bills)


def _process_items_by_categories(items: List[GetBillResponse | CostDocument]) -> ByCategoriesResponse:
    total_by_categories = defaultdict(float)
    total = 0.0
    for item in items:
        items_total = sum([_.total for _ in item.items])
        total_by_categories[item.category] += items_total
        total += items_total
    categories = sorted(
        [ByCategory(category=k, total=v) for k, v in total_by_categories.items()],
        key=lambda x: x.total,
        reverse=True
    )
    return ByCategoriesResponse(total=total, categories=categories)


@router.get("/by-categories", response_model=ByCategoriesResponse)
async def get_analytics_by_categories(
    user_name: str = "unknown",
    from_dt: datetime = None,
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    bills = await get_bills(user_name, from_dt, db=db, request_id=request_id)
    costs = await get_costs(user_name, from_dt, db=db, request_id=request_id)
    return _process_items_by_categories(bills+costs)
