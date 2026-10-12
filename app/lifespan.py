from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.db.session import create_session_factory
from app.services.resources import Resources


@asynccontextmanager
async def lifespan(app):
    settings = getattr(app.state, "settings", None) or get_settings()
    settings.validate_runtime()
    engine, factory = create_session_factory(settings.database_url)
    app.state.settings, app.state.engine = settings, engine
    app.state.session_factory = factory
    app.state.resources = Resources.production(settings)
    try:
        yield
    finally:
        app.state.resources.close()
        engine.dispose()

