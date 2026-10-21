"""
Laus Console Server - FastAPI Backend (Pilar 4)
Expõe os dados consolidados do Livro-Razão e o estado do Kill Switch para a UI.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json
import os
import sqlite3

app = FastAPI(title="Laus Autonomous Engine Dashboard")

from pathlib import Path

BASE_DIR = Path(os.environ.get("LAUS_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
DB_PATH = str(BASE_DIR / "accounting_ledger" / "laus_vault.db")
STATE_PATH = str(BASE_DIR / "console_ui" / "specs" / "global_state.json")

def get_db_metrics():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(net_profit_usd), 0), COALESCE(SUM(tax_provision_brl), 0) FROM journal_entries")
        total_ops, total_net, total_tax = cur.fetchone()
        conn.close()
        return {"total_trades": total_ops, "pnl_usd": round(total_net, 4), "tax_brl": round(total_tax, 2)}
    except Exception:
        return {"total_trades": 0, "pnl_usd": 0.0, "tax_brl": 0.0}

def get_system_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"kill_switch": False, "status_reason": "Monitoramento ativo"}

@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    metrics = get_db_metrics()
    state = get_system_state()
    
    status_class = "danger" if state.get("kill_switch") else "success"
    status_text = "🔴 DETONADO (HALTED)" if state.get("kill_switch") else "🟢 ATIVO (RUNNING)"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Laus Console UI</title>
        <link rel="stylesheet" href="https://jsdelivr.net">
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
            <h1 class="mb-4">🏛️ LAUS — Painel de Controle Quantitativo</h1>
            <div class="row g-4">
                <div class="col-md-12">
                    <div class="status-box status-{status_class}">
                        BARRAMENTO HARDWARE: {status_text}<br>
                        <small class="text-white-50">Motivo: {state.get('status_reason', 'Nenhum log gerado')}</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>📈 Operações</h3>
                        <p class="fs-2 text-info">{{metrics['total_trades']}}</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>💰 PnL Realizado</h3>
                        <p class="fs-2 text-success">+${{metrics['pnl_usd']:.4f}} USD</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3>⚖️ Fisco (IN 1888)</h3>
                        <p class="fs-2 text-warning">R$ {{metrics['tax_brl']:.2f}}</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
