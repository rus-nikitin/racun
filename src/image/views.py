from typing import List
import hashlib
from bson import Binary

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, status
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db import get_db
from src.context import get_request_id
from src.exceptions import QRCodeDecodeError

from .schemas import UploadImageResponse, QrUrlResponse
from .service import process_qr_url_1


log = getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[str])
async def get_names(
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    collection = db["image"]
    cursor = collection.find({"user_name": user_name}, {"_id": 0, "image_name": 1})
    documents = await cursor.to_list()
    return [_["image_name"] for _ in documents]


def get_image_name_from_bytes(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()


async def upload_image_bytes(image_bytes, image_name, user_name, db, request_id):
    collection = db["image"]
    document = await collection.find_one(
        {
            "image_name": image_name,
            "user_name": user_name
        }
    )
    if document: return UploadImageResponse(image_name=image_name)

    await collection.insert_one(
        {
            "image_name": image_name,
            "user_name": user_name,
            "binary": Binary(image_bytes)
        }
    )

    log.info(
        f"Request ID: [{request_id}] "
        f"image_name={image_name} successfully uploaded"
    )


    return UploadImageResponse(image_name=image_name)


@router.post("/upload", response_model=UploadImageResponse)
async def upload_image(
    image: UploadFile = File(...),
    user_name: str = "unknown",
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    image_bytes = await image.read()
    image_name = get_image_name_from_bytes(image_bytes)

    return await upload_image_bytes(image_bytes, image_name, user_name, db, request_id)


def qr_decode_by_image_bytes(image_bytes, image_name, request_id):
    try:
        qr_url = process_qr_url_1(image_bytes)
        log.info(
            f"Request ID: [{request_id}] "
            f"QR code successfully decoded for image_name={image_name}. "
            f"Extracted URL: {qr_url[:30]}{'...' if len(qr_url) > 30 else ''}"
        )
        return QrUrlResponse(qr_url=qr_url)

    except QRCodeDecodeError as e:
        log.error(
            f"Request ID: [{request_id}] "
            f"QR code decoding failed for image_name={image_name}. "
            f"Error: {str(e)}"
        )
        raise HTTPException(
            status_code=422,
            detail=f"Failed to decode QR code: {str(e)}"
        )

    except Exception as e:
        log.error(
            f"Request ID: [{request_id}] "
            f"Unexpected error during QR processing for image_name={image_name}. "
            f"Error type: {type(e).__name__}, Message: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error during QR code processing"
        )


@router.post("/qr/decode", response_model=QrUrlResponse)
async def qr_decode_by_image(
    image: UploadFile = File(...),
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    image_bytes = await image.read()
    image_name = get_image_name_from_bytes(image_bytes)

    return qr_decode_by_image_bytes(image_bytes, image_name, request_id)


@router.get("/qr/decode-by", response_model=QrUrlResponse)
async def qr_decode_by_image_name(
    image_name: str,
    db: AsyncIOMotorDatabase=Depends(get_db),
    request_id: str = Depends(get_request_id)
):
    collection = db["image"]
    document = await collection.find_one({"image_name": image_name})
    if not document:
        raise HTTPException(status_code=404, detail="Image not found.")

    image_bytes = document["binary"]

    return qr_decode_by_image_bytes(image_bytes, image_name, request_id)
