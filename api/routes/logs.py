from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from ..database import get_db
from ..dependencies import verify_api_key
from ..models import ActivityLog
from ..schemas import ActivityLogListResponse, ActivityLogResponse

router = APIRouter(prefix="/v1/logs", tags=["Activity Logs"])


@router.get("", response_model=ActivityLogListResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    total = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0
    offset = (page - 1) * per_page
    result = await db.execute(
        select(ActivityLog)
        .order_by(desc(ActivityLog.timestamp))
        .offset(offset)
        .limit(per_page)
    )
    logs = result.scalars().all()
    return ActivityLogListResponse(
        items=[ActivityLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )
