from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
import httpx
from httpx import HTTPStatusError

from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db import get_db
from src.client import get_async_client
from src.context import get_request_id
from src.exceptions import ParseContentError

from .schemas import (
    QrUrlRequest,
    SpecificationsRequest,
    SpecificationItem,
    SellerInfo,
    SpecificationsResponse
)
from .service import (
    get_specifications_request,
    get_dt,
    get_meta_info
)


log = getLogger(__name__)

router = APIRouter()


@router.post("/processing", response_model=SpecificationsResponse)
async def processing_qr_url_content(
    qur: QrUrlRequest,
    db: AsyncIOMotorDatabase=Depends(get_db),
    async_client: httpx.AsyncClient=Depends(get_async_client),
    request_id: str = Depends(get_request_id)
):
    try:
        response = await async_client.get(str(qur.qr_url))
        response.raise_for_status()
    except HTTPStatusError as http_exc:
        raise HTTPException(
            status_code=http_exc.response.status_code,
            detail=f"GET {str(qur.qr_url)} request error"
        )

    content = response.content

    try:
        sr: SpecificationsRequest = get_specifications_request(content)
        dt: datetime = get_dt(content)
        meta_info: List[str] = get_meta_info(content)
    except ParseContentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    specifications_url = 'https://suf.purs.gov.rs/specifications'
    try:
        response = await async_client.post(
            specifications_url,
            data=sr.model_dump(),
        )
        response.raise_for_status()
    except HTTPStatusError as http_exc:
        raise HTTPException(
            status_code=http_exc.response.status_code,
            detail=f"POST {specifications_url} request error"
        )
    data = response.json()
    items = []
    success = data.get("success", False)
    if success:
        items = data.get("items", [])
        items = [SpecificationItem(**_) for _ in items]

    log.info(
        f"Request ID: [{request_id}] "
        f"specifications successfully processed"
    )

    fields = SellerInfo.__annotations__.keys()
    return SpecificationsResponse(
        dt=dt,
        items=items,
        seller_info=SellerInfo(**dict(zip(fields, meta_info)))
    )
