"""
Laus Console UI & Observability - Telemetria e Trava de Segurança (Pilar 4)
Gerencia especificações visuais em awesome-design-md e manipula o Kill Switch global.
"""
import os    # <-- Injetado com sucesso para corrigir o NameError
import json
import time
from typing import Dict, Any, List

class TelemetryConsole:
    def __init__(self, state_path: str):
        self.state_path = state_path
        self._init_state()

    def _init_state(self):
        """Garante a existência do arquivo de estado global do painel."""
        if not os.path.exists(self.state_path):
            self.update_hardware_status(kill_switch_active=False, reason="System initialized")

    def get_current_state(self) -> Dict[str, Any]:
        """Lê o estado do painel em tempo real."""
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"kill_switch": True, "reason": "Erro de leitura de barramento"}

    def update_hardware_status(self, kill_switch_active: bool, reason: str):
        """Altera o estado do Kill Switch (bloqueio mecânico de ordens)."""
        state = {
            "kill_switch": kill_switch_active,
            "last_update": time.time(),
            "status_reason": reason,
            "metrics": {
                "heartbeat": "HEALTHY" if not kill_switch_active else "HALTED",
                "ui_template": "awesome-design-md"
            }
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)

    def render_awesome_design_spec(self, summary_metrics: Dict[str, Any]) -> str:
        """Gera a folha estática markdown padrão awesome-design-md para exibição na UI."""
        state = self.get_current_state()
        status_color = "🔴 HALTED" if state["kill_switch"] else "🟢 ACTIVE"
        
        spec = f"""---
component: TelemetryDashboard
theme: awesome-design-md
updated_at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state['last_update']))}
---

# 📊 Painel de Controle Laus UI

## ⚡ Estado do Hardware
- **Status Operacional:** {status_color}
- **Motivo do Estado:** {state['status_reason']}
- **Modo do Barramento:** Zero-Trust Sandbox

## 📈 Métricas Consolidadas (Ledger Engine)
- **Operações Concluídas:** {summary_metrics.get('total_operacoes', 0)}
- **PnL Consolidado Líquido:** +${summary_metrics.get('lucro_liquido_usd', 0.0):.4f} USD
- **Provisão Fiscal (IN 1888):** R$ {summary_metrics.get('provisao_ir_brl', 0.0):.2f}
"""
        return spec
