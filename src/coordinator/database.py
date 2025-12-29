from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..shared.config import config

# Create database engine
engine = create_engine(
    config.coordinator.database_url,
    connect_args={"check_same_thread": False} if config.coordinator.database_url.startswith("sqlite") else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
