from src.schemas import RacunBase
from src.bill.schemas import GetBillResponse


class ProcessingImageResponse(GetBillResponse):
    ...


class ProcessingImageNameRequest(RacunBase):
    image_name: str
