# Encargos: el jefe de redacción elige, los agentes del servidor escriben

El jefe de redacción (Claude) elige los temas y deja un archivo por noticia en `redaccion/encargos/pendientes/`. En el servidor, `newtimes-encargos.timer` mira cada 5 minutos: si hay encargos, `redactor.py --encargos` descarga las fuentes, escribe con el agente de la sección (Haiku, por API), contrasta y publica. Si no hay encargos no llama a la API.

## Titulares

A las 8:50, 11:50, 14:50, 17:50 y 20:50 (Madrid), `newtimes-titulares.timer` guarda en `redaccion/encargos/titulares.yaml` los titulares recientes de los RSS, con sección, medio, título, enlace y resumen. No usa la API. Antes de guardarlos descarga cada página y **descarta las que el servidor no puede leer** (muro de pago, bloqueo): todo lo que figura en la lista es utilizable como fuente. Así el jefe elige sobre fuentes que el servidor puede leer.

## Horario diario (Madrid)

| Hora | Quién | Qué |
|---|---|---|
| 8:50, 11:50, 14:50, 17:50, 20:50 | Servidor | Titulares legibles, sin API |
| 9:06, 12:06, 15:06, 18:06, 21:06 | Jefe de redacción (Claude) | Deja hasta 4 encargos; el servidor los publica hacia las :15 |
| Cada 5 min | Servidor | Escribe y publica los encargos pendientes |
| :20 de cada hora, 7-23 h, y 0, 3 y 6 h | Servidor | Redactor autónomo ES: elige entre RSS legibles y publica hasta 2 |
| :35 de cada hora, 7-23 h, y 0, 3 y 6 h | Servidor | Redactor autónomo EN |

El autónomo sale a las :20 para encontrar ya publicados los encargos del jefe y no repetir temas. Pide dos temas de más para compensar los que descarte la verificación, de modo que un turno no se pierde por un solo descarte.

## Formato

Archivo `redaccion/encargos/pendientes/AAAAMMDD-HHMM-slug.yaml`:

```yaml
seccion: economia
tema: "Una o dos frases con el hecho concreto que debe contar la noticia."
destacado: false
fuentes:
  - medio: Europa Press
    titulo: "Titular de la pieza"
    url: https://www.europapress.es/economia/...
  - medio: INE
    titulo: Nota de prensa
    url: https://www.ine.es/...
```

- Entre 1 y 4 fuentes, con su URL `https` exacta y dominio en `config/fuentes_admitidas.yaml`. Deben ser páginas abiertas: el agente solo sabe lo que hay en ellas.
- **Siempre dos dominios distintos** de `config/fuentes_admitidas.yaml` que cuenten el mismo hecho (una agencia y un medio, dos medios, o una agencia y el documento oficial; `cincodias.elpais.com` y `elpais.com` cuentan como uno). Desde el 22/11 el servidor descarta el encargo si, tras buscar en los titulares, no reúne dos (en la semana del 16 al 22/11, 4 descartes por este motivo), y una noticia con un solo medio no se indexa. Busca la segunda pieza en `titulares.yaml` o, si falta, en la web; si no existe, elige otro tema.
- Las noticias no nombran medios en el texto (las fuentes van al final): no pidas en `tema` que se atribuya algo a un medio.
- `destacado: true` en una como mucho.
- Pon `tema` y `titulo` siempre **entre comillas dobles** (y escapa con `\"` las comillas interiores): un «: » sin comillas rompe el YAML. Antes del commit, comprueba los archivos con `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" redaccion/encargos/pendientes/*.yaml`.
- El `tema` solo orienta: no incluyas datos que no estén en las fuentes, porque el verificador descartará la noticia.

## Criterios de crecimiento (revisión SEO 6, 16/11/2026)

Al elegir entre temas de igual interés, el jefe de redacción prefiere, por este orden:

