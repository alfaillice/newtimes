# NewTimes.news: crecimiento y SEO

Documento vivo. Lo actualiza la revisión semanal (y cualquier revisión manual): prioridades, estado de cada acción y datos disponibles.
Leyenda: ✅ hecho y verificado · 🛠 hecho, pendiente de verificar en producción · 📋 preparado/recomendado · ⛔ bloqueado (necesita a JM Triviño)

## Prioridades vigentes (ordenadas por impacto, urgencia y esfuerzo)

| # | Acción | Impacto | Urgencia | Esfuerzo | Responsable | Estado |
|---|---|---|---|---|---|---|
| 1 | Verificar newtimes.news en Google Search Console (registro TXT en Cloudflare) y enviar sitemap.xml y sitemap-noticias.xml | Muy alto | Alta | 15 min | JM | ⛔ |
| 2 | Reejecutar el instalador en el VPS (activa 301/410 de URLs antiguas, CSP para AdSense y YouTube) | Alto | Alta | 5 min | JM | ⛔ |
| 3 | Comprobar que la redacción horaria publica y cubre todas las secciones | Muy alto | Alta | — | Claude | 📋 |
| 4 | Alta en Bing Webmaster Tools (importar desde Search Console) | Medio | Media | 10 min | JM | ⛔ |
| 5 | Google News: alta en Publisher Center con logo, secciones y RSS | Alto | Media | 30 min | JM | ⛔ |
| 6 | Perfiles de marca (X, Bluesky, Telegram, canal de WhatsApp) y añadirlos a `perfiles` en config/site.yaml | Medio | Media | 1 h | JM + Claude | 📋 |
| 7 | AdSense: mensaje RGPD publicado, sitio aprobado, anuncios automáticos desactivados | Alto (ingresos) | Alta | 20 min | JM | ⛔ |
| 8 | Páginas de tema "pilares" para asuntos con recorrido (Urda/alta velocidad, inflación, elecciones) con contexto propio | Medio | Media | Medio | Claude | 📋 |
| 9 | Fuentes WOFF2 (menos peso en tipografías) generadas en el servidor | Bajo | Baja | Bajo | Claude | 📋 |

## Registro de revisiones

### Revisión 1 · 30/10/2026 18:55
**Datos verificados**
- `site:newtimes.news`: Google tiene indexadas URLs de la web anterior (`/noticias/<id>/...`, `/es/noticias/...`). Ninguna URL de la web nueva aún.
- Búsqueda "newtimes.news": ningún resultado propio; la marca compite con New Times (Ruanda), Miami/Phoenix New Times.
- Producción: robots.txt con los dos sitemaps; sitemap-noticias válido con 6 noticias; ads.txt correcto; botón Directo, bloque de publicidad y "Configurar cookies" presentes.
- Medición local (aproximada, sin AdSense ni red real): portada móvil 32 KB propios/12 peticiones, noticia 74 KB/8, CLS 0,000.
- No disponible: PageSpeed Insights (API inaccesible desde el entorno), cabeceras HTTP reales, Search Console, analítica.

**Cambios (commit 269d2f4)** 🛠
- Páginas `/tema/<etiqueta>/` enlazadas desde cada noticia; noindex si tienen menos de 3 noticias.
- BreadcrumbList en noticias; NewsMediaOrganization y WebSite en portada.
- `robots: max-image-preview:large` y `fetchpriority="high"` en la imagen principal.
- sitemap.xml con `lastmod`.
- IndexNow tras cada construcción en el servidor.
- nginx: 301 de `/categoria/*` a secciones; 410 para noticias de la web anterior (requiere reejecutar el instalador).

## Datos que faltan para medir
- Search Console: impresiones, clics, CTR, posición, cobertura, Discover, Google News.
- Analítica de visitas: ninguna instalada (opción sin cookies: Plausible/Umami en el VPS).
- AdSense: aprobación, RPM, ingresos.
- Core Web Vitals reales (CrUX), cuando haya tráfico.
