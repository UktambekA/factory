"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(title="The Chocolate Factory", description="Mini-MRP MVP")
app.include_router(router)

# Optional: mount static files if you add CSS/JS later
# app.mount("/static", StaticFiles(directory="app/static"), name="static")
