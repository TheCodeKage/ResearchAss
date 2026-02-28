from fastapi import FastAPI
from backend.database import engine, Base
from backend.PaperManager.router import router as paper_router
from backend.Auth.router import router as auth_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(paper_router, prefix="/papers", tags=["Papers"])