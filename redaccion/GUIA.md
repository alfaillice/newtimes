# Guía editorial de NewTimes.news (edición España)

Esta guía la siguen los agentes que redactan cada hora. Si algo no está aquí, manda el sentido común periodístico: exactitud, atribución y servicio al lector.

## 1. Qué publicamos

Actualidad de interés general para lectores en España: política nacional, internacional, economía, sociedad, ciencia y salud, tecnología, cultura y deportes.

Cada hora se publican **entre 2 y 4 noticias**, solo si hay hechos nuevos que lo justifiquen. Mejor una noticia sólida que cuatro flojas. Si en esa hora no hay nada nuevo y relevante, no se publica nada.

### Criterios para elegir
1. Hechos nuevos de las últimas horas, confirmados por al menos una fuente de la lista.
2. Impacto en mucha gente o relevancia pública clara.
3. Que no lo hayamos publicado ya. Comprueba siempre `python3 redaccion/recientes.py` antes de elegir. Si un asunto ya publicado tiene novedades importantes, escribe una pieza nueva con el desarrollo (no edites la anterior salvo para corregir errores).
4. Variedad: no más de 2 piezas de la misma sección por hora.

### Lo que no se publica nunca
- Rumores, filtraciones sin confirmar, contenido viral sin verificar.
- Ofertas, productos, sorteos, contenido patrocinado o de afiliación.
- Opinión propia, editoriales o juicios de valor. Las opiniones solo aparecen atribuidas a quien las expresa.
- Horóscopos, consejos de salud sin respaldo científico, "según la psicología…".
- Información sobre personas privadas que no sea de interés público. Nada de víctimas identificadas sin que lo hayan hecho públicamente autoridades o familias.
- Contenido de sucesos con detalles morbosos.

## 2. Fuentes verificadas

Solo estas fuentes sirven de base. Las agencias y fuentes oficiales tienen prioridad.

**Agencias:** EFE (efe.com), Europa Press (europapress.es), Reuters, AFP, AP.

**Oficiales España:** BOE, La Moncloa (lamoncloa.gob.es), ministerios, Congreso, Senado, CGPJ/Poder Judicial, INE, Banco de España, CNMV, AEMET, DGT, Ministerio de Sanidad, comunidades autónomas.

**Oficiales internacionales:** Comisión Europea, Parlamento Europeo, BCE, Eurostat, ONU y agencias (OMS, ACNUR…), OTAN, FMI, OCDE.

**Medios de referencia (España):** RTVE, El País, El Mundo, La Vanguardia, ABC, elDiario.es, El Confidencial, Cadena SER, Cope, 20minutos, El Periódico, La Razón, Expansión, Cinco Días, El Economista, Marca y AS (deportes), Agencia SINC (ciencia).

**Medios de referencia (internacional):** BBC, The Guardian, Financial Times, The New York Times, The Washington Post, Le Monde, AP News, Al Jazeera (atribuyendo).

**Ciencia:** revistas con revisión por pares (Nature, Science, The Lancet, NEJM, PNAS…) y notas de prensa de universidades y del CSIC.

Reglas:
- Un dato importante (cifras, muertos, acusaciones, decisiones) debe estar en una agencia, una fuente oficial o **dos medios** de la lista. Si solo lo publica un medio, se atribuye expresamente: «según publica El País».
- Cita entre 1 y 4 fuentes por noticia, siempre con su URL exacta.
- Si las fuentes discrepan, se cuenta la discrepancia.

## 3. Cómo se escribe

- **Texto propio.** Nunca copies ni traduzcas párrafos de otros medios. Lee las fuentes, entiende los hechos y escríbelos con tu estructura y tus palabras. Nada de reproducir el orden de párrafos de la fuente.
- **Citas literales:** solo declaraciones de protagonistas, cortas (menos de 25 palabras), entre comillas españolas o inglesas, atribuidas a quien las dijo. Como máximo dos por noticia. Nunca inventes ni retoques una cita.
- **Extensión:** cuerpo de 250 a 600 palabras (mínimo técnico: 120).
- **Estructura:** primer párrafo con lo esencial (qué, quién, cuándo, dónde); después contexto, reacciones atribuidas y qué pasará ahora. Ladillos (`## Subtítulo`) solo si pasa de 450 palabras.
- **Titular:** informativo, en presente o pasado, sin clickbait, sin preguntas, sin "esto es lo que", sin mayúsculas innecesarias. Máximo ~110 caracteres.
- **Entradilla:** una o dos frases que añadan información al titular (no lo repitan). Máximo ~250 caracteres.
- **Estilo:** español de España, norma RAE y recomendaciones de FundéuRAE. Cifras con punto de millar (1.250), decimales con coma (4,9 %). Horas en formato 24 h con referencia («a las 18.00, hora peninsular»).
- **Neutralidad:** verbos de atribución neutros (dijo, afirmó, explicó). Evita «denunció», «reconoció», «admitió» salvo que sea literal. Da voz a las partes implicadas cuando la fuente la recoja.
- **Fechas relativas:** escribe «este jueves», «el pasado martes», no «ayer» u «hoy», porque la noticia se lee después.

## 4. Formato del archivo

Ruta: `content/es/AAAA/MM/DD/slug.md`, con la fecha de publicación (hora de Madrid). El slug es el titular resumido en minúsculas, sin tildes, con guiones, máximo 8 palabras: `bce-mantiene-tipos-octubre`.

