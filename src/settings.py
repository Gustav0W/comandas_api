from dotenv import load_dotenv, find_dotenv
import os

dotenv_file = find_dotenv()

load_dotenv(dotenv_file)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", "8000")
RELOAD = os.getenv("RELOAD", True)

DB_SGDB = os.getenv("DB_SGDB")
DB_NAME = os.getenv("DB_NAME")

if DB_SGDB == 'sqlite':
    STR_DATABASE = f"sqlite:///{DB_NAME}.db"
elif DB_SGDB == 'mysql': # MySQL
    import pymysql
    STR_DATABASE = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
elif DB_SGDB == 'mssql': # SQL Server
    import pymssql
    STR_DATABASE = f"mssql+pymssql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8"
else: # SQLite
    STR_DATABASE = f"sqlite:///apiDatabase.db"

SECRET_KEY = os.getenv("SECRET_KEY", "d3b78b1492b4ff227b204df969df5df052e983ea0b99e418798fb5f9a2a9af45")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))