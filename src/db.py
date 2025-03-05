from contextlib import asynccontextmanager


from fastapi import Request, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import CollectionInvalid

from config import settings
from logging import getLogger

log = getLogger(__name__)


async def collections_init(db: AsyncIOMotorDatabase):
    try:
        collection = await db.create_collection("image")
        await collection.create_index([("image_name", 1), ("user_name", 1)], unique=True)
        log.info("Collection 'image' successfully created.")
    except CollectionInvalid:
        log.info("Collection 'image' already exists.")

    try:
        collection = await db.create_collection("bill")
        await collection.create_index([("qr_url", 1), ("user_name", 1)], unique=True)
        await collection.create_index([("image_name", 1), ("user_name", 1)], unique=True)
        await collection.create_index([("image_name", 1), ("user_name", 1), ("qr_url", 1)], unique=True)
        log.info("Collection 'bill' successfully created.")
    except CollectionInvalid:
        log.info("Collection 'bill' already exists.")

    try:
        collection = await db.create_collection("cost")
        log.info("Collection 'cost' successfully created.")
    except CollectionInvalid:
        log.info("Collection 'cost' already exists.")


@asynccontextmanager
async def db_lifespan(app: FastAPI):
    """
    An async context manager, designed to be passed to FastAPI() as a lifespan.

    Initializes a MongoDB client and attaches it to the app
    Create collections if they don't exist.

    On shutdown, ensures that the database connection is closed appropriately.
    """

    # Startup
    app.mongodb_client = AsyncIOMotorClient(str(settings.mongo_dsn))
    app.db = app.mongodb_client.get_database(settings.mongo_db_name)

    ping_response = await app.db.command("ping")
    if int(ping_response["ok"]) != 1:
        raise Exception("Problem connecting to database cluster.")
    else:
        log.info("Connected to database cluster.")

    await collections_init(app.db)

    yield

    # Shutdown
    app.mongodb_client.close()
    log.info("Closed database connection.")


def get_db(request: Request):
    db = request.app.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection is not available")
    return db
