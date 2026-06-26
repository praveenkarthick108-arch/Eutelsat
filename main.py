import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from database import engine, SessionLocal
import models
from routes import generate, sessions, testcases, export, scope
from routes import followup, jira as jira_routes
from routes import rag as rag_routes
from rag import ingest as rag_ingest
from ai_pipeline import client


def _background_ingest():
    """Run RAG ingest in a background thread so startup is non-blocking."""
    db = SessionLocal()
    try:
        result = rag_ingest.ingest(db, client, force=False)
        status = result.get("status")
        if status == "ingested":
            print(f"[RAG] Ingested {result['chunks']} chunks from {result['source']}")
        elif status == "already_ingested":
            print(f"[RAG] Ready: {result['chunks']} chunks from {result['source']}")
        else:
            print(f"[RAG] Startup ingest result: {result}")
    except Exception as e:
        print(f"[RAG] Background ingest failed (non-fatal): {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)

    # Incremental column migrations — safe to re-run (errors mean column already exists)
    migrations = [
        "ALTER TABLE test_cases ADD COLUMN confidence_score REAL DEFAULT 0.85",
        "ALTER TABLE test_cases ADD COLUMN hallucination_risk TEXT DEFAULT 'Low'",
        "ALTER TABLE sessions ADD COLUMN from_cache INTEGER DEFAULT 0",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

    print("Database ready")

    # Kick off RAG ingest in the background — server starts immediately
    t = threading.Thread(target=_background_ingest, daemon=True)
    t.start()
    print("[RAG] Background ingest started...")

    yield


app = FastAPI(
    title="Eutelsat GenAI Test Case Generator",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(generate.router,      prefix="/api", tags=["generate"])
app.include_router(sessions.router,      prefix="/api", tags=["sessions"])
app.include_router(testcases.router,     prefix="/api", tags=["testcases"])
app.include_router(export.router,        prefix="/api", tags=["export"])
app.include_router(scope.router,         prefix="/api", tags=["scope"])
app.include_router(followup.router,      prefix="/api", tags=["followup"])
app.include_router(jira_routes.router,   prefix="/api", tags=["jira"])
app.include_router(rag_routes.router,    prefix="/api", tags=["rag"])

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    print("\nEutelsat GenAI Test Case Generator v2.0")
    print("Starting server at http://0.0.0.0:8000")
    print("Share with team: http://<your-ip>:8000\n")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["*.db", "*.db-shm", "*.db-wal"],
    )
