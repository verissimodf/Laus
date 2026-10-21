# Especificação Técnica — AwesomeAPI e BrasilAPI

## 1. AwesomeAPI (Cotações de Moedas)
- **Endpoint:** `GET https://economia.awesomeapi.com.br/json/last/USD-BRL`
- **Campos Principais:**
  - `bid`: Cotação de compra fiduciária.
  - `ask`: Cotação de venda fiduciária.
  - `high`, `low`: Máxima e mínima do dia.
  - `pctChange`: Variação percentual diária.
  - `timestamp`: Timestamp Unix da última atualização.

## 2. BrasilAPI (Cadastro de Bancos e Compensação)
- **Endpoint:** `GET https://brasilapi.com.br/api/banks/v1`
- **Uso:** Validação de participantes do Sistema de Pagamentos Brasileiro (SPB), ISPB e códigos COMPE para liquidação de rampas fiat (PIX/TED).
- **Campos:** `ispb`, `name`, `code`, `fullName`.

## 3. Modelo Matemático de Spread Líquido
$$\Delta_{\text{net}} = \frac{P_{\text{crypto}} - P_{\text{fiat}}}{P_{\text{fiat}}} - \left( f_{\text{maker/taker}} + f_{\text{withdrawal}} + f_{\text{iof/pix}} + s_{\text{slippage}} \right)$$
- Gatilho típico de arbitragem: $\Delta_{\text{net}} > 0.0065$ ($65\text{ bps}$).
