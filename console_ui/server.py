"""
Laus Console Server - FastAPI Backend (Pilar 4)
Painel local de leitura para métricas do ledger paper e estado do sistema.
"""
import html
import json
import os
import secrets
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

BASE_DIR = Path(os.environ.get("LAUS_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
load_dotenv(BASE_DIR / ".env", override=False)

DB_PATH = str(BASE_DIR / "accounting_ledger" / "laus_vault.db")
STATE_PATH = str(BASE_DIR / "console_ui" / "specs" / "global_state.json")
security = HTTPBasic()


def require_console_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    expected_username = os.environ.get("LAUS_CONSOLE_USERNAME", "")
    expected_password = os.environ.get("LAUS_CONSOLE_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Console credentials are not configured",
        )

    username_matches = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        expected_username.encode("utf-8"),
    )
    password_matches = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        expected_password.encode("utf-8"),
    )
    if not (username_matches & password_matches):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


app = FastAPI(
    title="Laus Paper Dashboard",
    dependencies=[Depends(require_console_credentials)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def get_db_metrics():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(net_profit_usd), 0), "
                "COALESCE(SUM(tax_provision_brl), 0) FROM journal_entries"
            )
            total_ops, total_net, total_tax = cur.fetchone()
        return {
            "total_trades": int(total_ops),
            "pnl_usd": round(float(total_net), 4),
            "tax_brl": round(float(total_tax), 2),
        }
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return {"total_trades": 0, "pnl_usd": 0.0, "tax_brl": 0.0}


def get_system_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as state_file:
                state = json.load(state_file)
            if isinstance(state, dict):
                return state
        except (OSError, json.JSONDecodeError):
            pass
    return {"kill_switch": False, "status_reason": "Monitoramento ativo"}


@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    metrics = get_db_metrics()
    state = get_system_state()

    status_class = "danger" if state.get("kill_switch") else "success"
    status_text = "🔴 ATIVO (HALTED)" if state.get("kill_switch") else "🟢 INATIVO (RUNNING)"
    status_reason = html.escape(
        str(state.get("status_reason", "Nenhum motivo registrado")),
        quote=True,
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Laus Console UI</title>
        <style>
            body {{ background-color: #0f172a; color: #f8fafc; font-family: sans-serif; padding: 30px; }}
            .card {{ background-color: #1e293b; border: 1px solid #334155; color: #f8fafc; }}
            .status-box {{ padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; }}
            .status-success {{ background-color: #065f46; color: #34d399; }}
            .status-danger {{ background-color: #991b1b; color: #fca5a5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏛️ LAUS — Painel de Controle Quantitativo (paper)</h1>
            <div class="row g-4">
                <div class="col-md-12">
                    <div class="status-box status-{status_class}">
                        ESTADO DO KILL SWITCH: {status_text}<br>
                        <small>Motivo: {status_reason}</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>📈 Registros paper</h3>
                        <p class="fs-2 text-info">{metrics['total_trades']}</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>💰 PnL estimado (paper)</h3>
                        <p class="fs-2 text-success">${metrics['pnl_usd']:+.4f} USD</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>⚖️ Provisão simulada</h3>
                        <p class="fs-2 text-warning">R$ {metrics['tax_brl']:.2f}</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
