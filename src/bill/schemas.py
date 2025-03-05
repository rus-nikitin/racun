from typing import List
from datetime import datetime

from src.schemas import RacunBase
from src.suf_purs.views import QrUrlRequest, SpecificationItem, SellerInfo


class UploadBillRequest(QrUrlRequest):
    image_name: str

    dt: datetime
    items: List[SpecificationItem]
    seller_info: SellerInfo

    category: str = "Other"


class UploadBillResponse(RacunBase):
    upserted_id: str | None = None


class GetBillResponse(UploadBillRequest):
    bill_id: str
    user_name: str
