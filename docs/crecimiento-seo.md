# NewTimes.news: crecimiento y SEO

Documento vivo. Lo actualiza la revisión semanal (y cualquier revisión manual): prioridades, estado de cada acción y datos disponibles.
Leyenda: ✅ hecho y verificado · 🛠 hecho, pendiente de verificar en producción · 📋 preparado/recomendado · ⛔ bloqueado (necesita a JM Triviño)

## Prioridades vigentes (ordenadas por impacto, urgencia y esfuerzo)

| # | Acción | Impacto | Urgencia | Esfuerzo | Responsable | Estado |
|---|---|---|---|---|---|---|
| 1 | Continuidad de la redacción: hueco de casi 5 días sin publicar (01/11 09:13 → 06/11 07:32). Averiguar la causa (¿tareas suspendidas, límite de uso?) y dejar un respaldo que no dependa de las tareas en la nube (redactor del servidor) | Muy alto (frescura, Google News, Discover) | Inmediata | 15 min | JM | ⛔ |
| 2 | Verificar newtimes.news en Google Search Console (registro TXT en Cloudflare) y enviar sitemap.xml, sitemap-noticias.xml y /en/sitemap-noticias.xml | Muy alto | Alta | 15 min | JM | ⛔ |
| 3 | Reejecutar el instalador en el VPS (activa 301/410 de URLs antiguas, CSP para AdSense y YouTube) | Alto | Alta | 5 min | JM | ⛔ |
| 4 | Fuentes: enlazar la nota original de la agencia u organismo en vez de reproducciones (Infobae = 37 % de las fuentes de la semana). Aviso automático en `build.py --check` desde 92fcd44; falta que el jefe de redacción lo aplique | Alto (E-E-A-T, Google News) | Alta | Bajo | Claude (jefe de redacción) | 🛠 |
| 5 | Evitar duplicados cuando vigilante y jefe de redacción coinciden (06/11: retirada pieza Koldo, ccdc5ca) | Medio | Media | Bajo | Claude + JM (decidir) | 📋 |
| 6 | Equilibrar secciones: Tecnolog-IA, Cultura y Ciencia y salud con 5 noticias/semana frente a 17 de Internacional | Alto | Media | Bajo | Claude (jefe de redacción) | 📋 |
| 7 | Google News: alta en Publisher Center (edición ES y EN por separado) con logo, secciones y RSS | Alto | Media | 30 min | JM | ⛔ |
| 8 | Alta en Bing Webmaster Tools (importar desde Search Console) | Medio | Media | 10 min | JM | ⛔ |
| 9 | AdSense: mensaje RGPD publicado, sitio aprobado, anuncios automáticos desactivados | Alto (ingresos) | Alta | 20 min | JM | ⛔ |
| 10 | Perfiles de marca (X, Bluesky, Telegram, canal de WhatsApp) y añadirlos a `perfiles` en config/site.yaml (hoy `sameAs` vacío) | Medio | Media | 1 h | JM + Claude | 📋 |
| 11 | Redactor del servidor (d095676): ningún commit `[servidor]` en todo el historial, luego no está instalado o no publica | Medio | Media | 5 min | JM | ⛔ |
| 12 | Permitir newtimes.news en WebFetch para las tareas programadas (esta revisión no pudo leer producción) | Medio (medición) | Media | 2 min | JM | ⛔ |
| 13 | Páginas de tema "pilares" (Urda/alta velocidad, Irán-Ormuz, dana, inflación) con contexto propio | Medio | Media | Medio | Claude | 📋 |
| 14 | Fuentes WOFF2 generadas en el servidor | Bajo | Baja | Bajo | Claude | 📋 |
| 15 | Evaluar la redacción en el VPS tras una semana: noticias publicadas y descartadas (`redaccion/encargos/descartados/`), errores corregidos por el vigilante, gasto de API. Si es sólida, valorar que el VPS también elija los temas y retirar al jefe de Claude | Alto (costes) | Media | Bajo | Claude + JM (Sonnet para el jefe) | 📋 |

## Registro de revisiones

### Revisión 3 · 06/11/2026 07:40
**Cambios desde la revisión 2** (git log): ~20 commits de redacción el 31/10–01/11, botones de compartir (Threads, Instagram, TikTok), carrusel de portada; **ningún commit entre el 01/11 09:13 y el 06/11 07:30 (hora de Madrid)**. Hoy, a las 07:32, el vigilante hizo una edición de recuperación (840000d, 4 noticias) y a la vez el jefe de redacción publicó 4 (7d6effb); una pieza duplicada del caso Koldo se retiró (ccdc5ca).

**Datos verificados**
- Hueco de publicación: 4 días y 22 h sin noticias (git log). En ese tiempo sitemap-noticias.xml quedó vacío (la construcción local sin noticias de 48 h genera `<urlset>` vacío) y la portada se quedó en el 01/11.
- Tareas (list_triggers): jefe de redacción, vigilante y esta revisión se dispararon todas a las 06:22 del 06/11 y figuran actualizadas a esa hora; la de TikTok terminó el 05/11 en 3 segundos. No hay registro de las ejecuciones intermedias, así que la causa del hueco no se puede demostrar desde aquí.
- `site:newtimes.news` y "NewTimes.news" (buscador de la herramienta, no Google): ningún resultado propio; dominan Phoenix/Miami New Times y New Times (Ruanda).
- Producción: **no verificada**. WebFetch rechazó todas las URLs de newtimes.news (permiso no concedido en una ejecución desatendida); no se usó otro método.
- Volumen (recientes.py 168, antes de la recuperación): 74 noticias; internacional 17, deportes 12, España 11, economía 10, sociedad 9, tecnología 5, cultura 5, ciencia-salud 5. Por día: 30/10 19, 31/10 46, 01/11 9, 02–05/11 0.
- Fuentes de esas 74 noticias: 255 enlaces; infobae.com 96 (37 %), eldiario.es 12, unitel.bo 12, aljazeera.com 9, yahoo 9, diariosigloxxi.com 4. Mediana 511 palabras, mínimo 233. Todas con imagen y firma de agente (el check exige agente correcto por sección).
- `build.py --check`: 85 artículos válidos, 0 errores (tras la recuperación). Construcción local: canonical, og, NewsArticle con datePublished/dateModified y RSS presentes.

**Cambios (commit 92fcd44)** ✅ en el repositorio
- `build.py --check` avisa, sin bloquear, cuando una noticia de las últimas 6 h enlaza una reproducción (infobae.com, yahoo.com, msn.com, unitel.bo, diariosigloxxi.com) y remite al apartado 2 de GUIA.md. Probado con una noticia de prueba con fecha actual (dos avisos, 0 errores) y retirada antes del commit.

**Problemas**
- Hueco de casi 5 días: el problema más grave del periodo; para Google News la regularidad pesa más que cualquier ajuste técnico.
- Vigilante y jefe de redacción pueden publicar a la vez (duplicado de hoy).
- Infobae sigue siendo la fuente principal; el redactor del servidor no está activo.
- Sin acceso a producción ni a Search Console, no hay medición.

### Revisión 2 · 31/10/2026 21:40
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
- Estado del redactor del servidor (systemctl status newtimes-redactor.timer) y su registro: sin commits `[servidor]`.
- Historial de ejecuciones de las tareas programadas entre el 01/11 y el 06/11 (causa del hueco).
- Acceso de WebFetch a newtimes.news en las tareas desatendidas (para verificar producción).
- Enlaces entrantes (no hay herramienta de backlinks disponible).
