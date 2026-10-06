from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import scans, calibration, pattern_stats

app = FastAPI(
    title="AttackGraph AI API",
    description="Controlled Security Analysis Platform — Server-side allowlist protected",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scans.router)
app.include_router(calibration.router)
app.include_router(pattern_stats.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AttackGraph AI API"}

