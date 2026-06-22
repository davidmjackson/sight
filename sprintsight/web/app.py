"""Stage 6 FastAPI app (SS-6) + Stage 5 auth gate (SS-34)."""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sprintsight.web import service
from sprintsight.web.auth.session import login_session, logout_session, session_secret
from sprintsight.web.auth.users import SeedAuthenticator

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Sprintsight watermelon detector")
    app.add_middleware(
        SessionMiddleware, secret_key=session_secret(), same_site="lax", https_only=False
    )
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
    authenticator = SeedAuthenticator()

    @app.get("/login", response_class=HTMLResponse)
    def page_login(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request, "login.html", {"error": None, "user": None}
        )

    @app.post("/login")
    def do_login(
        request: Request, email: str = Form(...), password: str = Form(...)
    ):
        user = authenticator.authenticate(email, password)
        if user is None:
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid email or password.", "user": None},
                status_code=200,
            )
        login_session(request, user)
        return RedirectResponse("/", status_code=303)

    @app.get("/logout")
    def do_logout(request: Request) -> RedirectResponse:
        logout_session(request)
        return RedirectResponse("/login", status_code=303)

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
            request, "portfolio.html", {"rows": service.portfolio(), "user": None}
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(request: Request, team_id: str) -> HTMLResponse:
        detail = service.team_detail(team_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail, "user": None})

    return app


app = create_app()
