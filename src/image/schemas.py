from pydantic import HttpUrl

from src.schemas import RacunBase


class UploadImageResponse(RacunBase):
    image_name: str


class QrUrlResponse(RacunBase):
    qr_url: HttpUrl
