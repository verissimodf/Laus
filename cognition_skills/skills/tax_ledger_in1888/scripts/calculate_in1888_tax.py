#!/usr/bin/env python3
"""
Motor de Cálculo Fiscal e Partidas Dobradas — IN 1888 (Pilar 8)
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Adiciona modulo de contabilidade ao path
ledger_dir = project_root / "accounting_ledger"
if str(ledger_dir) not in sys.path:
    sys.path.insert(0, str(ledger_dir))

from ledger_engine import AccountingLedger


def audit_tax_and_ledger(db_path: str = None):
    print("=" * 60)
    print("⚖️ AUDITORIA CONTÁBIL E COMPLIANCE FISCAL (IN 1888)")
    print("=" * 60)

    if db_path is None:
        db_path = str(project_root / "accounting_ledger" / "laus_vault.db")

    ledger = AccountingLedger(db_path)

    # 1. Simulação de registro contábil de arbitragem
    entry = ledger.record_arbitrage_trade(
        symbol="USDT/BRL",
        amount_usd=500.0,
        rate=5.48,
        spread_pct=0.85,
        source="ArbEngine_Pilar2"
    )

    print(f"[OK] Lançamento de Partidas Dobradas Registrado:")
    print(f"     ID Registro: #{entry['entry_id']}")
    print(f"     Lucro Líquido Realizado: ${entry['net_profit_usd']:.4f} USD")
    print(f"     Taxas Descontadas:       ${entry['fee_usd']:.4f} USD")
    print(f"     Provisão IRPF (15%):     R$ {entry['tax_provision_brl']:.2f}")

    # 2. Resumo Consolidado
    summary = ledger.get_summary()
    print(f"\n[BALANÇO CONSOLIDADO DO LEDGER]:")
    print(f"     Total de Transações:     {summary['total_operacoes']}")
    print(f"     Lucro Líquido Acumulado: ${summary['lucro_liquido_usd']:.2f} USD")
    print(f"     Provisão Fiscal Total:   R$ {summary['provisao_ir_brl']:.2f}")

    # 3. Alerta de Limite IN 1888
    volume_mensal_brl = summary['total_operacoes'] * 500.0 * 5.48
    limite_in1888 = 30000.00
    alerta_80 = limite_in1888 * 0.80

    print(f"\n[STATUS DA IN 1888/2019 (RECEITA FEDERAL)]:")
    print(f"     Volume Estimado no Mês:  R$ {volume_mensal_brl:,.2f}")
    print(f"     Limite de Notificação:   R$ {limite_in1888:,.2f}")
    if volume_mensal_brl >= limite_in1888:
        print("     🚨 STATUS: DECLARAÇÃO OBRIGATÓRIA (Limite Excedido)")
    elif volume_mensal_brl >= alerta_80:
        print("     ⚠️ STATUS: ALERTA DE PROXIMIDADE (>= 80% do limite)")
    else:
        print("     ✅ STATUS: DENTRO DO LIMITE DE ISENÇÃO DE REPORTE")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    audit_tax_and_ledger()
