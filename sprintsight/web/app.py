"""Stage 6 FastAPI app (SS-6): portfolio grid + per-team watermelon drill-in."""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sprintsight.web import service

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Sprintsight watermelon detector")
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    @app.get("/api/portfolio")
    def api_portfolio() -> list[dict]:
        return [asdict(row) for row in service.portfolio()]

    @app.get("/api/team/{team_id}")
    def api_team(team_id: str) -> dict:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)

    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request, "portfolio.html", {"rows": service.portfolio()}
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(request: Request, team_id: str) -> HTMLResponse:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail})

    return app


app = create_app()
