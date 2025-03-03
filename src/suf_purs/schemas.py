from typing import List
from datetime import datetime

from pydantic import ConfigDict, HttpUrl, field_validator

from src.schemas import RacunBase


class QrUrlRequest(RacunBase):
    qr_url: HttpUrl

    @field_validator("qr_url")
    def validate_host(cls, value: HttpUrl):
        if value.host != "suf.purs.gov.rs":
            raise ValueError("URL must have host 'suf.purs.gov.rs'")
        return value


class SpecificationsRequest(RacunBase):
    invoiceNumber: str
    token: str


class SpecificationItem(RacunBase):
    gtin: str
    name: str
    quantity: float
    total: float
    unitPrice: float
    label: str
    labelRate: float
    taxBaseAmount: float
    vatAmount: float


class SellerInfo(RacunBase):
    model_config = ConfigDict(frozen=True)
    number: str
    company: str
    store: str
    address: str
    district: str
    cashier: str
    esir: str


class SpecificationsResponse(RacunBase):
    dt: datetime
    items: List[SpecificationItem]
    seller_info: SellerInfo
