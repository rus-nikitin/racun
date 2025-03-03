from typing import List, Literal
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db import get_db
from src.context import get_request_id

from .schemas import (
    UploadBillRequest,
    UploadBillResponse,
    GetBillResponse
)


log = getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadBillResponse)
async def upload_bill(
    bill: UploadBillRequest,
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    document = bill.model_dump(mode="json")
    document["dt"] = bill.dt
    document["user_name"] = user_name

    collection = db["bill"]
    filter_query = {
        "$and": [
            {"image_name": document["image_name"]},
            {"qr_url": document["qr_url"]},
            {"user_name": document["user_name"]}
        ]
    }
    result = await collection.replace_one(
        filter_query,
        document,
        upsert=True
    )

    log.info(
        f"Request ID: [{request_id}] "
        f"bill successfully uploaded"
    )

    if result.upserted_id:
        return UploadBillResponse(upserted_id=str(result.upserted_id))

    return UploadBillResponse()


@router.get("/one", response_model=GetBillResponse | None)
async def get_bill(
    bill_id: str | None = None,
    user_name: str | None = None,
    image_name: str | None = None,
    qr_url: str | None = None,
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    query = {}
    if bill_id:
        query["_id"] = ObjectId(bill_id)
    if user_name:
        query["user_name"] = user_name
    if image_name:
        query["image_name"] = image_name
    if qr_url:
        query["qr_url"] = qr_url

    collection = db["bill"]

    document = await collection.find_one(query)
    if document:
        return GetBillResponse(bill_id=str(document["_id"]), **document)
    return None


@router.get("", response_model=List[GetBillResponse])
async def get_bills(
    user_name: str = "unknown",
    from_dt: datetime = None,
    sort_dt: Literal["-1", "1"] = "-1",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    collection = db["bill"]

    query = {"user_name": user_name}
    if from_dt:
        query["dt"] = {"$gte": from_dt}
    cursor = collection.find(query).sort("dt", int(sort_dt))
    documents = await cursor.to_list()

    return [GetBillResponse(bill_id=str(_["_id"]), **_) for _ in documents]
