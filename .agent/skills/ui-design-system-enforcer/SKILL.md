---
name: ui-design-system-enforcer
description: Aplica rigorosamente as diretrizes visuais do Laus Design System (docs/design-system.md) em qualquer desenvolvimento ou refatoração no diretório console-ui/.
triggers:
  - "console-ui"
  - "frontend"
  - "design-system"
  - "dashboard"
  - "ui"
  - "componentes"
  - "tailwind"
  - "shadcn"
---

# UI Design System Enforcer — Laus Console

Esta habilidade obriga a conformidade estrita com o sistema de design financeiro de alta densidade especificado em `docs/design-system.md` (inspirado no padrão `VoltAgent/awesome-design-md`).

## 1. Diretriz Mandatória
Antes de gerar, refatorar ou modificar qualquer componente React/Next.js dentro de `console-ui/`:
1. Leia integralmente o arquivo `docs/design-system.md`.
2. Nunca adicione classes de cores arbitrárias fora da paleta oficial do Laus.
3. Nunca utilize fontes proporcionais para números de mercado, cotações ou saldos.

---

## 2. Tokens Visuais Obrigatórios

### Superfícies e Fundos
- **Global Canvas:** `#06090F` (`bg-[#06090F]`)
- **Painéis e Cards:** `#0B101B` (`bg-[#0B101B]`)
- **Headers e Inputs:** `#111827` (`bg-gray-900`)
- **Bordas Sutis:** `#1E293B` (`border-[#1E293B]`)

### Acentos e Indicadores de Estado
- **Ciano Cognitivo (Jarvis/Skills):** `#00F0FF` (`text-[#00F0FF]`, `border-[#00F0FF]`)
- **Violeta Neural (Swarm MiroFish):** `#8B5CF6` (`text-[#8B5CF6]`)
- **Verde Esmeralda (Bull/Lucro):** `#10B981` (`text-[#10B981]`)
- **Vermelho Carmesim (Bear/Prejuízo):** `#F43F5E` (`text-[#F43F5E]`)
- **Âmbar Simulação (Shadow Mode):** `#F59E0B` (`text-[#F59E0B]`, `border-[#F59E0B]`)
- **Vermelho Crítico (Kill Switch):** `#DC2626` (`bg-[#DC2626]/20`, `border-[#DC2626]`)

---

## 3. Regra de Ouro da Tipografia Quantitativa
Qualquer exibição de dado financeiro ou telemétrico (preço USD-BRL, saldo de conta, spread em bps, PnL, latência em ms, taxa de gás, hash de transação, código ISPB ou contagem de tokens) **DEVE** utilizar:

```tsx
<span className="font-mono tabular-nums text-xs text-[#F8FAFC]">
  {formatCurrency(price)}
</span>
```

A propriedade `tabular-nums` (`font-variant-numeric: tabular-nums`) garante largura idêntica para todos os dígitos de 0 a 9, impedindo o salto visual da interface durante atualizações em tempo real via WebSocket.

---

## 4. Elementos Críticos de Missão
1. **Destaque do Modo Shadow vs. Live Execution:**
   - Todo card ou cabeçalho associado ao Gêmeo Digital (`digital-twin`) deve portar a tag/borda âmbar `SHADOW / PAPER TRADING`.
   - Execuções com custódia real devem portar a tag esmeralda `LIVE MPC`.
2. **Kill Switch Permanente:**
   - Botão de parada emergencial posicionado no canto superior direito da Topbar (`h-12`).
   - Requer confirmação de 2 etapas (`Hold 1.5s` ou modal via atalho `Shift + Esc`).
3. **Telemetria PostHog:**
   - Toda ação relevante do operador (mudança de estratégia, disparo de ordem manual, acionamento do Kill Switch) deve emitir `posthog.capture("nome_do_evento")`.

---

## 5. Checklist de Verificação Antes da Conclusão
- [ ] Leitura prévia de `docs/design-system.md` efetuada?
- [ ] Todos os valores numéricos usam `font-mono tabular-nums`?
- [ ] Fundo do canvas respeita `#06090F` e bordas `#1E293B`?
- [ ] O Kill Switch e o seletor Shadow/Live estão visíveis?
