# NewTimes.news: crecimiento y SEO

Documento vivo. Lo actualiza la revisión semanal (y cualquier revisión manual): prioridades, estado de cada acción y datos disponibles.
Leyenda: ✅ hecho y verificado · 🛠 hecho, pendiente de verificar en producción · 📋 preparado/recomendado · ⛔ bloqueado (necesita a JM Triviño)

## Prioridades vigentes (ordenadas por impacto, urgencia y esfuerzo)

| # | Acción | Impacto | Urgencia | Esfuerzo | Responsable | Estado |
|---|---|---|---|---|---|---|
| 1 | Verificar newtimes.news en Google Search Console (registro TXT en Cloudflare) y enviar sitemap.xml, sitemap-noticias.xml y /en/sitemap-noticias.xml. Sin esto no hay ninguna medición real | Muy alto | Inmediata | 15 min | JM | ⛔ |
| 2 | Comprobar que el redactor autónomo del VPS publica: sin commits entre el 09/11 01:36 y 08:50 (Madrid) pese a turnos previstos. `sudo journalctl -u newtimes-redactor -u newtimes-redactor-en --since today -n 40` | Muy alto (frescura) | Inmediata | 5 min | JM | ⛔ |
| 3 | Permitir newtimes.news en WebFetch para las tareas programadas: dos revisiones seguidas sin poder leer producción | Alto (medición) | Alta | 2 min | JM | ⛔ |
| 4 | Google News: alta en Publisher Center (ES y EN por separado) con logo, secciones y RSS | Alto | Alta | 30 min | JM | ⛔ |
| 5 | Reejecutar `instalar.sh` en el VPS (301/410 de URLs antiguas, 301 de los duplicados retirados, CSP para AdSense y YouTube) | Alto | Alta | 5 min | JM | ⛔ |
| 6 | Fuentes: enlazar la nota original. Infobae baja de 37 % a 33 % de los enlaces (76 de 228); no está en `config/fuentes_admitidas.yaml`, así que los encargos del VPS ya no deberían usarlo. Medir en la revisión 5 | Alto (E-E-A-T, Google News) | Alta | Bajo | Claude (jefe de redacción) | 🛠 |
| 7 | Continuidad: 49 noticias el 06/11, 3 el 07/11, 10 el 08/11. El VPS ya sirve de respaldo; confirmar una semana de ritmo estable | Muy alto | Alta | Bajo | Claude + JM | 🛠 |
| 8 | Evaluar la redacción en el VPS tras una semana completa (hoy: menos de 12 h de datos, 1 noticia ES y 3 EN, 0 descartadas). Si es sólida, valorar que el VPS elija temas y retirar al jefe de Claude | Alto (costes) | Media | Bajo | Claude + JM | 📋 |
| 9 | Perfiles de marca (X, Bluesky, Telegram, canal de WhatsApp) y añadirlos a `perfiles` en config/site.yaml (hoy `sameAs` vacío). Textos listos abajo | Medio | Media | 1 h | JM + Claude | 📋 |
| 10 | (Parcial: horario con 5 turnos, filtro de legibilidad y 2 temas por sección) Equilibrar secciones: Cultura 4, Tecnolog-IA 5 y Ciencia y salud 6 noticias/semana frente a 15 de Internacional | Alto | Media | Bajo | Claude (jefe de redacción) | 📋 |
| 11 | Hacer crecer la edición inglesa: 7 noticias en total, 3 esta semana. Debería subir con el temporizador EN | Alto (audiencia global) | Media | Bajo | Claude + JM | 📋 |
| 12 | Alta en Bing Webmaster Tools (importar desde Search Console) | Medio | Media | 10 min | JM | ⛔ |
| 13 | AdSense: mensaje RGPD publicado, sitio aprobado, anuncios automáticos desactivados | Alto (ingresos) | Alta | 20 min | JM | ⛔ |
| 14 | Páginas de tema "pilares" (huelga general 11N, Urda/alta velocidad, Irán-Ormuz, 29N) con contexto propio. De 510 temas, 66 son indexables | Medio | Media | Medio | Claude | 📋 |
| 15 | Duplicados por retiradas tardías: 3 pares más retirados y check reforzado. El check solo detecta casos muy parecidos: el 2.º y el 3.º par no los habría parado. Vigilar que el vigilante no publique si el jefe ya lo hizo | Medio | Media | Bajo | Claude | 🛠 |
| 16 | Titulares largos en España: mediana de 100 caracteres. Regla endurecida el 09/11 a 60-90 caracteres en GUIA.md; medir con `docs/salud-seo.md` | Medio | Media | Bajo | Claude | 🛠 |
| — | Hechos: redactor del servidor activo (primer `[servidor]` el 08/11 23:10 UTC) ✅ · Fuentes WOFF2 🛠 · Relacionadas por tema 🛠 | | | | | |

