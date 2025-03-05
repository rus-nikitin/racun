from typing import List, Literal
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db import get_db
from src.context import get_request_id

from .schemas import (
    CostItem,
    CostSellerInfo,
    CostCreate,
    CostUpdate,
    CostDocument
)


log = getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=CostDocument)
async def upload_cost(
    cost: CostCreate | CostUpdate,
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    document = cost.model_dump(mode="json")
    document["dt"] = cost.dt
    document["user_name"] = user_name

    collection = db["cost"]
    if type(cost) is CostCreate:
        result = await collection.insert_one(document)
        cost_id = str(result.inserted_id)
        log.info(
            f"Request ID: [{request_id}] "
            f"cost {cost_id} inserted"
        )
        return CostDocument(cost_id=cost_id, **document)
    else:
        cost_id = document["cost_id"]
        del document["cost_id"]
        result = await collection.replace_one(
            {"_id": ObjectId(cost.cost_id)},
            document,
            upsert=True
        )
        if result.upserted_id:
            cost_id = str(result.upserted_id)
        log.info(
            f"Request ID: [{request_id}] "
            f"cost {cost_id} replaced"
        )
        return CostDocument(cost_id=cost_id, **document)


@router.get("/one", response_model=CostDocument | None)
async def get_cost(
    cost_id: str,
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    query = {"_id": ObjectId(cost_id)}
    collection = db["cost"]

    document = await collection.find_one(query)
    if document:
        return CostDocument(cost_id=cost_id, **document)
    return None

@router.get("", response_model=List[CostDocument])
async def get_costs(
    user_name: str = "unknown",
    from_dt: datetime = None,
    sort_dt: Literal["-1", "1"] = "-1",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    collection = db["cost"]

    query = {"user_name": user_name}
    if from_dt:
        query["dt"] = {"$gte": from_dt}
    cursor = collection.find(query).sort("dt", int(sort_dt))
    documents = await cursor.to_list()

    return [CostDocument(cost_id=str(_["_id"]), **_) for _ in documents]
