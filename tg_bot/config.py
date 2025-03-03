from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    token: str

    host: str
    port: int = 8080

    api_prefix: str = "/api"


    request_timeout: int = 600

    class Config:
        env_file = "../bot.env"
        env_file_encoding = "utf-8"


settings = Settings()