### Textos para abrir perfiles (JM crea la cuenta; Claude añade la URL a `perfiles`)
- Nombre: NewTimes.news. Usuario: `newtimesnews` (o el más parecido disponible).
- Bio ES: «Periódico digital escrito por agentes de inteligencia artificial, con fuentes enlazadas en cada noticia. Supervisión humana.»
- Bio EN: «Digital newspaper written by AI agents, with sources linked in every story. Human oversight.»
- Enlace: https://newtimes.news (o /en/). Imagen: `/img/logo.svg`. La autoría de IA debe verse en la bio.
- Automatización posible con el RSS (`/rss.xml`, `/en/rss.xml`) cuando existan las cuentas.

## Registro de revisiones

### Revisión 5 · 09/11/2026 22:00 (manual, a petición de JM)
**Datos verificados**
- Producción legible por WebFetch (portada al día: última noticia 18:11 del 09/11; title y description correctos; Open Graph, canonical, robots con max-image-preview y selector de edición). En construcción local: NewsMediaOrganization, WebSite, NewsArticle, BreadcrumbList e hreflang presentes; `sameAs` vacío.
- Ritmo (redaccion/seo_salud.py): ES 15 noticias en 24 h, mayor hueco entre 7 y 23 h de 10,3 h (no hubo publicación entre las 18:11 y las 22:00 pese al turno de las 20:05); EN 11 en 24 h. Secciones ES (7 d): internacional 17, economía 11, España 10, deportes 7, sociedad 7, tecnología 6, ciencia-salud 6, cultura 4.
- Titulares ES: mediana 100 caracteres y 68 de 68 por encima de 70 (EN: mediana 63). Causa probable de títulos cortados en Google.
- Fuentes ES (7 d): infobae.com sigue en cabeza (72 enlaces de 68 noticias), seguido de eldiario.es 17 y aljazeera.com 10; Europa Press solo 9. 10 de 68 noticias con una sola fuente; EN 8 de 11.
- `build.py --check`: 157 artículos válidos, 0 errores.

**Cambios** (commits c7157fe y 723610f) 🛠 pendiente de verificar en producción
- Redacción: jefe a 5 turnos, titulares a 5 al día con filtro de legibilidad, autónomo ES horario a las :20, sobremuestreo de candidatas (detalle en `redaccion/ENCARGOS.md`).
- Secciones: título y descripción propios por sección y edición (antes «Economía | NewTimes.news» y una descripción genérica); las páginas 2+ añaden el número de página a ambos.
- Noticias: `keywords`, `wordCount` e `isAccessibleForFree` en NewsArticle; `article:modified_time` y `article:tag` en Open Graph.
- GUIA.md: titular entre 60 y 90 caracteres (máximo 100).
- `redaccion/seo_salud.py` y `newtimes-salud.timer`: informe diario sin API en `docs/salud-seo.md` (requiere reejecutar `instalar-redactor.sh`).

**Cadencia de gestión decidida**
- Diaria, gratuita (VPS, 23:30): `docs/salud-seo.md`.
- Semanal, Claude (lunes 8:58): revisión completa con prompt ampliado (frescura, Google News, titulares, secciones, oportunidades de tráfico).
- No se añade tarea diaria de Claude: con Search Console parado no habría datos nuevos que justifiquen el gasto de plan.

**Problemas**
- Infobae sigue siendo la fuente enlazada principal (reproducción de EFE/Europa Press): los encargos y el redactor deben enlazar la agencia original.
- Sin Search Console no hay medición real; es el mayor freno para decidir con datos.
- El hueco de la tarde-noche del 09/11 debería cerrarse con el nuevo horario; comprobar en la próxima revisión.

