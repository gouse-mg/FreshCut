"""
app.py
------
FastAPI application entry point.
Run with: uvicorn app:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routes import router

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FreshCut Meat Shop API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup_info():
    print("=" * 52)
    print("  FreshCut Meat Shop API v2 is running 🥩")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 52)
