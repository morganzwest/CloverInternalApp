from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.services import hubspot

router = APIRouter(prefix="/hubspot", tags=["HubSpot"])


@router.post("/sync")
def sync_hubspot_data(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(hubspot.sync_all_data)
        return {"status": "started", "message": "HubSpot full sync started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/time-sync")
def sync_hubspot_time_data(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(hubspot.time_sync)
        return {"status": "started", "message": "HubSpot time sync started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
