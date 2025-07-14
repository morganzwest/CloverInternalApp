# main.py

import sys
import asyncio

# ── 1) On Windows, switch to the Proactor loop so asyncio.create_subprocess_exec works ──
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import hubspot, companies, time_entries, reports

app = FastAPI()

origins = [
    "http://localhost:5173",
    "https://clover-internal-a5jsm8esk-flowsight.vercel.app/",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(hubspot.router)
app.include_router(companies.router)
app.include_router(time_entries.router)
app.include_router(reports.router)
