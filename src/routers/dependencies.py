from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.auth import get_current_user
import os

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

MAX_LIMIT = os.environ.get("MAX_LIMIT")
LIMIT_DEFAULT = int(os.environ.get("LIMIT_DEFAULT"))
