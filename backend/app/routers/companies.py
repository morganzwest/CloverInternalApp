from fastapi import APIRouter, Query, HTTPException
from app.supabase.client import supabase
from postgrest.exceptions import APIError

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/")
def list_companies(limit: int = Query(50), offset: int = Query(0)):
    result = (
        supabase
        .table("hubspot_companies")
        .select("*")
        .range(offset, offset + limit - 1)
        .order("name", desc=True)
        .execute()
    )
    return result.data


@router.get("/{company_id}")
def get_company(company_id: str):
    """
    Retrieve a single company by its ID.
    """
    try:
        resp = (
            supabase
            .table("hubspot_companies")
            .select("*")
            .eq("hubspot_id", company_id)
            .single()
            .execute()
        )
    except APIError:
        # single() raises APIError if no row (or more than one) is found
        raise HTTPException(
            status_code=404,
            detail=f"Company with ID {company_id} not found"
        )
    return resp.data
