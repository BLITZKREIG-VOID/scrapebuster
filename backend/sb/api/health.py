from fastapi import APIRouter

from ..contracts import Health

router = APIRouter()

@router.get("/health", response_model=Health)
async def get_health():
    return Health(status="ok")
