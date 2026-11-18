# Plan de prueba (4 fases)

Regla: no pases de fase hasta cumplir los criterios. Con menos de 50 trades, los resultados no dicen nada.

## Fase 0 · Humo (30 min)
1. Despliega en Railway con `railway_variables_test.env` (modo `signals`). Debe llegar "🤖 Bot OFS iniciado".
2. Envía los ejemplos: `python send_example.py example_long_entry.json https://TU-APP.up.railway.app TU_SECRET`
   y repite con `example_absorption.json`, `example_trailing_update.json`, `example_target_hit.json`.
   (Ojo: `example_long_entry.json` es del lunes 15:35 UTC: cae dentro del horario 13-17.)
3. `GET /status?secret=…` → debe mostrar 1 trade cerrado y +3.0R. `GET /report?secret=…&days=7` → informe en Telegram.
4. `GET /scan?secret=…` → resumen del escáner en Telegram (tarda ~1 min).
✔ Criterio: todos los mensajes llegan y no hay errores en los logs de Railway.

## Fase 1 · Señales reales sin dinero (2 semanas, `signals`)
1. En TradingView: añade `OFS_Indicador_ES_TEST.pine` en 5m, gráfico `BINANCE:BTCUSDT.P` (mejor volumen) y otro igual para ETH. Crea la alerta "Any alert() function call" con el webhook por símbolo.
2. Cada día compara 3–5 señales de Telegram con el gráfico: ¿la zona, el valor y la absorción son los que ves?
3. Apunta en una hoja: hora, moneda, lado, calidad de la zona (LVN/sin testear/normal), resultado.
✔ Criterio: las señales coinciden con el gráfico y el informe semanal no muestra errores de lectura.

## Fase 2 · Backtest en TradingView (en paralelo)
- Carga `OFS_Estrategia_Backtest_ES_TEST.pine` en BTC y ETH (5m) y mira *Strategy Tester*: nº de operaciones, factor de beneficio, drawdown máximo, R medio.
- Cambia **un** parámetro cada vez. Compara contra el perfil de fábrica (`OFS_Indicador_ES.pine`).
✔ Criterio: más de 100 operaciones simuladas y factor de beneficio > 1.3 después de comisiones.

## Fase 3 · Demo (2–4 semanas, `TRADING_MODE=demo`)
1. Crea la API key de la cuenta demo (VST) de BingX, ponla en `BINGX_API_KEY/SECRET` y cambia `TRADING_MODE=demo`.
2. Comprueba en BingX que entrada, stop y objetivo salen donde dice Telegram, y que el stop se mueve en cada `TRAILING`.
3. Revisa el informe semanal (domingo 20:00 UTC).
✔ Criterio: 30+ trades, ejecución correcta, R medio positivo y sin incidencias de stops sin colocar.

## Fase 4 · Real con riesgo mínimo (solo si pasaste las anteriores)
`TRADING_MODE=live`, `RISK_PCT=0.1`, una sola moneda, API key sin permiso de retiro. Sube el riesgo solo tras 50+ trades reales con resultado coherente con la demo.

## Cuándo parar
- 2 pérdidas seguidas en un día → el bot ya se detiene (`MAX_LOSS_STREAK`).
- Drawdown semanal > 5 R → pausa y revisa antes de seguir.
- Cualquier orden sin stop o mensaje de error repetido → vuelve a `signals`.
