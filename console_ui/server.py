"""
Laus Console Server - FastAPI Backend (Pilar 4)
Painel local de leitura para métricas do ledger paper e estado do sistema.
"""
import html
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Header, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from core_jarvis.state import kill_switch_path, read_kill_switch
from core_jarvis.orchestrator import JarvisOrchestrator
from pydantic import BaseModel, Field
from cognition_skills.skills.posthog_telemetry.scripts.emit_posthog_event import capture_laus_event

BASE_DIR = Path(os.environ.get("LAUS_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
load_dotenv(BASE_DIR / ".env", override=False)

DB_PATH = os.environ.get("LAUS_LEDGER_PATH", str(BASE_DIR / "accounting_ledger" / "laus_vault.db"))
STATE_PATH = str(kill_switch_path())
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
        with closing(sqlite3.connect(Path(DB_PATH).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
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
            "available": True,
        }
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return {"total_trades": 0, "pnl_usd": 0.0, "tax_brl": 0.0, "available": False}


def get_system_state():
    active, reason = read_kill_switch(STATE_PATH)
    worker_verified = False
    try:
        worker = json.loads((Path(STATE_PATH).parent / "worker.status.json").read_text(encoding="utf-8"))
        worker_verified = 0 <= time.time() - worker["timestamp"] < 60
        if worker_verified and worker.get("emergency_stop") is True:
            active, reason = True, worker.get("reason") or "WORKER_LATCHED_RESTART_REQUIRED"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {"kill_switch": active, "status_reason": reason or "Paper habilitado no estado persistido",
            "worker_verified": worker_verified}


class EmergencyRequest(BaseModel):
    confirmation: str
    reason: str = Field(min_length=1, max_length=500)


@app.post("/api/emergency")
def activate_emergency(body: EmergencyRequest, x_laus_action: str = Header(default="")):
    # Custom header prevents cross-origin form submissions with cached Basic auth.
    if x_laus_action != "activate-emergency" or body.confirmation != "HALT PAPER" or not body.reason.strip():
        raise HTTPException(status_code=400, detail="Explicit emergency confirmation required")
    orchestrator = JarvisOrchestrator(kill_switch_path=STATE_PATH)
    orchestrator.trigger_kill_switch(body.reason.strip())
    active, reason = read_kill_switch(STATE_PATH)
    if not active or reason != body.reason.strip():
        raise HTTPException(status_code=503, detail="Emergency state could not be persisted")
    capture_laus_event("laus_operator_emergency", "console_operator", {"status": "HALTED"})
    return {"kill_switch": True, "scope": "paper", "reset": "local operator command required"}


@app.get("/console.js")
def console_script():
    return Response('''document.getElementById("emergency").onclick = async () => {
      if (!window.confirm("Interromper novas simulações paper?")) return;
      const response = await fetch("/api/emergency", {method:"POST",
        headers:{"Content-Type":"application/json","X-Laus-Action":"activate-emergency"},
        body:JSON.stringify({confirmation:"HALT PAPER",reason:"Console operator emergency"})});
      if (response.ok) location.reload(); else window.alert("Falha ao persistir parada: " + response.status);
    };''', media_type="application/javascript")


@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    metrics = get_db_metrics()
    state = get_system_state()
    availability = "" if metrics.get("available", True) else "Ledger indisponível: métricas abaixo não verificadas"

    status_class = "danger" if state.get("kill_switch") else "success"
    status_text = "🔴 ATIVO (HALTED)" if state.get("kill_switch") else "INATIVO (ESTADO PAPER LIBERADO)"
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
            body {{ background-color: #06090F; color: #F8FAFC; font-family: sans-serif; padding: 30px; }}
            .card {{ background-color: #0B101B; border: 1px solid #1E293B; color: #F8FAFC; }}
            p {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }}
            #emergency {{ float: right; background: #DC2626; color: #F8FAFC; padding: 12px; }}
            .shadow {{ color: #F59E0B; }}
            .status-box {{ padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; }}
            .status-success {{ background-color: #065f46; color: #34d399; }}
            .status-danger {{ background-color: #991b1b; color: #fca5a5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <button id="emergency" type="button">PARAR PAPER</button>
            <p class="shadow">SHADOW / PAPER TRADING — {availability}</p>
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
        <script src="/console.js" defer></script>
    </body>
    </html>
    """
    return html_content
