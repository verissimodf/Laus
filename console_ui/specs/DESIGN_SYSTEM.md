# 🎨 Laus Console Design System Spec
> Inspirado nas convenções do VoltAgent/awesome-design-md e focado em interfaces analíticas de missão crítica.

## Paleta de Cores (Dark Mode Nativo)
- **Background Principal:** `#0B0F17` (Deep Obsidian)
- **Superfície dos Cards/Modais:** `#131B2A` (Slate Navy)
- **Bordas e Divisores:** `#1F293D` (Subtle Steel)
- **Acentos e Destaques:**
  - Primário (Jarvis Core): `#38BDF8` (Sky Cyan)
  - Sucesso / Compra / Spread Positivo: `#10B981` (Emerald)
  - Perigo / Kill Switch / Erro Crítico: `#EF4444` (Crimson)
  - Alerta / Drawdown Moderado: `#F59E0B` (Amber)

## Filosofia de Layout
1. **Densidade de Informação Eficiente:** Tabelas de ordens e spreads com fontes monoespaçadas (`JetBrains Mono` ou `Fira Code`).
2. **Kill Switch de Acesso Rápido:** Sempre fixado no cabeçalho superior direito com confirmação por duplo clique/deslizamento.
3. **Telemetria PostHog Integrada:** Cada clique de estratégia e alteração de parâmetros gera evento tipado para auditoria.
