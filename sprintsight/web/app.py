"""Stage 6 FastAPI app (SS-6) + Stage 5 auth gate (SS-34)."""

from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sprintsight.config import load_env
from sprintsight.web import crosstool_service, service
from sprintsight.web.auth.session import (
    is_dev,
    issue_csrf,
    login_session,
    logout_session,
    require_api_user,
    session_secret,
    session_user,
    valid_csrf,
)
from sprintsight.web.auth.users import User, make_authenticator

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))
# Expose the per-session CSRF minter to templates so the shared shell's logout form can
# carry a token without every authenticated route having to thread it through its context.
# On authenticated renders this only ever READS the session: you reach a logged-in page only
# via POST /login, which already required the token GET /login minted, so it is present by
# then. It mints (a session write) solely pre-login, where login.html passes csrf_token
# explicitly and the logout form is not rendered — so no authenticated GET rewrites the cookie.
_TEMPLATES.env.globals["issue_csrf"] = issue_csrf
_THEME = _HERE / "static" / "theme"


def create_app() -> FastAPI:
    load_env()
    app = FastAPI(title="Sprintsight watermelon detector")
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        same_site="lax",
        https_only=not is_dev(),
    )
    app.mount("/css", StaticFiles(directory=str(_THEME / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(_THEME / "js")), name="js")
    app.mount("/illos", StaticFiles(directory=str(_THEME / "illos")), name="illos")
    app.mount("/fonts", StaticFiles(directory=str(_THEME / "fonts")), name="fonts")
    authenticator = make_authenticator()

    @app.get("/login", response_class=HTMLResponse)
    def page_login(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request, "login.html", {"error": None, "user": None, "csrf_token": issue_csrf(request)}
        )

    @app.post("/login")
    def do_login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        csrf_token: str = Form(""),
    ):
        # CSRF guard runs BEFORE authentication, so a forged POST never probes credentials.
        if not valid_csrf(request, csrf_token):
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {
                    "error": "Your session expired. Please try again.",
                    "user": None,
                    "csrf_token": issue_csrf(request),
                },
                status_code=400,
            )
        user = authenticator.authenticate(email, password)
        if user is None:
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid email or password.", "user": None,
                 "csrf_token": issue_csrf(request)},
                status_code=200,
            )
        login_session(request, user)
        return RedirectResponse("/", status_code=303)

    @app.post("/logout")
    def do_logout(request: Request, csrf_token: str = Form("")) -> RedirectResponse:
        # Sign-out is state-changing, so it is a CSRF-guarded POST: a forged cross-site
        # request (no/wrong token) is rejected and leaves the session intact (fail closed).
        if not valid_csrf(request, csrf_token):
            raise HTTPException(status_code=400, detail="invalid csrf token")
        logout_session(request)
        return RedirectResponse("/login", status_code=303)

    @app.get("/api/portfolio")
    def api_portfolio(user: User = Depends(require_api_user)) -> list[dict]:  # noqa: B008
        return [asdict(row) for row in service.portfolio()]

    @app.get("/api/team/{team_id}")
    def api_team(
        team_id: str,
        audience: str = service.DEFAULT_AUDIENCE,
        user: User = Depends(require_api_user),  # noqa: B008
    ) -> dict:
        detail = service.team_detail(team_id, audience)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return asdict(detail)

    @app.get("/api/crosstool")
    def api_crosstool(user: User = Depends(require_api_user)) -> dict:  # noqa: B008
        return asdict(crosstool_service.crosstool_view())

    @app.get("/crosstool", response_class=HTMLResponse)
    def page_crosstool(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        page = crosstool_service.crosstool_view()
        return _TEMPLATES.TemplateResponse(
            request, "crosstool.html", {"page": page, "user": user}
        )

    @app.get("/", response_class=HTMLResponse)
    def page_portfolio(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        rows = service.portfolio()
        return _TEMPLATES.TemplateResponse(
            request,
            "portfolio.html",
            {"rows": rows, "summary": service.summarize(rows), "user": user},
        )

    @app.get("/team/{team_id}", response_class=HTMLResponse)
    def page_team(
        request: Request, team_id: str, audience: str = service.DEFAULT_AUDIENCE
    ) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        detail = service.team_detail(team_id, audience)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown team")
        return _TEMPLATES.TemplateResponse(request, "team.html", {"d": detail, "user": user})

    @app.get("/admin/accounts", response_class=HTMLResponse)
    def page_admin_accounts(request: Request) -> HTMLResponse:
        user = session_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        return _TEMPLATES.TemplateResponse(
            request,
            "admin_accounts.html",
            {"user": user, "accounts": authenticator.all_users()},
        )

    return app


app = create_app()
