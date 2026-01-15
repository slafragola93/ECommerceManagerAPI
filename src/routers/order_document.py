from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import OrderDocumentSchema, AllOrderDocumentResponseSchema, OrderDocumentResponseSchema
from src.services.core.wrap import check_authentication
from ..services.routers.auth_service import authorize

router = APIRouter(
    prefix='/api/v1/order_documents',
    tags=['Order Document']
)


