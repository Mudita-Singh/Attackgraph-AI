from fastapi import FastAPI
from api.routes import scans

app = FastAPI(
    title="AttackGraph AI API",
    description="Controlled Security Analysis Platform — Server-side allowlist protected",
    version="0.1.0"
)

app.include_router(scans.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AttackGraph AI API"}
