from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import ServerSelectionTimeoutError

from src.db import get_db

log = getLogger(__name__)

router = APIRouter()

DATABASE_ERROR_MESSAGE = "Problem connecting to the database cluster."


@router.get(
    "",
    response_model=Dict,
    responses={
        200: {
            "description": "Successful health check.",
            "content": {
                "application/json": {
                    "example": {"success": True}
                }
            }
        },
        500: {
            "description": "Database connection error.",
            "content": {
                "application/json": {
                    "example": {"detail": "Problem connecting to the database cluster."}
                }
            }
        }
    },
)
async def health_check(db: AsyncIOMotorDatabase=Depends(get_db)) -> Any:
    try:
        ping_response = await db.command("ping")
        if ping_response.get("ok") != 1:
            log.error("Database ping response invalid: %s", ping_response)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=DATABASE_ERROR_MESSAGE,
            )
    except ServerSelectionTimeoutError as e:
        log.error("Database connection error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=DATABASE_ERROR_MESSAGE,
        )

    log.info("Health check successful.")
    return {"success": True}
