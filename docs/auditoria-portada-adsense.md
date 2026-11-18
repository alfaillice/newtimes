# Auditoría de portada, retención y AdSense · 18/11/2026

## 1. Fallo de la portada (corregido)

**Causa.** `build.py` elegía el carrusel así: primero todas las noticias marcadas `destacado` de las últimas 48 h (en orden de fecha) y después rellenaba con las demás. Una marcada de hace 40-47 h ganaba siempre a una noticia sin marcar de hace 10 minutos, y si no había nada en 48 h recurría a las 12 últimas sin límite de edad. Con 2-3 noticias nuevas al día en el momento del cierre, el carrusel mostraba el 17/11 en las posiciones 3-5 y la marcada del 16/11 (cumbre Xi-Putin-Trump) podía abrir la portada.

**Corrección** (`elegir_portada` en `build.py`, 6 pruebas en `tests/test_portada.py`):
- Ventana de 24 h; solo se amplía a 36 h si hay menos de 3 noticias. Nada de días anteriores. Si la redacción lleva más de 36 h parada se muestran las 3 últimas antes que una portada vacía.
- Orden por hora de publicación; una noticia `destacado` cuenta como 6 h más reciente. La importante de las últimas horas abre; una «destacada» de hace 20 h no desplaza a la de hace 1 h.
- Máximo 2 por sección y 5 en total (variedad, como pide GUIA.md).
- Sirve a las dos ediciones (ES y EN).

## 2. Qué hace buena a una portada de periódico (y estado en NewTimes)

| Clave | Estado | Acción |
|---|---|---|
| Frescura y jerarquía: lo más importante y reciente arriba | Era el fallo. Corregido | Medir a diario que ninguna noticia de la portada tenga más de 36 h (añadir a `seo_salud.py`) |
| Fecha y hora visibles y relativas («hace 2 h») | Existen (`data-rel`), solo para hoy | Mantener |
| Un solo titular dominante y entradilla útil | Carrusel con 5 diapositivas | El carrusel esconde 4 de 5 noticias (la mayoría no pasa de la primera). Proponer: titular principal + 4 secundarias visibles en rejilla (ver §4) |
| Variedad de secciones | Ahora limitada a 2 por sección | — |
| Servicio y utilidad (tiempo, resultados, plazos) | Parcial (criterios de ENCARGOS.md) | Bloque fijo «Hoy en 1 minuto» con las 5 noticias más leídas/recientes |
| Transparencia editorial (quién, cómo, fuentes, correcciones) | Buena: firma de agente, fuentes, «Cómo trabajamos» | Añadir enlace visible a una política de correcciones y fecha de actualización |
| Confianza: fuentes originales | 0 de 249 enlazan el documento original | Prioridad ya recogida en ENCARGOS.md |

## 3. Comportamiento y diseño: hallazgos

1. **Carrusel con avance automático cada 7 s que nunca se detiene** (salvo teclado/táctil). Incumple WCAG 2.2.2 (pausar contenido en movimiento), mueve el titular que el lector está leyendo y empeora el CTR. Propuesta: sin autoavance, o con botón «Pausar» y parada al pasar el ratón.
2. «Última hora» muestra siempre el último titular, sea o no urgente: devalúa la etiqueta. Propuesta: solo si la noticia tiene menos de 2 h; si no, «Última actualización».
3. La promoción «En directo» (televisión de un tercero) ocupa un bloque a ancho completo entre el carrusel y las noticias, sin contenido propio.
4. «Hoy, hora a hora» solo contiene lo de hoy: a las 00:30 queda casi vacío. Propuesta: ventana móvil de 12 h.
5. Frecuencia: 29 noticias en 24 h ES (objetivo 14). Bien, pero con concentraciones; la portada necesita 3-5 piezas nuevas cada pocas horas.
6. Retención: faltan módulos de «Lo más leído», boletín por correo/RSS visible, «Sigue este tema» (las páginas `/tema/` existen pero no se anuncian desde la portada), notificaciones push y perfil en redes (`perfiles` vacío).
7. Rendimiento: portada de unos 11 KB comprimida, CLS 0, sin desbordamiento en móvil (revisión 4-6). Sin hallazgos.

## 4. AdSense: riesgos reales de rechazo o limitación

Lo que revisan en la práctica es la **calidad del contenido** y la política de **contenido de bajo valor / generado a escala**, más que el diseño.

1. **Contenido de poco valor añadido.** 203 de 249 noticias tienen una sola fuente y son reelaboraciones de Europa Press, BBC, Guardian o El País, escritas por IA a gran ritmo. Es el mayor riesgo («scaled content abuse» y «contenido duplicado/reescrito»). Mitigación: más fuentes por noticia, documento original enlazado, contexto propio (explicadores en los temas pilares), menos piezas pero más sólidas, y piezas de servicio genuinamente útiles.
2. **Anuncios junto a vídeo de un tercero.** La página `/directo/` insertaba un anuncio al lado de una señal de France 24. AdSense exige contenido propio del editor en las páginas con anuncios: **retirado** (`directo: ""` en `config/site.yaml`). Valorar sacar `/directo/` del mapa del sitio o añadirle texto propio.
3. **Páginas de juegos y horóscopo** (`/juegos/`, `/horoscopo/`): contenido generado, sin valor informativo y en conflicto con GUIA.md («no publicamos horóscopos»). Mantenerlas sin anuncios o retirarlas del menú mientras se evalúa el sitio.
4. **Imágenes.** Solo bancos libres: bien. Vigilar fotos de relleno sin relación con el hecho (revisión 6, punto 10), que parecen contenido engañoso.
5. **Requisitos formales: cumplidos.** `ads.txt` correcto, aviso legal, privacidad, cookies con CMP de Google (RGPD), contacto, «Cómo trabajamos», titular identificado. Pendiente en el panel: aprobación del sitio y mensaje RGPD (JM).
6. **Densidad de anuncios.** Portada: 2 bloques (tras «Lo último» y cada 3 secciones); noticia: 2; sección: 1. Razonable, siempre claramente etiquetados «Publicidad». No añadir más hasta tener aprobación y datos.
7. **Todos los huecos usan el mismo `data-ad-slot`.** No impide la aprobación; conviene crear uno por ubicación para medir RPM.
8. **Tráfico y antigüedad.** Sin Search Console ni analítica no hay datos. Google suele tardar semanas en aprobar sitios nuevos con poco tráfico orgánico.

## 5. Plan propuesto

| Prioridad | Acción | Quién |
|---|---|---|
| Hecha | Portada solo con actualidad y pruebas | Claude |
| Hecha | Sin anuncio en `/directo/` | Claude |
| Alta | Verificar Search Console, solicitar Google News, aprobar AdSense | JM |
| Alta | Más fuentes por noticia y documento original (encargos y redactor) | Claude |
| Hecha (18/11) | Carrusel con botón de pausa y parada con el ratón; «Última hora» solo si <2 h; «Hora a hora» con ventana de 12 h | Claude |
| Media | Rejilla de 4 secundarias visibles y bloque «Sigue este tema» | Claude |
| Media | Medición de frescura de portada en `seo_salud.py` | Claude |
| Media | Boletín/RSS visible, perfiles sociales | JM + Claude |
