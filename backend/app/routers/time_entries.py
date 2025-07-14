from fastapi import APIRouter, Query
from app.supabase.client import supabase

router = APIRouter(prefix="/time-entries", tags=["Time Entries"])


@router.get("/")
def list_time_entries(limit: int = Query(50), offset: int = Query(0)):
    result = (
        supabase
        .table("time_entries")
        .select("*")
        .range(offset, offset + limit - 1)
        .order("start_time", desc=True)
        .execute()
    )
    return result.data
