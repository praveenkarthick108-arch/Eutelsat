from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./eutelsat_testgen.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

# Enable WAL mode for concurrent read+write access (background ingest + API)
with engine.connect() as _conn:
    _conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
    _conn.execute(__import__("sqlalchemy").text("PRAGMA busy_timeout=30000"))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