1. **Fuente original.** Si la pieza de agencia se basa en un documento oficial o científico abierto (nota del INE, BOE, Banco de España, AEMET, DGT, estudio en una revista), ponlo también en `fuentes`. Del 16 al 22/11 solo 1 de 157 noticias ES y 2 de 97 EN lo enlazaban; además cuenta como segunda fuente.
2. **Secciones flojas**: Tecnolog-IA (13 noticias ES en 7 días, frente a 28 de Deportes) y, en la edición inglesa, Spain (5 frente a 29 de World): un tema de tecnología por turno si `titulares.yaml` trae alguno con hechos nuevos. (Datos de la revisión SEO 7, 23/11.)
3. **Temas de servicio que la gente busca**, siempre con hechos de fuentes admitidas y sin especular: avisos naranja o rojo de la AEMET (zonas, horas), huelgas con fechas y servicios mínimos, operaciones especiales de tráfico de la DGT, plazos y calendarios oficiales (campaña de la renta, festivos, cambio de hora), resultados de los grandes partidos con datos del encuentro. El titular dice qué, dónde y cuándo.
4. **Seguimiento de los grandes asuntos** (elecciones generales del 29N, huelga educativa de Madrid, COP31, vivienda, Ucrania, inteligencia artificial): cuando haya un hecho nuevo, nombra el asunto en el campo `tema` con esas mismas palabras para que el agente use la etiqueta existente y la cobertura quede enlazada. Las páginas `/tema/` ya no se indexan (22/11); el valor está en noticias completas y con dos fuentes.

## Encargo mensual de Cultura: lanzamientos musicales

Una vez al mes, una tarea programada de Claude deja este encargo (sin fuentes: las busca el servidor):

```yaml
tipo: lanzamiento-youtube
```

El servidor lee el RSS público de los canales oficiales de `config/lanzamientos.yaml` (Nyomi Jet y Pressente), descarta los *shorts*, los vídeos de más de 60 días y los que ya tienen noticia (campo `video:`), y elige el más reciente. Jesús Lozano escribe una pieza breve con el título, la fecha y la descripción del artista, sin valorar la obra; pasa la misma verificación que el resto. La noticia lleva `video: <id>`, que inserta el reproductor en lugar de la foto, y como imagen un fotograma del propio vídeo (`licencia: video-oficial`, solo de `i.ytimg.com` y solo del vídeo indicado). Si no hay lanzamiento nuevo, el encargo pasa a descartados con ese motivo.

## Qué comprueba el servidor antes de publicar

1. Que las fuentes estén admitidas y tengan texto suficiente.
2. Que todas las cifras de dos o más dígitos estén en las fuentes (solo en la edición española).
3. Una segunda lectura del modelo contra las fuentes: cifras, fechas, nombres, cargos, citas y atribuciones.
4. `build.py --check`.

Si algo falla, no se publica y el encargo pasa a `redaccion/encargos/descartados/` con su `motivo`. Si falla la API, se reintenta hasta 3 veces.

## Puesta en marcha

1. En el VPS: `sudo bash /srv/newtimes/repo/deploy/instalar-redactor.sh`, tras actualizar el repositorio.
2. Probar sin publicar (escribe el archivo, pero no hace commit; bórralo después): dejar un encargo y ejecutar, como indica el instalador, `redactor.py --encargos --prueba`.
3. Activo desde el 09/11/2026: las tareas programadas de Claude ya usan este sistema (los textos de abajo).

## Instrucciones para el cambio

**Jefe de redacción**, en lugar de los pasos 3 a 5:

> 3. Elige hasta 4 temas nuevos de actualidad, como máximo 2 por sección, solo si hay hechos que lo justifiquen; ejecuta antes `python3 redaccion/recientes.py 48` y da prioridad a las secciones sin cobertura.
> 4. No uses agentes ni escribas noticias. Lee `redaccion/ENCARGOS.md` y `redaccion/encargos/titulares.yaml`, que el servidor actualiza diez minutos antes de cada turno. Elige los temas de esa lista y usa sus enlaces como fuentes, con una agencia siempre que exista; solo busca en la web si hace falta una fuente más de `config/fuentes_admitidas.yaml`. Deja un encargo por noticia en `redaccion/encargos/pendientes/`.
> 5. Haz commit "Encargos AAAA-MM-DD HH:00: N temas" (hora de Madrid) y `git push` a main. Si falla por cambios remotos, `git pull --rebase` y reintenta una vez.

**Vigilante**, añadir en el paso 2:

> e) Encargos en `redaccion/encargos/pendientes/` con más de 30 minutos y los descartados del último día, con su motivo. Si hay pendientes atascados, el redactor del servidor no está funcionando: dilo para que JM Triviño revise `sudo journalctl -u newtimes-encargos -n 30`.

Al activarlo, actualizar también los apartados 1 y 6 de `GUIA.md` y `TAREA.md`, y las páginas «Cómo trabajamos» y «How we work», porque los agentes dejarán de investigar por su cuenta.
