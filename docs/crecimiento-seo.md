# NewTimes.news: crecimiento y SEO

Documento vivo. Lo actualiza la revisión semanal (y cualquier revisión manual): prioridades, estado de cada acción y datos disponibles.
Leyenda: ✅ hecho y verificado · 🛠 hecho, pendiente de verificar en producción · 📋 preparado/recomendado · ⛔ bloqueado (necesita a JM Triviño)

## Prioridades vigentes (ordenadas por impacto, urgencia y esfuerzo)

| # | Acción | Impacto | Urgencia | Esfuerzo | Responsable | Estado |
|---|---|---|---|---|---|---|
| 1 | Verificar newtimes.news en Google Search Console (registro TXT en Cloudflare) y enviar sitemap.xml, sitemap-noticias.xml y /en/sitemap-noticias.xml | Muy alto | Alta | 15 min | JM | ⛔ |
| 2 | Reejecutar el instalador en el VPS (activa 301/410 de URLs antiguas, CSP para AdSense y YouTube) | Alto | Alta | 5 min | JM | ⛔ |
| 3 | Fuentes: enlazar la nota original de la agencia u organismo (EFE, Europa Press, oficiales) en vez de reproducciones (Infobae = 39 % de las fuentes; dominios fuera de la lista de GUIA.md) | Alto (E-E-A-T, Google News) | Alta | Medio | Claude (guía/agentes) + JM (decidir) | 📋 |
| 4 | Equilibrar secciones: Tecnolog-IA, Cultura y Ciencia y salud con 4 noticias/semana frente a 14 de Internacional | Alto | Media | Bajo | Claude (jefe de redacción) | 📋 |
| 5 | Google News: alta en Publisher Center (edición ES y EN por separado) con logo, secciones y RSS | Alto | Media | 30 min | JM | ⛔ |
| 6 | Alta en Bing Webmaster Tools (importar desde Search Console) | Medio | Media | 10 min | JM | ⛔ |
| 7 | AdSense: mensaje RGPD publicado, sitio aprobado, anuncios automáticos desactivados | Alto (ingresos) | Alta | 20 min | JM | ⛔ |
| 8 | Perfiles de marca (X, Bluesky, Telegram, canal de WhatsApp) y añadirlos a `perfiles` en config/site.yaml (hoy `sameAs` vacío) | Medio | Media | 1 h | JM + Claude | 📋 |
| 9 | Confirmar si el redactor del servidor (RSS + Haiku, commit d095676) está instalado y activo; si publica, que respete GUIA.md igual que los agentes | Medio | Media | 5 min | JM | ⛔ |
| 10 | Páginas de tema "pilares" (Urda/alta velocidad, Irán-Ormuz, dana, inflación) con contexto propio | Medio | Media | Medio | Claude | 📋 |
| 11 | Fuentes WOFF2 generadas en el servidor | Bajo | Baja | Bajo | Claude | 📋 |

## Registro de revisiones

### Revisión 2 · 31/10/2026 21:50
**Cambios desde la revisión 1** (git log): 50 commits; edición en inglés `/en/` con 4 noticias (c014a77), redactor automático en el servidor con la API de Claude (d095676, requiere instalación en el VPS), menú fijo, reglas de rigor (duplicados, datos solo si están en las fuentes), retirada de una noticia duplicada.

**Datos verificados**
- `site:newtimes.news` y "NewTimes.news" (buscador de la herramienta, no Google): ningún resultado propio; dominan Phoenix/Miami New Times. Sin Search Console no hay dato de indexación real.
- Producción (WebFetch con `?c=`): robots.txt con sitemap.xml + sitemap-noticias.xml + /en/sitemap-noticias.xml; sitemap-noticias con 62 URLs de las últimas 48 h, todas `es`; sitemap.xml con 140 URLs (26 de `/en/`, 21 `/tema/`), algunas sin lastmod; ads.txt correcto; portada al día (última noticia 21:11, 43 noticias del día, enlace "English edition").
- Noticias revisadas: Jamenei (ES, Juan de la Torre, 4 fuentes, foto CC BY 4.0) y Blocus (EN, Álvaro Luna, 5 fuentes, foto CC BY 2.0). Firma de agente y nota de IA presentes.
- Volumen (recientes.py 168): 62 noticias en 2 días; internacional 14, España 10, economía 9, deportes 9, sociedad 8, tecnología 4, cultura 4, ciencia-salud 4. En las últimas 12 h, Tecnolog-IA 0.
- Fuentes de las 62 noticias: 210 enlaces; infobae.com 81 (39 %, reproducciones de EFE/Europa Press), unitel.bo 11, yahoo 7, y varios dominios fuera de la lista de GUIA.md (diariosigloxxi, 1027wbow, mdjonline…). Mediana 514 palabras, mínimo 322.
- Tareas: jefe de redacción horario, último turno 31/10 21:06 (Madrid) SUCCEEDED; vigilante 21:12 SUCCEEDED. `build.py --check`: 66 artículos válidos, 0 errores.
- No disponible: Search Console, analítica, PageSpeed/CrUX, estado del redactor del servidor en el VPS.

**Cambios (commit 968090c)** 🛠
- hreflang es/en/x-default en portadas de sección (página 1), equipo y fichas de agente (antes solo en la portada). Las noticias no llevan hreflang porque cada edición escribe las suyas.
- NewsArticle: `author.url` apunta a la ficha del agente (`/equipo/<slug>/`, `/en/team/<slug>/`) en vez de a "Cómo trabajamos".
- sitemap.xml: lastmod en fichas de agente (última noticia firmada) y en la página de equipo.
- Validado con `build.py --check` y construcción local revisando el HTML generado; pendiente de verificar en producción.

**Problemas**
- Dependencia de reproducciones (Infobae, Unitel, Yahoo) como fuente enlazada: resta autoridad y algunos dominios no están en la lista de GUIA.md.
- Desequilibrio de secciones (tecnología, cultura y ciencia infrarrepresentadas).
- Marca invisible en buscadores; sin Search Console no se puede medir.
- Riesgo de duplicados entre el redactor del servidor y la tarea horaria si ambos están activos.

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
- Search Console (ES y EN): impresiones, clics, CTR, posición, cobertura, Discover, Google News.
- Analítica de visitas: ninguna instalada (opción sin cookies: Plausible/Umami en el VPS).
- AdSense: aprobación, RPM, ingresos.
- Core Web Vitals reales (CrUX), cuando haya tráfico; PageSpeed no accesible desde el entorno de revisión.
- Estado del redactor del servidor (systemctl status newtimes-redactor.timer) y su registro.
- Enlaces entrantes (no hay herramienta de backlinks disponible).
