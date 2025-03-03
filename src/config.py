from pydantic_settings import BaseSettings
from pydantic import MongoDsn


class Settings(BaseSettings):
    project_name: str

    host: str
    port: int = 8080

    api_prefix: str = "/api"

    mongo_dsn: MongoDsn
    mongo_db_name: str

    web_concurrency: int = 1

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()
