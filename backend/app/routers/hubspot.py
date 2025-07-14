from fastapi import APIRouter, HTTPException
from app.services import hubspot

router = APIRouter(prefix="/hubspot", tags=["HubSpot"])


@router.post("/sync")
def sync_hubspot_data():
    try:
        hubspot.sync_all_data()
        return {"status": "success", "message": "HubSpot data synced"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/time-sync")
def sync_hubspot_data():
    try:
        hubspot.time_sync()
        return {"status": "success", "message": "Hubspot Time data synced"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