```markdown
---
titulo: El BCE mantiene los tipos de interés en el 2 % por cuarta reunión consecutiva
entradilla: Lagarde avisa de que la inflación de servicios sigue alta y deja abierta una bajada en diciembre si los datos acompañan.
seccion: economia
agente: alberto-rodrigo
fecha: 2026-10-30T15:05:00+01:00
lugar: Fráncfort
destacado: false
etiquetas: [BCE, tipos de interés, inflación]
imagen:
  buscar: "European Central Bank headquarters Frankfurt"
  alt: "Sede del Banco Central Europeo en Fráncfort"
  pie: "Imagen de archivo de la sede del BCE en Fráncfort."
fuentes:
  - medio: Banco Central Europeo
    titulo: Decisiones de política monetaria
    url: https://www.ecb.europa.eu/...
  - medio: EFE
    titulo: El BCE mantiene los tipos...
    url: https://efe.com/...
---

Texto de la noticia en Markdown...
```

Secciones válidas: `espana`, `internacional`, `economia`, `sociedad`, `ciencia-salud`, `tecnologia`, `cultura`, `deportes`.

- `fecha`: la hora real de publicación, con zona horaria (+01:00 en invierno, +02:00 en verano).
- `destacado: true` solo para la noticia más importante de la hora, y solo si de verdad lo es. Va al carrusel de portada.
- `lugar`: ciudad desde la que se informa (opcional).
- `imagen`: **obligatoria**. Ver el apartado 5.

## 5. Imágenes

Cada noticia lleva una imagen. **Nunca** se usan fotos de los medios de comunicación ni de agencias (EFE, Europa Press, Reuters, Getty…): tienen derechos de autor. El generador rechaza cualquier imagen que no venga de un banco con licencia libre.

**Forma preferida: Wikimedia Commons.** No hace falta descargar nada ni averiguar la licencia: el servidor consulta Commons, comprueba que la licencia es libre (CC0, CC BY, CC BY-SA o dominio público) y pone el autor y la licencia reales.

```yaml
imagen:
  buscar: "Knesset building Jerusalem"     # búsqueda en Commons (mejor en inglés, 2-5 palabras)
  alt: "Edificio de la Knéset en Jerusalén"   # qué se ve en la foto
  pie: "Imagen de archivo de la sede de la Knéset en Jerusalén."
```

Si conoces el archivo exacto de Commons (por ejemplo, la foto principal de un artículo de Wikipedia), mejor indícalo en lugar de `buscar`:

```yaml
imagen:
  commons: "File:Nombre exacto del archivo.jpg"
  alt: "..."
  pie: "..."
```

Qué foto elegir, por orden de preferencia:
1. La persona protagonista (retrato oficial o de acto público), si la noticia gira en torno a ella.
2. El lugar o la institución: el edificio del organismo, la ciudad, la infraestructura (una estación, un puerto, un estadio).
3. Un objeto o escena genérica que represente el tema (billetes de euro, un tren AVE, un hospital, monedas de bitcoin, un bosque quemado).

Reglas del pie de foto:
- Si la imagen no es del hecho que se cuenta (casi siempre), el pie empieza por **«Imagen de archivo»**. Nunca insinúes que una foto genérica es del suceso.
- Nada de imágenes de víctimas, heridos, cadáveres ni menores.
- `alt` describe lo que se ve, para lectores con discapacidad visual.

Otras procedencias permitidas (solo si Commons no sirve): Pexels, Unsplash, fotos oficiales de La Moncloa, de la Comisión Europea o del Parlamento Europeo, NASA y ESA. En ese caso se indica todo a mano:

```yaml
imagen:
  url: "https://images.pexels.com/photos/..."    # enlace directo al archivo de imagen
  autor: "Nombre del fotógrafo / Pexels"
  licencia: pexels        # cc0, cc-by, cc-by-sa, dominio-publico, pexels, unsplash, uso-oficial
  fuente: "https://www.pexels.com/photo/..."     # página donde figura la licencia
  alt: "..."
  pie: "Imagen de archivo de ..."
```

## 6. Agentes de la redacción

Cada sección tiene su agente redactor, definido en `config/agentes.yaml` (y en `.claude/agents/`). **Cada noticia la investiga, la escribe y la firma el agente de su sección**, con su estilo (`estilo`) y priorizando sus fuentes de referencia (`fuentes`). Las reglas de esta guía están siempre por encima del estilo de cada agente.

La firma es obligatoria en los metadatos: `agente: <slug>`. El generador rechaza una noticia sin firma o firmada por el agente de otra sección. Si una noticia toca dos secciones, se elige la principal y la firma su agente.

## 7. Antes de publicar

1. `python3 build.py --check` debe terminar sin errores.
2. Relee: ¿cada dato está en alguna fuente citada? ¿hay alguna frase copiada de una fuente? ¿el titular dice lo que el texto cuenta?
3. Un commit por hora: `Redacción AAAA-MM-DD HH:00: N noticias`.

## 8. Correcciones

Si detectas un error en una noticia ya publicada, corrígelo en su archivo, añade `actualizado:` con la hora y, al final del texto, una línea: `*Corrección: en una versión anterior se decía X; lo correcto es Y.*`
