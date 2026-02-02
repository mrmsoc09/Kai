from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://k1:k1pass@localhost:5432/k1")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
