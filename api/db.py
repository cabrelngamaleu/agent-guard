import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

url = URL.create(
    "postgresql+psycopg",
    username="guard",
    password=os.environ["DB_PASSWORD"],
    host="localhost",
    port=5432,
    database="guard",
)
engine = create_engine(url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass