from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .utils.logging import setup_logging
from .utils.config import get_config
from .api.recommend import router as recommend_router
from .api.ingest import router as ingest_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()

    app = FastAPI(title="NLQ Team/SRM Recommender (PoC)", version="0.1.0")

    # CORS for intranet PoC
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static and templates
    app.mount("/static", StaticFiles(directory=str(__file__).replace("main.py", "static")), name="static")
    templates = Jinja2Templates(directory=str(__file__).replace("main.py", "templates"))

    # Include API routers
    app.include_router(recommend_router)
    app.include_router(ingest_router)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve the simple UI page."""
        # Trigger config load early to fail fast if misconfigured
        _ = get_config()
        return templates.TemplateResponse("index.html", {"request": request})

    return app


app = create_app()


