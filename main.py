from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from database import engine
import models
from routes import generate, sessions, testcases, export, scope
from routes import followup, jira as jira_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)

    # Incremental column migrations — safe to re-run (errors mean column exists)
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
                pass  # column already exists

    print("Database ready")
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
