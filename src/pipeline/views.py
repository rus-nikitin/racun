from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, status
import httpx
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError

from src.db import get_db
from src.client import get_async_client
from src.context import get_request_id
from src.image.views import upload_image, upload_image_bytes, qr_decode_by_image, qr_decode_by_image_name, get_image_name_from_bytes, qr_decode_by_image_bytes
from src.bill.views import upload_bill, get_bill
from src.bill.schemas import UploadBillRequest
from src.suf_purs.schemas import QrUrlRequest
from src.suf_purs.views import processing_qr_url_content

from .schemas import ProcessingImageResponse, ProcessingImageNameRequest

log = getLogger(__name__)

router = APIRouter()


async def _processing_image_name(
    image_name: str,
    user_name: str,
    db: AsyncIOMotorDatabase,
    async_client: httpx.AsyncClient,
    request_id: str
) -> ProcessingImageResponse:
    qr_url_response = await qr_decode_by_image_name(image_name, db, request_id)
    try:
        QrUrlRequest.model_validate(qr_url_response.model_dump())
    except ValidationError:
        raise HTTPException(
            status_code=422,
            detail="Invalid QR URL"
        )

    specifications_response = await processing_qr_url_content(qr_url_response, db, async_client, request_id)

    bill = UploadBillRequest(
        image_name=image_name,
        **qr_url_response.model_dump(),
        **specifications_response.model_dump()
    )
    upload_bill_response = await upload_bill(bill, user_name, db, request_id)

    return ProcessingImageResponse(
        **bill.model_dump(),
        **upload_bill_response.model_dump()
    )


@router.post("/processing-image", response_model=ProcessingImageResponse)
async def processing_image(
    response: Response,
    image: UploadFile = File(...),
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    async_client: httpx.AsyncClient=Depends(get_async_client),
    request_id: str = Depends(get_request_id)
):
    log.info(
        f"Request ID: [{request_id}] "
        f"filename: {image.filename} "
        f"username: {user_name}"
    )

    upload_image_response = await upload_image(image, user_name, db, request_id)
    image_name = upload_image_response.image_name

    bill = await get_bill(user_name=user_name, image_name=image_name, db=db)
    if bill:
        return ProcessingImageResponse(
            image_name=image_name,
            **bill.model_dump(),
        )

    return await _processing_image_name(image_name, user_name, db, async_client, request_id)


@router.post("/processing-image-name", response_model=ProcessingImageResponse)
async def processing_image_name(
    pin: ProcessingImageNameRequest,
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    async_client: httpx.AsyncClient=Depends(get_async_client),
    request_id: str = Depends(get_request_id)
):
    log.info(
        f"Request ID: [{request_id}] "
        f"image_name: {pin.image_name} "
        f"username: {user_name}"
    )

    return await _processing_image_name(pin.image_name, user_name, db, async_client, request_id)



@router.post("/processing", response_model=ProcessingImageResponse)
async def processing_by_image(
    image: UploadFile = File(...),
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    async_client: httpx.AsyncClient=Depends(get_async_client),
    request_id: str = Depends(get_request_id)
):
    image_bytes = await image.read()
    image_name = get_image_name_from_bytes(image_bytes)


    user_bill = await get_bill(user_name=user_name, image_name=image_name, db=db, request_id=request_id)
    if user_bill: return user_bill


    bill = await get_bill(image_name=image_name, db=db, request_id=request_id)
    if bill:
        user_bill = await get_bill(user_name=user_name, qr_url=str(bill.qr_url), db=db, request_id=request_id)
        if user_bill: return user_bill

        upserted_bill = await upload_bill(
            UploadBillRequest(**bill.model_dump()),
            user_name, db, request_id
        )
        user_bill = await get_bill(bill_id=upserted_bill.upserted_id, db=db, request_id=request_id)
        return user_bill


    try:
        qr_url_response = qr_decode_by_image_bytes(image_bytes, image_name, request_id)
    except Exception as e:
        await upload_image_bytes(image_bytes, image_name, user_name, db, request_id)
        log.info(
            f"Request ID: [{request_id}] "
            f"image_name={image_name} saved for future qr decode debug."
        )
        raise e

    try:
        QrUrlRequest.model_validate(qr_url_response.model_dump())
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid QR URL")


    user_bill = await get_bill(user_name=user_name, qr_url=str(qr_url_response.qr_url), db=db, request_id=request_id)
    if user_bill: return user_bill


    bill = await get_bill(qr_url=str(qr_url_response.qr_url), db=db, request_id=request_id)
    if bill:
        upserted_bill = await upload_bill(
            UploadBillRequest(**bill.model_dump()),
            user_name, db, request_id
        )
        user_bill = await get_bill(bill_id=upserted_bill.upserted_id, db=db, request_id=request_id)
        return user_bill


    specifications_response = await processing_qr_url_content(qr_url_response, db, async_client, request_id)
    bill = UploadBillRequest(
        image_name=image_name,
        **qr_url_response.model_dump(),
        **specifications_response.model_dump()
    )
    upserted_bill = await upload_bill(
        UploadBillRequest(**bill.model_dump()),
        user_name, db, request_id
    )
    user_bill = await get_bill(bill_id=upserted_bill.upserted_id, db=db, request_id=request_id)
    return user_bill
