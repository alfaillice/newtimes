---
estado: caida
desde: '2026-11-19T21:10:03+01:00'
detalle: 'API: HTTP 400 invalid_request_error: Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'
modelo: claude-haiku-5-5
---

# Estado de la API (redactor del servidor)

**La API de Anthropic rechaza las peticiones del redactor del servidor: no se publican noticias.**

Error: `API: HTTP 400 invalid_request_error: Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.`

Qué revisar, según el error:
- `credit balance is too low` o `usage limits`: recargar saldo o subir el límite de gasto en console.anthropic.com (Billing / Limits). Conviene activar la recarga automática.
- `authentication_error` (401) o `permission_error` (403): la clave de /etc/newtimes/redactor.env está revocada o es de otro espacio de trabajo.
- `not_found_error` (404) sobre el modelo: el modelo de NEWTIMES_MODELO no existe o se ha retirado.
- `rate_limit_error` (429) u `overloaded_error` (529): suele pasar solo; si dura horas, revisar el nivel de uso.

Registro: `sudo journalctl -u newtimes-salud-api -n 20` y `sudo journalctl -u newtimes-encargos -n 30`.
