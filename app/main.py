
from fastapi import FastAPI
from sqlalchemy import text

from app import models
from app.database import Base, engine
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.sharing import router as sharing_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Document Management & Secure File Sharing System")

app.include_router(auth_router)
app.include_router(sharing_router)
app.include_router(documents_router)

@app.get("/")
def home():
    return {"message": "Document Management System API is running"}


@app.get("/db-check")
def check_database():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"message": "MySQL connection successful"}
