from fastapi import APIRouter

from src.health.views import router as health_router
from src.image.views import router as image_router
from src.suf_purs.views import router as suf_purs_router
from src.bill.views import router as bill_router
from src.pipeline.views import router as pipeline_router
from src.analytics.views import router as analytics_router



api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(image_router, prefix="/image", tags=["image"])
api_router.include_router(suf_purs_router, prefix="/suf-purs", tags=["suf-purs"])
api_router.include_router(bill_router, prefix="/bill", tags=["bill"])
api_router.include_router(pipeline_router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
