from fastapi import APIRouter
from app.supabase.client import supabase

router = APIRouter(prefix="/example", tags=["Example"])


@router.get("/")
def get_users():
    response = supabase.table("users").select("*").limit(10).execute()
    return response.data
