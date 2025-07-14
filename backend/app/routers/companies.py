from fastapi import APIRouter, Query
from app.supabase.client import supabase

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/")
def list_companies(limit: int = Query(50), offset: int = Query(0)):
    result = (
        supabase
        .table("hubspot_companies")
        .select("*")
        .range(offset, offset + limit - 1)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data
