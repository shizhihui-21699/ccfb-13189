from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, check, stats
from .seed import seed_if_empty

Base.metadata.create_all(bind=engine)

app = FastAPI(title="注册临时身份识别服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境收紧为运营后台域名
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(check.router)
app.include_router(admin.router)
app.include_router(stats.router)


@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
