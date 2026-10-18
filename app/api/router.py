"""
文件说明: 该模块定义了FastAPI应用的路由，包括各个子模块的路由注册。
"""
from fastapi import APIRouter

from app.api.v1 import auth, chat, documents, jobs, knowledge_bases, search

router = APIRouter(prefix="/api/v1")
for module in (auth, knowledge_bases, documents, jobs, search, chat):
    router.include_router(module.router)

