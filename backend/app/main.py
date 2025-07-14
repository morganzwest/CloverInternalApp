from fastapi import FastAPI
from app.routers import hubspot, companies, time_entries, reports
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # <-- permitted origins
    allow_credentials=True,      # <-- if you need cookies/auth headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # or ["*"]
    allow_headers=["*"],         # or list only the headers you actually use
)

app.include_router(hubspot.router)
app.include_router(companies.router)
app.include_router(time_entries.router)
app.include_router(reports.router)
