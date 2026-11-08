# Encargos: el jefe de redacción elige, los agentes del servidor escriben

El jefe de redacción (Claude) elige los temas y deja un archivo por noticia en `redaccion/encargos/pendientes/`. En el servidor, `newtimes-encargos.timer` mira cada 5 minutos: si hay encargos, `redactor.py --encargos` descarga las fuentes, escribe con el agente de la sección (Haiku, por API), contrasta y publica. Si no hay encargos no llama a la API.

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

## Qué comprueba el servidor antes de publicar

1. Que las fuentes estén admitidas y tengan texto suficiente.
2. Que todas las cifras de dos o más dígitos estén en las fuentes (solo en la edición española).
3. Una segunda lectura del modelo contra las fuentes: cifras, fechas, nombres, cargos, citas y atribuciones.
4. `build.py --check`.

Si algo falla, no se publica y el encargo pasa a `redaccion/encargos/descartados/` con su `motivo`. Si falla la API, se reintenta hasta 3 veces.

## Puesta en marcha

1. En el VPS: `sudo bash /srv/newtimes/repo/deploy/instalar-redactor.sh`, tras actualizar el repositorio.
2. Probar sin publicar (escribe el archivo, pero no hace commit; bórralo después): dejar un encargo y ejecutar, como indica el instalador, `redactor.py --encargos --prueba`.
3. Cuando funcione, cambiar las instrucciones de las tareas programadas con los textos de abajo. Hasta entonces, el jefe de Claude sigue publicando con sus agentes.

## Instrucciones para el cambio

**Jefe de redacción**, en lugar de los pasos 3 a 5:

> 3. Elige hasta 4 temas nuevos de actualidad, como máximo 2 por sección, solo si hay hechos que lo justifiquen; ejecuta antes `python3 redaccion/recientes.py 48` y da prioridad a las secciones sin cobertura.
> 4. No uses agentes ni escribas noticias. Lee `redaccion/ENCARGOS.md`, busca para cada tema 2-3 fuentes abiertas de `config/fuentes_admitidas.yaml`, con una agencia o fuente oficial siempre que exista, y deja un encargo por noticia en `redaccion/encargos/pendientes/`.
> 5. Haz commit "Encargos AAAA-MM-DD HH:00: N temas" (hora de Madrid) y `git push` a main. Si falla por cambios remotos, `git pull --rebase` y reintenta una vez.

**Vigilante**, añadir en el paso 2:

> e) Encargos en `redaccion/encargos/pendientes/` con más de 30 minutos y los descartados del último día, con su motivo. Si hay pendientes atascados, el redactor del servidor no está funcionando: dilo para que JM Triviño revise `sudo journalctl -u newtimes-encargos -n 30`.

Al activarlo, actualizar también los apartados 1 y 6 de `GUIA.md` y `TAREA.md`, y las páginas «Cómo trabajamos» y «How we work», porque los agentes dejarán de investigar por su cuenta.
