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
tema: Una o dos frases con el hecho concreto que debe contar la noticia.
destacado: false
fuentes:
  - medio: Europa Press
    titulo: Titular de la pieza
    url: https://www.europapress.es/economia/...
  - medio: INE
    titulo: Nota de prensa
    url: https://www.ine.es/...
```

- Entre 1 y 4 fuentes, con su URL `https` exacta y dominio en `config/fuentes_admitidas.yaml`. Deben ser páginas abiertas: el agente solo sabe lo que hay en ellas.
- Hace falta una agencia o fuente oficial, o dos medios distintos. Con un solo medio, la noticia atribuye los datos a ese medio.
- `destacado: true` en una como mucho.
- El `tema` solo orienta: no incluyas datos que no estén en las fuentes, porque el verificador descartará la noticia.

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
