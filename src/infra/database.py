from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from settings import STR_DATABASE
from sqlalchemy.orm import Session


engine = create_engine(STR_DATABASE, echo=True)

Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)

Base = declarative_base()

async def cria_tabelas():
    Base.metadata.create_all(engine)

def get_db():
    db_session = Session()
    try:
        yield db_session
    finally:
        db_session.close()