### Revisión 4 · 09/11/2026 09:30
**Cambios desde la revisión 3** (git log, 44 commits en 8 días): la redacción pasa a encargos; instalado el redactor del servidor (primer commit `[servidor]` el 08/11 23:10 UTC, noticia del ANC); titulares y temporizadores en el VPS; jefe de redacción a dos turnos (9:06 y 18:06) con Sonnet; vigilante una vez al día.

**Datos verificados**
- Volumen ES (recientes.py 168): 63 noticias antes de retirar duplicados, 60 después. Por día: 06/11 49, 07/11 3, 08/11 10, 09/11 1. Secciones: internacional 15, economía 10, España 9, deportes 7, sociedad 7, ciencia-salud 6, tecnología 5, cultura 4.
- Edición EN: 7 noticias en total, 3 esta semana (00:35–01:35 del 09/11, ya desde el VPS). Fuentes Guardian, Al Jazeera, BBC; una de ellas con una sola fuente, atribuida en todo el texto.
- Fuentes ES: 228 enlaces; infobae.com 76 (33 %), eldiario.es 19, aljazeera.com 10, pbs.org 5, unitel.bo 4, diariosigloxxi.com 4. Mediana 534 palabras, mínimo 290. Todas con imagen y firma de agente.
- Titulares ES: mediana 101 caracteres, máximo 112, 4 por encima de 110.
- `build.py --check`: 141 artículos válidos, 0 errores (tras los cambios). Encargos: `pendientes/` y `descartados/` vacíos.
- Tareas (list_triggers): jefe y vigilante SUCCEEDED, últimos disparos el 08/11 a las 21:41 y 21:47 UTC. El historial no recoge por qué el 07/11 hubo solo 3 noticias.
- Construcción local: 270 URLs en sitemap.xml (antes de retirar), 14 en sitemap-noticias, 3 en /en/; canonical, og, NewsArticle y BreadcrumbList presentes; 510 temas, 66 indexables.
- Móvil local (Playwright, 390 px, sin AdSense ni red real): sin desbordamiento horizontal, CLS 0, 8-9 peticiones; portada 287 KB sin comprimir.
- `site:newtimes.news` y "NewTimes.news" (buscador de la herramienta, no Google): ningún resultado propio.
- Producción: **no verificada**. WebFetch rechazó robots.txt, sitemaps, ads.txt y portada (permiso no respondido en ejecución desatendida); no se usó otro método. Tampoco se pudo revisar la licencia de las imágenes publicadas: Commons no responde desde el entorno.

**Cambios** ✅ en el repositorio · 🛠 pendiente de verificar en producción
- a6a2f75: retirados 3 duplicados del 06/11 (Bruna, Cumbre Iberoamericana, UCO/Koldo), manteniendo las versiones con fuentes originales; `build.py --check` rechaza titular y entradilla muy parecidos en la misma sección y 24 h (probado: detecta el par de la Cumbre, ninguno de los 141 restantes). 301 preparados en nginx-antiguas.conf (requieren el instalador; mientras, 404).
- 4e41be4: relacionadas por etiquetas poco frecuentes, también entre secciones (revisado el HTML en 3 noticias); fuentes WOFF2 con WOFF de respaldo, 206 → 163 KB (comprobado que el navegador solo descarga las WOFF2); «Cómo trabajamos» y «How we work» explican la verificación automática y que no hay revisión humana previa de cada noticia; GUIA.md pide el hecho principal en los primeros 70 caracteres del titular.

**Problemas**
- Redactor autónomo: sin commits entre 01:36 y 08:50 del 09/11 aunque había turnos ES a las 07:05 y EN a las 04:35, 07:35 y 08:35 (Madrid). Puede ser falta de temas o un fallo: solo se ve en journalctl.
- Sin Search Console ni acceso a producción no hay ninguna medición de resultados.
- Marca invisible en el buscador disponible; `sameAs` vacío.
- Ritmo irregular entre el 06/11 y el 08/11.

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
- Registro del redactor del VPS (`journalctl`): turnos sin publicación y motivo; gasto real de API acumulado.
- Acceso de WebFetch a newtimes.news en las tareas desatendidas, para verificar producción y licencias de imagen.
- Historial de ejecuciones de las tareas programadas (causa de los huecos del 01–06/11 y del 07/11).
- Enlaces entrantes (no hay herramienta de backlinks disponible).
