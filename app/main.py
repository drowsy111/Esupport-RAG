import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.lifespan import lifespan


def create_app(settings=None, lifespan_override=None):
    setup_logging()
    application = FastAPI(
        title="Enterprise Support RAG", version="0.1.0",
        lifespan=lifespan_override or lifespan,
    )
    if settings is not None:
        application.state.settings = settings

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        # Early declared-size guard; reverse proxy must enforce actual body size as well.
        if request.url.path.endswith("/documents/upload"):
            limit = application.state.settings.upload_max_bytes + 1024 * 1024
            declared = request.headers.get("content-length")
            if declared:
                try:
                    too_large = int(declared) > limit or int(declared) < 0
                except ValueError:
                    too_large = True
                if too_large:
                    return JSONResponse(status_code=413, content={
                        "code": "FILE_TOO_LARGE", "message": "请求体超过上传限制",
                        "request_id": request.state.request_id,
                    })
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status, content={
            "code": exc.code, "message": exc.message,
            "request_id": getattr(request.state, "request_id", ""),
        })

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic input values may contain passwords: omit them from responses/logs.
        return JSONResponse(status_code=422, content={
            "code": "VALIDATION_ERROR", "message": "请求参数不符合接口要求",
            "request_id": getattr(request.state, "request_id", ""),
            "fields": [list(error["loc"]) for error in exc.errors()],
        })

    @application.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.getLogger(__name__).error(
            "request_failed request_id=%s type=%s",
            getattr(request.state, "request_id", ""), type(exc).__name__,
        )
        return JSONResponse(status_code=500, content={
            "code": "INTERNAL_ERROR", "message": "请求处理失败",
            "request_id": getattr(request.state, "request_id", ""),
        })

    @application.get("/health/live")
    def live():
        return {"status": "ok", "scope": "process"}

    application.include_router(router)
    return application


app = create_app()

