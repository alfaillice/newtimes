#!/usr/bin/env python3
"""Redactor automático de NewTimes.news que corre en el propio servidor.

Sustituye a la tarea programada de Claude (que gasta el plan Pro) por llamadas
directas y baratas a la API de Anthropic (por defecto, Claude Haiku):

  1. Lee los RSS de config/fuentes_rss.yaml (gratis, sin IA).
  2. Pide al modelo que elija 2-3 temas nuevos que no estén en las últimas 48 h.
  3. Descarga el texto de las piezas de origen y pide al agente de cada sección
     (config/agentes.yaml) que escriba la noticia siguiendo redaccion/GUIA.md.
  4. Comprueba las fuentes (config/fuentes_admitidas.yaml), contrasta cifras y
     datos con ellas, valida con build.py --check, hace commit y push a GitHub.
     El servidor la publica en el siguiente ciclo de actualizar.sh (5 min).

Con --encargos no elige temas: escribe los que el jefe de redacción deja en
redaccion/encargos/pendientes/ (ver redaccion/ENCARGOS.md). Si no hay encargos
no llama a la API.

Variables de entorno (en /etc/newtimes/redactor.env):
  ANTHROPIC_API_KEY   clave de la API (obligatoria)
  NEWTIMES_MODELO     modelo (por defecto claude-haiku-5-5)
  NEWTIMES_MAX        noticias máximas por ejecución (por defecto 3)
  NEWTIMES_MAX_ENCARGOS  encargos máximos por ejecución (por defecto 6)

Uso:  python3 redaccion/servidor/redactor.py [--prueba] [--max N] [--edicion es|en] [--encargos] [--titulares] [--salud-api]
      --salud-api  llamada mínima a la API; si falla, lo deja en docs/estado-api.md (alerta en GitHub)
      --prueba   escribe los archivos pero no hace commit ni push
      --edicion  es (por defecto; RSS de config/fuentes_rss.yaml, guía GUIA.md) o
                 en (RSS de config/fuentes_rss_en.yaml, guía GUIDE.md, escribe en content/en/)
"""
import argparse
import concurrent.futures
import email.utils
import functools
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Europe/Madrid")
UA = {"User-Agent": "NewTimesBot/1.0 (+https://newtimes.news/como-trabajamos/)"}
API = "https://api.anthropic.com/v1/messages"
GASTO = {"entrada": 0, "salida": 0}
EDICION = "es"   # la cambia main() con --edicion
FEEDS = {"es": "config/fuentes_rss.yaml", "en": "config/fuentes_rss_en.yaml"}
GUIAS = {"es": "redaccion/GUIA.md", "en": "redaccion/GUIDE.md"}
PENDIENTES = RAIZ / "redaccion/encargos/pendientes"
DESCARTADOS = RAIZ / "redaccion/encargos/descartados"
MAX_INTENTOS = 3
# Una noticia necesita este número de medios distintos y admitidos (ES y EN). Si el tema trae menos,
# el redactor busca la segunda pieza del mismo hecho entre los titulares leídos; si no la encuentra,
# descarta ese tema y pasa al siguiente. Así no se para la publicación.
FUENTES_MINIMAS = int(os.environ.get("NEWTIMES_FUENTES_MIN", 2))
MAX_CANDIDATAS = 4   # piezas de otros medios que se prueban para completar un tema
VENTANA_FUENTES_H = 24   # horas de titulares en los que buscar la segunda fuente de un hecho
MOTIVO = ""   # por qué se descartó la última noticia


class Reintentar(Exception):
    """Fallo pasajero de la API: el encargo se puede volver a intentar."""
    permanente = False


class ErrorAPI(Reintentar):
    """La API rechaza la petición (clave, saldo, modelo o petición no válida): reintentar no sirve."""
    permanente = True


def _detalle_http(e: urllib.error.HTTPError) -> str:
    """Mensaje de error de la API (p. ej. «credit balance is too low»), no solo «Bad Request»."""
    try:
        cuerpo = e.read().decode("utf-8", "replace")
        err = json.loads(cuerpo).get("error", {})
        return f"HTTP {e.code} {err.get('type', '')}: {err.get('message', '')}".strip()
    except Exception:  # noqa: BLE001
        return f"HTTP {e.code}: {e.reason}"


def log(*a):
    print(datetime.now(TZ).strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ red

def descargar(url: str, limite: int = 2_000_000) -> bytes:
    pet = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(pet, timeout=25) as r:
        return r.read(limite)


def claude(sistema: str, usuario: str, max_tokens: int = 8000) -> str:
    # Haiku 5.5 razona por defecto y ese razonamiento consume max_tokens: hay que dejar margen.
    cuerpo = json.dumps({
        "model": os.environ.get("NEWTIMES_MODELO", "claude-haiku-5-5"),
        "max_tokens": max_tokens,
        "system": sistema,
        "messages": [{"role": "user", "content": usuario}],
    }).encode()
    pet = urllib.request.Request(API, data=cuerpo, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(pet, timeout=180) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = _detalle_http(e)
        log(f"ERROR de la API: {detalle}")
        if 400 <= e.code < 500 and e.code not in (408, 409, 429):
            raise ErrorAPI(f"API: {detalle}") from e
        raise Reintentar(f"API: {detalle}") from e
    except OSError as e:
        raise Reintentar(f"API: {e}") from e
    uso = resp.get("usage", {})
    GASTO["entrada"] += uso.get("input_tokens", 0)
    GASTO["salida"] += uso.get("output_tokens", 0)
    if resp.get("stop_reason") == "max_tokens":
        raise ValueError(f"respuesta cortada al llegar a max_tokens ({max_tokens})")
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")


def extraer_json(texto: str):
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("la respuesta no contiene JSON")
    return json.loads(m.group(0))


# ------------------------------------------------------------------ RSS y páginas

def _texto(nodo, *etiquetas):
    for e in etiquetas:
        for hijo in nodo.iter():
            if hijo.tag.split("}")[-1] == e and (hijo.text or "").strip():
                return hijo.text.strip()
    return ""


def limpiar(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def leer_feeds(horas: int) -> list[dict]:
    cfg = yaml.safe_load((RAIZ / FEEDS[EDICION]).read_text(encoding="utf-8"))
    limite = datetime.now(TZ) - timedelta(hours=horas)
    items, vistos = [], set()
    for seccion, feeds in cfg.items():
        for f in feeds:
            try:
                raiz = ET.fromstring(descargar(f["url"]))
            except Exception as e:  # noqa: BLE001
                log(f"AVISO feed caído ({f['medio']}, {seccion}): {e}")
                continue
            n = 0
            for it in [x for x in raiz.iter() if x.tag.split("}")[-1] in ("item", "entry")]:
                titulo = limpiar(_texto(it, "title"))
                enlace = _texto(it, "link")
                if not enlace:
                    l = next((x for x in it if x.tag.split("}")[-1] == "link"), None)
                    enlace = l.get("href", "") if l is not None else ""
                if not titulo or not enlace or enlace in vistos:
                    continue
                fecha = _texto(it, "pubDate", "published", "updated", "date")
                try:
                    d = email.utils.parsedate_to_datetime(fecha) if "," in fecha else datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                    if d.tzinfo and d < limite:
                        continue
                except Exception:  # noqa: BLE001 — sin fecha legible: se acepta
                    pass
                vistos.add(enlace)
                items.append({"id": len(items), "seccion": seccion, "medio": f["medio"], "titulo": titulo,
                              "url": enlace.strip(), "resumen": limpiar(_texto(it, "description", "summary"))[:300]})
                n += 1
                if n >= 15:
                    break
    return items


class _Parrafos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dentro, self.salto, self.parrafos, self.actual = 0, 0, [], []
        self.enlaces = []   # enlaces dentro de los párrafos del texto (no menús ni pies)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "aside", "nav", "footer", "figure"):
            self.salto += 1
        elif tag == "p":
            self.dentro += 1
        elif tag == "a" and self.dentro and not self.salto:
            href = dict(attrs).get("href") or ""
            if href.startswith("http"):
                self.enlaces.append(href.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style", "aside", "nav", "footer", "figure"):
            self.salto = max(0, self.salto - 1)
        elif tag == "p" and self.dentro:
            self.dentro -= 1
            t = " ".join("".join(self.actual).split())
            if len(t) > 60:
                self.parrafos.append(t)
            self.actual = []

    def handle_data(self, data):
        if self.dentro and not self.salto:
            self.actual.append(data)


@functools.lru_cache(maxsize=256)
def html_pagina(url: str) -> str:
    return descargar(url).decode("utf-8", "replace")


VIDEO_YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def videos_fuentes(fuentes: list[dict], maximo: int = 5) -> list[dict]:
    """Vídeos de YouTube insertados en las páginas de las fuentes que YouTube deja insertar
    (oEmbed responde solo si el vídeo es público e insertable), con su título y su canal."""
    vistos, videos = set(), []
    for f in fuentes:
        try:
            ids = VIDEO_YT.findall(html_pagina(f["url"]))
        except Exception:  # noqa: BLE001
            continue
        for vid in ids:
            if vid in vistos or len(videos) >= maximo:
                continue
            vistos.add(vid)
            try:
                o = json.loads(descargar("https://www.youtube.com/oembed?format=json&url="
                                         + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}"), 100_000))
            except Exception:  # noqa: BLE001
                continue
            videos.append({"id": vid, "titulo": str(o.get("title") or "").strip(),
                           "autor": str(o.get("author_name") or "").strip()})
    return videos


@functools.lru_cache(maxsize=1024)
def texto_pagina(url: str) -> str:
    try:
        p = _Parrafos()
        p.feed(html_pagina(url))
        return "\n".join(p.parrafos)[:7000]
    except Exception as e:  # noqa: BLE001
        log(f"AVISO no se pudo leer {url}: {e}")
        return ""


MIN_LEGIBLE = 600   # caracteres de texto propio que debe dar una página para poder usarla como fuente


# ------------------------------------------------------------------ fuente original

AGENCIAS = {"efe.com", "europapress.es", "reuters.com", "afp.com", "apnews.com"}
NOMBRES_OFICIALES = {
    "ine.es": ("INE", "Spain's National Statistics Institute (INE)"), "boe.es": ("BOE", "Spain's Official State Gazette (BOE)"),
    "bde.es": ("Banco de España", "Bank of Spain"), "cnmv.es": ("CNMV", "CNMV"), "aemet.es": ("AEMET", "AEMET"),
    "dgt.es": ("DGT", "DGT"), "congreso.es": ("Congreso de los Diputados", "Congress of Deputies"),
    "senado.es": ("Senado", "Spanish Senate"), "poderjudicial.es": ("Poder Judicial", "Spanish judiciary (CGPJ)"),
    "gob.es": ("Gobierno de España", "Spanish Government"), "europa.eu": ("Unión Europea", "European Union"),
    "un.org": ("ONU", "United Nations"), "who.int": ("OMS", "World Health Organization"),
    "unhcr.org": ("ACNUR", "UNHCR"), "nato.int": ("OTAN", "NATO"), "imf.org": ("FMI", "IMF"),
    "oecd.org": ("OCDE", "OECD"), "worldbank.org": ("Banco Mundial", "World Bank"), "csic.es": ("CSIC", "CSIC"),
    "agenciasinc.es": ("Agencia SINC", "SINC"), "nature.com": ("Nature", "Nature"), "science.org": ("Science", "Science"),
    "thelancet.com": ("The Lancet", "The Lancet"), "nejm.org": ("NEJM", "NEJM"), "pnas.org": ("PNAS", "PNAS"),
}


@functools.lru_cache(maxsize=1024)
def enlaces_texto(url: str) -> tuple:
    try:
        p = _Parrafos()
        p.feed(html_pagina(url))
        return tuple(p.enlaces)
    except Exception:  # noqa: BLE001
        return ()


def _titulo_html(url: str) -> str:
    try:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_pagina(url), re.S | re.I)
    except Exception:  # noqa: BLE001
        return ""
    return " ".join(html.unescape(m.group(1)).split())[:200] if m else ""


def fuente_original(fuentes: list[dict], intentos: int = 3) -> dict | None:
    """Documento oficial o científico que las fuentes enlazan en su texto (nota del INE, BOE, estudio...).

    Google News y los lectores valoran el enlace a la fuente primaria. Solo se usa si es una página
    concreta (no una portada), de un dominio oficial o científico de config/fuentes_admitidas.yaml,
    distinto de las agencias, y con texto legible suficiente. No usa la API."""
    ya = {f["url"] for f in fuentes}
    probados = 0
    for f in fuentes:
        for href in enlaces_texto(f["url"]):
            partes = urllib.parse.urlsplit(href)
            if href in ya or len(partes.path.strip("/")) < 4 or partes.path.lower().endswith(".pdf"):
                continue
            c = clasificar(href)
            if not c or c[0] != "fuerte" or c[1] in AGENCIAS:
                continue
            probados += 1
            if len(texto_pagina(href)) >= MIN_LEGIBLE:
                nombre = NOMBRES_OFICIALES.get(c[1], (c[1], c[1]))[1 if EDICION == "en" else 0]
                return {"medio": nombre, "titulo": _titulo_html(href) or nombre, "url": href,
                        "texto": texto_pagina(href), "original_de": f["medio"]}
            if probados >= intentos:
                return None
    return None


def solo_legibles(items: list[dict], hilos: int = 8) -> list[dict]:
    """Descarta las piezas cuyo texto el servidor no puede leer (muro de pago, bloqueo, página vacía).

    Así ni el jefe de redacción ni el redactor automático gastan un turno en un tema que luego se
    descartaría por «sin texto suficiente». No usa la API: solo descarga páginas.
    """
    def ok(it):
        return len(texto_pagina(it["url"])) >= MIN_LEGIBLE
    with concurrent.futures.ThreadPoolExecutor(max_workers=hilos) as ex:
        validos = list(ex.map(ok, items))
    legibles = [it for it, v in zip(items, validos) if v]
    por_medio = {}
    for it, v in zip(items, validos):
        a = por_medio.setdefault(it["medio"], [0, 0])
        a[0] += v
        a[1] += 1
    log("Legibilidad por medio: " + ", ".join(f"{m} {a[0]}/{a[1]}" for m, a in sorted(por_medio.items())))
    return legibles


def comprobar_feeds() -> None:
    """Diagnóstico (--feeds): estado de cada RSS configurado y cuántas piezas legibles da."""
    for ed, ruta in FEEDS.items():
        cfg = yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))
        for seccion, feeds in cfg.items():
            for f in feeds:
                try:
                    raiz = ET.fromstring(descargar(f["url"]))
                    enlaces = [_texto(x, "link") for x in raiz.iter() if x.tag.split("}")[-1] in ("item", "entry")][:4]
                    leg = sum(len(texto_pagina(u)) >= MIN_LEGIBLE for u in enlaces if u)
                    print(f"OK    {ed}/{seccion:14} {f['medio']:14} {len(enlaces)} piezas, {leg} legibles  {f['url']}")
                except Exception as e:  # noqa: BLE001
                    print(f"FALLA {ed}/{seccion:14} {f['medio']:14} {e}  {f['url']}")


# ------------------------------------------------------------------ repositorio

def recientes(horas: int = 48) -> list[tuple]:
    limite = datetime.now(TZ) - timedelta(hours=horas)
    filas = []
    for ruta in (RAIZ / "content" / EDICION).glob("[0-9]*/[0-9]*/[0-9]*/*.md"):
        try:
            meta = yaml.safe_load(ruta.read_text(encoding="utf-8").split("\n---", 1)[0][3:]) or {}
            f = meta["fecha"]
            f = datetime.fromisoformat(f) if isinstance(f, str) else f
            f = (f if f.tzinfo else f.replace(tzinfo=TZ)).astimezone(TZ)
        except Exception:  # noqa: BLE001
            continue
        if f >= limite:
            filas.append((f, meta.get("seccion", "?"), meta.get("titulo", ruta.stem)))
    return sorted(filas, reverse=True)


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    vacias = {"el", "la", "los", "las", "de", "del", "en", "y", "a", "un", "una", "por", "con", "que", "se", "al", "su", "para",
              "the", "of", "in", "on", "and", "to", "for", "an", "at", "by", "with", "as", "is", "its", "from"}
    palabras = [p for p in re.split(r"[^a-z0-9]+", t) if p and p not in vacias]
    return "-".join(palabras[:8]) or "noticia"


def git(*args, ok=False):
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)
    if r.returncode and not ok:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def check() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, str(RAIZ / "build.py"), "--check"], capture_output=True, text=True, cwd=RAIZ)
    return r.returncode == 0, (r.stdout + r.stderr)[-1500:]


# ------------------------------------------------------------------ rigor

def descartar(motivo: str) -> None:
    global MOTIVO
    MOTIVO = motivo
    log(f"  descartado: {motivo}")


def _admitidas() -> dict:
    return yaml.safe_load((RAIZ / "config/fuentes_admitidas.yaml").read_text(encoding="utf-8"))


def clasificar(url: str) -> tuple[str, str] | None:
    """Devuelve (fuerte|medio, dominio de la lista) o None si la fuente no está admitida."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    cfg = _admitidas()
    # Primero los medios: cincodias.elpais.com no debe contarse como elpais.com
    for clase, clave in (("medio", "medios"), ("fuerte", "fuertes")):
        for d in sorted(cfg[clave], key=len, reverse=True):
            if host == d or host.endswith("." + d):
                return clase, d
    return None


def dominio(url: str) -> str | None:
    """Grupo editorial de la fuente: el dominio admitido más corto que la contiene.
    cincodias.elpais.com y elpais.com son el mismo grupo: no cuentan como dos medios."""
    if not clasificar(url):
        return None
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    cfg = _admitidas()
    coincidencias = [d for clave in ("medios", "fuertes") for d in cfg[clave]
                     if host == d or host.endswith("." + d)]
    return min(coincidencias, key=len)


def medios(fuentes: list[dict]) -> set[str]:
    """Dominios distintos y admitidos de un conjunto de fuentes."""
    return {d for d in (dominio(f["url"]) for f in fuentes) if d}


def solidez(fuentes: list[dict]) -> str:
    """ok: al menos FUENTES_MINIMAS medios distintos y admitidos. atribuir: solo uno. no: ninguno."""
    doms = medios(fuentes)
    if len(doms) >= FUENTES_MINIMAS:
        return "ok"
    return "atribuir" if doms else "no"


_VACIAS = {"para", "como", "pero", "sobre", "entre", "tras", "desde", "hasta", "este", "esta", "estos", "estas",
           "donde", "cuando", "ayer", "hoy", "también", "sino", "tiene", "tienen", "hacia", "según",
           "that", "this", "with", "from", "have", "were", "their", "they", "will", "after", "about", "into",
           "over", "says", "said", "more", "than", "also", "been", "which", "while", "where", "when", "amid"}


def palabras_clave(texto: str) -> set[str]:
    return {w for w in re.findall(r"\w+", texto.lower()) if len(w) > 3 and w not in _VACIAS and not w.isdigit()}


def candidatas_mismo_hecho(tema: dict, pool: list[dict]) -> list[dict]:
    """Piezas de otros medios que cuentan el mismo hecho que el tema, de más a menos parecidas.

    Se usan para completar una noticia de un solo medio sin frenar la redacción: si el tema no alcanza
    FUENTES_MINIMAS medios distintos, se buscan aquí las demás piezas del mismo hecho entre los titulares
    ya leídos. Dos piezas cuentan como el mismo hecho si comparten al menos dos palabras clave y al menos
    una cuarta parte de las de la pieza candidata.
    """
    base = palabras_clave(" ".join([tema.get("tema", "")] + [f"{i['titulo']} {i['resumen']}" for i in tema["items"]]))
    usados = {i["url"] for i in tema["items"]}
    doms = {dominio(i["url"]) for i in tema["items"]}
    puntuadas = []
    for it in pool:
        if it["url"] in usados or dominio(it["url"]) in doms:
            continue
        clave = palabras_clave(f"{it['titulo']} {it['resumen']}")
        comunes = len(clave & base)
        if comunes >= 2 and comunes / max(len(clave), 1) >= 0.25:
            puntuadas.append((comunes / len(clave), it))
    return [it for _, it in sorted(puntuadas, key=lambda x: -x[0])]


def _numeros(texto: str) -> set[str]:
    t = re.sub(r"(\d{1,2}):(\d{2})\b", r"\1.\2", texto)
    t = re.sub(r"(?<=\d) (?=\d{3}\b)", "", t)
    return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d+(?:[.,]\d+)*", t)}


def cifras_sin_fuente(articulo: str, fuentes: list[dict], ahora: datetime) -> list[str]:
    """Números de dos o más cifras del artículo que no aparecen en ninguna fuente."""
    base = _numeros(" ".join(f.get("titulo", "") + " " + f["texto"] for f in fuentes))
    base |= {str(ahora.year), f"{ahora.day:02d}", str(ahora.day)}
    return sorted(n for n in _numeros(articulo) if len(n) >= 2 and n not in base)


def verificar(d: dict, fuentes: list[dict]) -> list[str]:
    """Segunda lectura: lista de datos del artículo que las fuentes no sostienen."""
    bloque = "\n\n".join(f"### FUENTE {n}: {f['medio']}\n{f['texto']}" for n, f in enumerate(fuentes, 1))
    sistema = "Eres el verificador de NewTimes.news. Compruebas un artículo contra sus fuentes. Respondes solo con JSON válido."
    hoy = datetime.now(TZ).strftime("%A %d/%m/%Y")
    usuario = f"""Hoy es {hoy}. Una fecha deducida correctamente de una referencia relativa de las fuentes («el pasado miércoles»,
«este domingo») es correcta.

FUENTES:
{bloque}

ARTÍCULO:
Titular: {d['titulo']}
Entradilla: {d.get('entradilla', '')}
Lugar: {d.get('lugar', '')}
{d['cuerpo']}

Comprueba uno por uno las cifras, fechas, nombres propios, cargos, lugares, citas entre comillas y atribuciones del
artículo. Señala solo lo que NO esté en las fuentes o las contradiga. Si fuentes y artículo están en idiomas distintos,
una traducción fiel es correcta. El estilo no importa.

Responde solo con: {{"problemas": ["dato y por qué falla", ...]}} (lista vacía si todo está sostenido por las fuentes)."""
    datos = extraer_json(claude(sistema, usuario, 8000))
    if not isinstance(datos.get("problemas"), list):
        raise ValueError("respuesta del verificador sin lista de problemas")
    return [str(p) for p in datos["problemas"]]


# ------------------------------------------------------------------ redacción

def elegir_temas(items, publicadas, secciones, maximo) -> list[dict]:
    hace12 = datetime.now(TZ) - timedelta(hours=12)
    cobertura = {s: sum(1 for f, sec, _ in publicadas if sec == s and f >= hace12) for s in secciones}
    lista = "\n".join(f"[{i['id']}] ({i['seccion']} · {i['medio']}) {i['titulo']}" for i in items)
    ya = "\n".join(f"- [{s}] {t}" for _, s, t in publicadas)
    if EDICION == "en":
        return _elegir(items, por_id_lista=lista, ya=ya, cobertura=cobertura, secciones=secciones, maximo=maximo,
                       sistema="You are the news editor of NewTimes.news (English edition, for English-speaking readers "
                               "in Spain and abroad). You answer only with valid JSON.",
                       usuario=f"""Recent headlines from our sources:
{lista}

Already published in the last 48 hours (do NOT repeat the same story unless there is an important development):
{ya}

Stories per section in the last 12 h: {json.dumps(cobertura)}

Choose between 0 and {maximo} new stories of general interest for English-speaking readers interested in Spain,
Europe and the world: concrete, confirmed facts, at most 2 per section, priority to sections with little coverage and
to Spain-related news. No opinion, rumours, horoscopes, offers, morbid crime stories or live blogs without facts.
If nothing deserves it, return an empty list.
For each story give the ids of 2 or 3 headlines about that same event, from DIFFERENT outlets (required: every story must be covered by at least two outlets).
Valid sections: {", ".join(secciones)}. Mark destacado=true on at most one, only if it is clearly the most important.

Answer only with: {{"temas": [{{"seccion": "...", "ids": [n, ...], "destacado": false, "tema": "one sentence"}}]}}""")
    sistema = "Eres el jefe de redacción de NewTimes.news (edición España). Respondes solo con JSON válido."
    usuario = f"""Titulares recientes de nuestras fuentes:
{lista}

Ya publicado en las últimas 48 horas (NO repetir el mismo asunto salvo novedad importante):
{ya}

Noticias por sección en las últimas 12 h: {json.dumps(cobertura)}

Elige entre 0 y {maximo} temas nuevos de interés general para lectores en España: hechos concretos y confirmados,
máximo 2 por sección, prioridad a secciones con poca cobertura. Nada de opinión, rumores, horóscopos, ofertas,
sucesos morbosos ni directos sin hechos. Si no hay nada que lo merezca, devuelve una lista vacía.
Para cada tema da los ids de 2 o 3 titulares que traten ese mismo hecho, de medios distintos (obligatorio: cada tema debe estar cubierto por al menos dos medios).
Secciones válidas: {", ".join(secciones)}. Marca destacado=true en como mucho uno, solo si es claramente lo más importante.

Responde solo con: {{"temas": [{{"seccion": "...", "ids": [n, ...], "destacado": false, "tema": "una frase"}}]}}"""
    return _elegir(items, por_id_lista=lista, ya=ya, cobertura=cobertura, secciones=secciones, maximo=maximo,
                   sistema=sistema, usuario=usuario)


def _elegir(items, por_id_lista, ya, cobertura, secciones, maximo, sistema, usuario) -> list[dict]:
    datos = extraer_json(claude(sistema, usuario, 6000))
    por_id = {i["id"]: i for i in items}
    temas, cuenta, destacado = [], {}, False
    for t in datos.get("temas", []):
        sec, ids = t.get("seccion"), [i for i in t.get("ids", []) if i in por_id][:3]
        if sec not in secciones or not ids or cuenta.get(sec, 0) >= 2 or len(temas) >= maximo:
            continue
        cuenta[sec] = cuenta.get(sec, 0) + 1
        t["destacado"] = bool(t.get("destacado")) and not destacado
        destacado = destacado or t["destacado"]
        temas.append({"seccion": sec, "items": [por_id[i] for i in ids], "destacado": t["destacado"], "tema": t.get("tema", "")})
    return temas


def _fuente(it: dict) -> dict | None:
    """Texto de una pieza de origen, o None si no se puede leer."""
    texto = texto_pagina(it["url"])
    if len(texto) < MIN_LEGIBLE:
        # La pieza era legible al hacer la lista de titulares: si ahora no, suele ser un bloqueo
        # pasajero del medio (límite de peticiones). Se reintenta una vez, sin caché, tras una pausa.
        time.sleep(20)
        html_pagina.cache_clear()
        texto = texto_pagina.__wrapped__(it["url"])
        log(f"  reintento de lectura: {len(texto)} caracteres en {it['url']}")
    texto = texto or it["resumen"]
    return {**it, "texto": texto} if len(texto) > 200 else None


def redactar(tema, agente, guia) -> str | None:
    fuentes = []
    for it in tema["items"]:
        if not clasificar(it["url"]):
            log(f"  fuente no admitida, se ignora: {it['url']}")
            continue
        f = _fuente(it)
        if f:
            fuentes.append(f)
    # Hacen falta FUENTES_MINIMAS medios distintos. Si el tema tiene menos, se completa con otra pieza
    # del mismo hecho que ya esté en la lista de titulares, sin descartar la noticia ni parar la redacción.
    for it in candidatas_mismo_hecho(tema, tema.get("pool", []))[:MAX_CANDIDATAS]:
        if len(medios(fuentes)) >= FUENTES_MINIMAS:
            break
        if dominio(it["url"]) in medios(fuentes):
            continue
        f = _fuente(it)
        if f:
            log(f"  segunda fuente ({f['medio']}): {f['url']}")
            fuentes.append(f)
    if sum(len(f["texto"]) for f in fuentes) < 800:
        descartar(f"sin texto suficiente en las fuentes: {tema['tema']}")
        return None
    if solidez(fuentes) == "no":
        descartar(f"ninguna fuente admitida: {tema['tema']}")
        return None
    orig = fuente_original(fuentes)
    if orig:
        log(f"  fuente original enlazada por {orig['original_de']}: {orig['url']}")
        fuentes.append(orig)
    if solidez(fuentes) != "ok":
        descartar(f"menos de {FUENTES_MINIMAS} medios distintos: {tema['tema']}")
        return None

    def cabecera(f):
        if not f.get("original_de"):
            return f"{f['medio']} — {f['titulo']}"
        return (f"{f['medio']} — {f['titulo']} (original document linked by {f['original_de']}: use it to check and "
                f"complete facts about this same event only)" if EDICION == "en" else
                f"{f['medio']} — {f['titulo']} (documento original que enlaza {f['original_de']}: úsalo para "
                f"comprobar y completar datos de este mismo hecho, no de otros asuntos)")
    bloque = "\n\n".join(f"### FUENTE {n}: {cabecera(f)}\nURL: {f['url']}\n{f['texto']}"
                         for n, f in enumerate(fuentes, 1))
    tema["videos"] = videos_fuentes(fuentes)
    if tema["videos"]:
        bloque += ("\n\n### VÍDEOS DE YOUTUBE INSERTADOS EN LAS FUENTES\n"
                   + "\n".join(f"[{v['id']}] «{v['titulo']}» — canal: {v['autor']}" for v in tema["videos"]))
    ahora = datetime.now(TZ)
    if EDICION == "en":
        sistema = f"""You are {agente['nombre']}, AI reporter for the {tema['seccion']} section of NewTimes.news (English edition).
Your style: {agente['estilo']}

Follow this editorial guide strictly (it overrides your style):
{guia}"""
        usuario = f"""It is {ahora.strftime('%A %d/%m/%Y, %H:%M')} (Madrid time). Write a story in British English about: {tema['tema']}

Use ONLY the facts in these sources. Do not add any fact, figure, name or quote that is not in them.
Write in your own words and structure: do not copy, translate or paraphrase sentence by sentence. Direct quotes: at most
two, short, only if they are in the source (translate faithfully if the source is in Spanish). If sources disagree,
attribute each version to the person or body behind it. Explain Spanish institutions and parties briefly for international readers.
NEVER name a media outlet in the text (no "according to X", "X reports", "X told"): the sources are listed separately at the end.

{bloque}

Answer only with this JSON:
{{"titulo": "headline in sentence case", "entradilla": "standfirst", "lugar": "city or empty", "etiquetas": ["...", "..."],
 "imagen_buscar": ["Wikimedia Commons search in English, 2-5 words, most precise first", "..."],
 "imagen_alt": "what can be seen", "imagen_pie": "File image of ...",
 "imagen2_buscar": ["Commons search for a SECOND picture of a different subject (place, institution, other person involved)", "..."],
 "imagen2_alt": "what can be seen", "imagen2_pie": "File image of ...",
 "video": "id of a video from the YOUTUBE VIDEOS list that shows exactly this event, or empty",
 "cuerpo": "Markdown text, 250-500 words, paragraphs separated by a blank line"}}
If the sources are not enough for a rigorous story, answer {{"descartar": "reason"}}."""
        bloque = bloque.replace("### FUENTE", "### SOURCE")
        usuario = usuario.replace("### FUENTE", "### SOURCE")
    else:
        sistema, usuario = _prompts_es(agente, tema, guia, ahora, bloque)
    return _escribir(tema, agente, fuentes, sistema, usuario, ahora)


def _prompts_es(agente, tema, guia, ahora, bloque):
    sistema = f"""Eres {agente['nombre']}, redactor de la sección {tema['seccion']} de NewTimes.news.
Tu estilo: {agente['estilo']}

Sigue estrictamente esta guía editorial (manda sobre tu estilo):
{guia}"""
    usuario = f"""Hoy es {ahora.strftime('%A %d/%m/%Y, %H:%M')} (hora de Madrid). Escribe una noticia sobre: {tema['tema']}

Usa ÚNICAMENTE los hechos de estas fuentes. No añadas ningún dato, cifra, nombre ni cita que no aparezca en ellas.
Escribe con tus palabras y tu propia estructura: no copies ni parafrasees frase a frase. Citas literales: máximo dos,
cortas, solo si están en la fuente. Si las fuentes discrepan, atribuye cada versión a la persona u organismo que la sostiene.
NUNCA nombres un medio de comunicación en el texto (nada de «según X», «X informa», «X publica»): las fuentes se listan aparte, al final.

{bloque}

Responde solo con este JSON:
{{"titulo": "...", "entradilla": "...", "lugar": "ciudad o vacío", "etiquetas": ["...", "..."],
 "imagen_buscar": ["búsqueda Wikimedia Commons en inglés, 2-5 palabras, de la más precisa a la más general", "..."],
 "imagen_alt": "qué se ve", "imagen_pie": "Imagen de archivo de ...",
 "imagen2_buscar": ["búsqueda en Commons para una SEGUNDA foto de otro motivo (lugar, institución, otra persona implicada)", "..."],
 "imagen2_alt": "qué se ve", "imagen2_pie": "Imagen de archivo de ...",
 "video": "id de un vídeo de la lista VÍDEOS DE YOUTUBE que muestre exactamente este hecho, o vacío",
 "cuerpo": "texto en Markdown, 250-500 palabras, párrafos separados por línea en blanco"}}
Si las fuentes no bastan para una noticia rigurosa, responde {{"descartar": "motivo"}}."""
    return sistema, usuario


def _escribir(tema, agente, fuentes, sistema, usuario, ahora, extra=None):
    try:
        d = extraer_json(claude(sistema, usuario, 16000))
    except Reintentar:
        raise
    except Exception as e:  # noqa: BLE001
        descartar(f"error al redactar: {e}")
        return None
    if d.get("descartar"):
        descartar(f"el agente descarta el tema: {d['descartar']}")
        return None
    usadas = fuentes
    cuerpo = (d.get("cuerpo") or "").strip()
    d["cuerpo"] = cuerpo
    if len(cuerpo.split()) < 150 or not d.get("titulo"):
        descartar("texto demasiado corto o sin titular")
        return None
    articulo = f"{d['titulo']}\n{d.get('entradilla', '')}\n{cuerpo}"
    if EDICION == "es":
        sueltas = cifras_sin_fuente(articulo, fuentes, ahora)
        if sueltas:
            descartar(f"cifras que no están en las fuentes: {', '.join(sueltas)}")
            return None
    try:
        problemas = verificar(d, fuentes)
    except Reintentar:
        raise
    except Exception as e:  # noqa: BLE001
        descartar(f"la verificación no dio un resultado válido: {e}")
        return None
    if problemas:
        descartar("la verificación encontró datos sin sostén: " + "; ".join(problemas)[:600])
        return None
    archivo = "File image" if EDICION == "en" else "Imagen de archivo"
    pie = d.get("imagen_pie") or archivo + "."
    if not pie.startswith(archivo):
        pie = f"{archivo}. " + pie
    meta = {
        "titulo": d["titulo"].strip(), "entradilla": (d.get("entradilla") or "").strip(),
        "seccion": tema["seccion"], "agente": agente["slug"],
        "fecha": ahora.replace(second=0, microsecond=0).isoformat(),
        "destacado": tema["destacado"], "etiquetas": d.get("etiquetas") or [],
        "imagen": {"buscar": (d.get("imagen_buscar") or [tema["seccion"]])[:4],
                   "alt": d.get("imagen_alt") or d["titulo"], "pie": pie},
        "fuentes": [{"medio": f["medio"], "titulo": f["titulo"], "url": f["url"]} for f in usadas],
    }
    if d.get("lugar"):
        meta["lugar"] = d["lugar"].strip()
    # Segunda imagen (otro motivo) y vídeo, si el agente los propone: la guía pide al menos dos imágenes
    busca2 = [b for b in (d.get("imagen2_buscar") or []) if str(b).strip()][:4]
    if busca2 and busca2 != meta["imagen"]["buscar"]:
        pie2 = d.get("imagen2_pie") or archivo + "."
        if not pie2.startswith(archivo):
            pie2 = f"{archivo}. " + pie2
        meta["imagenes"] = [{"buscar": busca2, "alt": d.get("imagen2_alt") or d["titulo"], "pie": pie2}]
    elegido = next((v for v in tema.get("videos") or [] if v["id"] == str(d.get("video") or "").strip()), None)
    if elegido:
        meta["video"] = elegido
    if extra:
        meta.update(extra)
    carpeta = RAIZ / "content" / EDICION / ahora.strftime("%Y/%m/%d")
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{slugify(meta['titulo'])}.md"
    if ruta.exists():
        descartar(f"ya existe {ruta.name}")
        return None
    ruta.write_text("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + cuerpo + "\n", encoding="utf-8")
    ok, salida = check()
    if not ok:
        descartar(f"no pasa build.py --check: {salida[-400:]}")
        ruta.unlink()
        return None
    log(f"  OK {ruta.relative_to(RAIZ)} — {meta['titulo']}")
    return str(ruta.relative_to(RAIZ))


# ------------------------------------------------------------- lanzamientos musicales

YT = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}


def videos_canal(artista: dict) -> list[dict]:
    """Vídeos recientes de un canal oficial de YouTube, por su RSS público (sin API ni IA)."""
    raiz = ET.fromstring(descargar(f"https://www.youtube.com/feeds/videos.xml?channel_id={artista['canal_id']}"))
    videos = []
    for e in raiz.findall("a:entry", YT):
        vid = e.findtext("yt:videoId", "", YT)
        nodo = e.find("a:link", YT)
        enlace = (nodo.get("href") if nodo is not None else "") or ""
        if not vid or "/shorts/" in enlace:   # un short no es un lanzamiento
            continue
        grupo = e.find("media:group", YT)
        videos.append({
            "artista": artista["nombre"], "canal": artista["canal"], "id": vid,
            "titulo": e.findtext("a:title", "", YT).strip(),
            "publicado": datetime.fromisoformat(e.findtext("a:published", "", YT)).astimezone(TZ),
            "descripcion": (grupo.findtext("media:description", "", YT) if grupo is not None else "").strip(),
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return sorted(videos, key=lambda v: v["publicado"], reverse=True)


def _videos_publicados() -> set[str]:
    hechos = set()
    for ruta in (RAIZ / "content").glob("*/*/*/*/*.md"):
        m = re.search(r"^video:\s*['\"]?([A-Za-z0-9_-]{11})", ruta.read_text(encoding="utf-8")[:4000], re.M)
        if m:
            hechos.add(m.group(1))
        m = re.search(r"^video:\s*\n\s+id:\s*['\"]?([A-Za-z0-9_-]{11})", ruta.read_text(encoding="utf-8")[:4000], re.M)
        if m:
            hechos.add(m.group(1))
    return hechos


def _fotograma(vid: str) -> str:
    for calidad in ("maxresdefault", "hqdefault"):
        url = f"https://i.ytimg.com/vi/{vid}/{calidad}.jpg"
        try:
            descargar(url, 5_000_000)
            return url
        except Exception:  # noqa: BLE001
            continue
    return ""


def escribir_lanzamiento(agentes, guia) -> str | None:
    """Encargo mensual de Cultura: el último lanzamiento aún no contado de los artistas de config/lanzamientos.yaml."""
    cfg = yaml.safe_load((RAIZ / "config/lanzamientos.yaml").read_text(encoding="utf-8"))
    seccion = cfg.get("seccion", "cultura")
    dias = int(cfg.get("dias", 60))
    ya = _videos_publicados()
    limite = datetime.now(TZ) - timedelta(days=dias)
    por_artista, candidatos = {}, []
    for art in cfg["artistas"]:
        try:
            vids = videos_canal(art)
        except Exception as e:  # noqa: BLE001
            log(f"  AVISO no se pudo leer el canal de {art['nombre']}: {e}")
            continue
        por_artista[art["nombre"]] = vids
        candidatos += [v for v in vids if v["id"] not in ya and v["publicado"] >= limite]
    if not por_artista:
        raise Reintentar("no se pudo leer ningún canal de YouTube")
    if not candidatos:
        descartar(f"ningún lanzamiento nuevo sin publicar en los últimos {dias} días")
        return None
    v = max(candidatos, key=lambda x: x["publicado"])
    log(f"  lanzamiento elegido: {v['artista']} — {v['titulo']} ({v['publicado']:%d/%m/%Y}) {v['url']}")
    otros = [o for o in por_artista[v["artista"]] if o["id"] != v["id"]][:6]
    fuentes = [{"medio": f"{v['artista']} (canal oficial en YouTube)", "titulo": v["titulo"], "url": v["url"],
                "texto": f"Artista: {v['artista']}\nCanal oficial: {v['canal']}\nTítulo del vídeo: {v['titulo']}\n"
                         f"Publicado en YouTube el {v['publicado']:%d/%m/%Y}\n\nDescripción publicada por el artista:\n"
                         f"{v['descripcion'] or '(sin descripción)'}"}]
    if otros:
        fuentes.append({"medio": f"{v['artista']} (canal oficial en YouTube)", "titulo": "Vídeos anteriores del canal",
                        "url": v["canal"],
                        "texto": "Vídeos anteriores publicados en el canal oficial:\n" + "\n".join(
                            f"- «{o['titulo']}», publicado el {o['publicado']:%d/%m/%Y}" for o in otros)})
    foto = _fotograma(v["id"])
    if not foto:
        descartar(f"no se pudo obtener un fotograma del vídeo {v['id']}")
        return None
    tema = {"seccion": seccion, "destacado": False,
            "tema": f"el lanzamiento de «{v['titulo']}», nuevo vídeo de {v['artista']} publicado en su canal oficial de YouTube"}
    bloque = "\n\n".join(f"### FUENTE {n}: {f['medio']} — {f['titulo']}\nURL: {f['url']}\n{f['texto']}"
                         for n, f in enumerate(fuentes, 1))
    ahora = datetime.now(TZ)
    sistema, usuario = _prompts_es(agentes[seccion], tema, guia, ahora, bloque)
    usuario += ("\n\nEs una pieza de servicio sobre un lanzamiento musical, de 150 a 300 palabras. Cuenta qué se ha "
                "publicado, de quién, cuándo y dónde verlo, y lo que diga la descripción del artista (atribuida a él). "
                "No valores la obra ni añadas nada sobre la trayectoria del artista que no esté en las fuentes; si la "
                "descripción está vacía, sé breve. Deja imagen_buscar vacío: la imagen será un fotograma del propio vídeo.")
    extra = {"video": v["id"], "imagenes": [], "imagen": {
        "url": foto, "autor": f"{v['artista']} / YouTube", "licencia": "video-oficial", "fuente": v["url"],
        "alt": f"Fotograma del vídeo «{v['titulo']}» de {v['artista']}",
        "pie": f"Fotograma del vídeo «{v['titulo']}», publicado por {v['artista']} en YouTube."}}
    return _escribir(tema, agentes[seccion], fuentes, sistema, usuario, ahora, extra)


# ------------------------------------------------------------------ encargos

_CLAVE_SIMPLE = re.compile(r"^(\s*(?:- )?[a-z_]+): (?!['\"|>])(.*: .*)$")


def cargar_encargo(texto: str):
    """Lee un encargo; si el YAML falla solo porque un valor lleva «: » sin comillas, lo entrecomilla."""
    try:
        return yaml.safe_load(texto)
    except yaml.YAMLError:
        reparado = "\n".join(
            (m.group(1) + ": " + json.dumps(m.group(2).strip(), ensure_ascii=False)) if (m := _CLAVE_SIMPLE.match(l)) else l
            for l in texto.splitlines())
        datos = yaml.safe_load(reparado)  # si sigue fallando, se propaga el error
        log("  aviso: YAML del encargo reparado (valor con «: » sin comillas)")
        return datos


def _validar_encargo(e, secciones) -> str:
    if not isinstance(e, dict) or e.get("seccion") not in secciones:
        return "sección ausente o no válida"
    if not str(e.get("tema") or "").strip():
        return "falta el tema"
    fuentes = e.get("fuentes")
    if not isinstance(fuentes, list) or not 1 <= len(fuentes) <= 4:
        return "hacen falta entre 1 y 4 fuentes"
    for f in fuentes:
        url = str(f.get("url", "")) if isinstance(f, dict) else ""
        if not url.startswith("https://"):
            return f"fuente sin URL https: {f}"
        if not clasificar(url):
            return f"fuente no admitida en config/fuentes_admitidas.yaml: {url}"
    return ""


def _archivar(ruta: Path, encargo, motivo: str) -> None:
    DESCARTADOS.mkdir(parents=True, exist_ok=True)
    datos = encargo if isinstance(encargo, dict) else {"contenido": str(encargo)}
    datos = {**datos, "motivo": motivo, "descartado": datetime.now(TZ).replace(microsecond=0).isoformat()}
    (DESCARTADOS / ruta.name).write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    ruta.unlink()


def _publicar(hechas: list[tuple], extra: list[str], etiqueta: str) -> None:
    ahora = datetime.now(TZ)
    if hechas:
        nombres = ", ".join(sorted({s for s, _ in hechas}))
        if EDICION == "en":
            msg = f"Newsroom EN {ahora:%Y-%m-%d %H}:00: {len(hechas)} stories (agents: {nombres}) [servidor]"
        else:
            msg = f"Redacción {ahora:%Y-%m-%d %H}:00: {len(hechas)} noticias (agentes: {nombres}) [servidor]"
    else:
        msg = f"{etiqueta} [servidor]"
    git("add", "-A", *extra, *[r for _, r in hechas])
    git("commit", "-q", "-m", msg)
    if git("push", "-q", "origin", "HEAD:main", ok=True).returncode:
        git("pull", "-q", "--rebase", "origin", "main")
        git("push", "-q", "origin", "HEAD:main")


def procesar_encargos(secciones, agentes, guia, prueba: bool) -> None:
    pendientes = sorted(PENDIENTES.glob("*.yaml"))
    if not pendientes:
        return
    tope = int(os.environ.get("NEWTIMES_MAX_ENCARGOS", 6))
    log(f"{len(pendientes)} encargos pendientes (se procesan hasta {tope})")
    hechas, cambios = [], 0
    for ruta in pendientes[:tope]:
        texto = ruta.read_text(encoding="utf-8")
        try:
            encargo = cargar_encargo(texto)
        except yaml.YAMLError as e:
            encargo, error, especial = texto, f"YAML no válido: {e}", False
        else:
            especial = isinstance(encargo, dict) and encargo.get("tipo") == "lanzamiento-youtube"
            error = "" if especial else _validar_encargo(encargo, secciones)
        if error:
            log(f"Encargo {ruta.name} rechazado: {error}")
            if not prueba:
                _archivar(ruta, encargo, error)
                cambios += 1
            continue
        if especial:
            tema = {"seccion": "cultura", "tema": "lanzamiento musical (YouTube)"}
        else:
            tema = {"seccion": encargo["seccion"], "tema": str(encargo["tema"]).strip(),
                    "destacado": bool(encargo.get("destacado")),
                    "items": [{"medio": f.get("medio") or urllib.parse.urlsplit(f["url"]).hostname, "url": f["url"],
                               "titulo": f.get("titulo") or "", "resumen": ""} for f in encargo["fuentes"]]}
        log(f"Encargo {ruta.name}: [{tema['seccion']}] {tema['tema']}")
        try:
            hecha = escribir_lanzamiento(agentes, guia) if especial else redactar(tema, agentes[tema["seccion"]], guia)
        except Reintentar as e:
            intentos = MAX_INTENTOS if e.permanente else int(encargo.get("intentos", 0)) + 1
            log(f"  fallo de la API (intento {intentos} de {MAX_INTENTOS}): {e}")
            if prueba:
                continue
            if e.permanente:
                _estado_api(False, str(e))   # el aviso sale en este mismo commit, sin esperar al chequeo horario
                _archivar(ruta, encargo, f"la API rechaza la petición (revisar clave, saldo o modelo en /etc/newtimes/redactor.env): {e}")
            elif intentos >= MAX_INTENTOS:
                _archivar(ruta, encargo, f"la API falló {intentos} veces: {e}")
            else:
                ruta.write_text(yaml.safe_dump({**encargo, "intentos": intentos}, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
            cambios += 1
            continue
        if hecha:
            hechas.append((agentes[tema["seccion"]]["slug"], hecha))
            if not prueba:
                ruta.unlink()
                _estado_api(True, "")
        elif not prueba:
            _archivar(ruta, encargo, MOTIVO)
            cambios += 1
    informar_gasto()
    if prueba:
        log(f"{len(hechas)} noticias escritas (modo prueba, sin commit ni cambios en los encargos)")
    elif hechas or cambios:
        _publicar(hechas, ["redaccion/encargos", *(["docs/estado-api.md"] if ESTADO_API.exists() else [])], f"Encargos: {cambios} sin publicar")
        log(f"Publicadas {len(hechas)} noticias; {cambios} encargos sin publicar")


def publicar_titulares(horas: int) -> None:
    """Deja en el repositorio los titulares recientes de los RSS para que el jefe elija. No usa la API."""
    items = solo_legibles([i for i in leer_feeds(horas) if clasificar(i["url"])])
    ahora = datetime.now(TZ).replace(second=0, microsecond=0)
    datos = {"generado": ahora.isoformat(), "titulares": [
        {k: i[k] for k in ("seccion", "medio", "titulo", "url", "resumen")} for i in items]}
    ruta = RAIZ / "redaccion/encargos/titulares.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    log(f"{len(items)} titulares guardados")
    _publicar([], [str(ruta.relative_to(RAIZ))], f"Titulares {ahora:%Y-%m-%d %H:%M}")


ESTADO_API = RAIZ / "docs/estado-api.md"


def _estado_api(ok: bool, detalle: str) -> bool:
    """Deja en docs/estado-api.md si la API responde. Devuelve True si el estado ha cambiado.

    Solo se reescribe cuando cambia el estado o el error, para no hacer un commit cada hora.
    El workflow «Alerta API» de GitHub lee este archivo y abre (o cierra) una incidencia.
    """
    estado = "ok" if ok else "caida"
    anterior = {}
    if ESTADO_API.exists():
        m = re.match(r"---\n(.*?)\n---", ESTADO_API.read_text(encoding="utf-8"), re.S)
        anterior = (yaml.safe_load(m.group(1)) if m else None) or {}
    if anterior.get("estado") == estado and (ok or anterior.get("detalle") == detalle):
        return False
    ahora = datetime.now(TZ).replace(microsecond=0).isoformat()
    if anterior.get("estado") == estado and anterior.get("desde"):
        ahora = str(anterior["desde"])   # sigue caída con otro error: se conserva desde cuándo
    datos = {"estado": estado, "desde": ahora, "detalle": detalle,
             "modelo": os.environ.get("NEWTIMES_MODELO", "claude-haiku-5-5")}
    if ok:
        texto = "La API de Anthropic responde con normalidad al redactor del servidor."
    else:
        texto = ("**La API de Anthropic rechaza las peticiones del redactor del servidor: no se publican noticias.**\n\n"
                 f"Error: `{detalle}`\n\n"
                 "Qué revisar, según el error:\n"
                 "- `credit balance is too low` o `usage limits`: recargar saldo o subir el límite de gasto en "
                 "console.anthropic.com (Billing / Limits). Conviene activar la recarga automática.\n"
                 "- `authentication_error` (401) o `permission_error` (403): la clave de /etc/newtimes/redactor.env "
                 "está revocada o es de otro espacio de trabajo.\n"
                 "- `not_found_error` (404) sobre el modelo: el modelo de NEWTIMES_MODELO no existe o se ha retirado.\n"
                 "- `rate_limit_error` (429) u `overloaded_error` (529): suele pasar solo; si dura horas, revisar el nivel de uso.\n\n"
                 "Registro: `sudo journalctl -u newtimes-salud-api -n 20` y `sudo journalctl -u newtimes-encargos -n 30`.")
    ESTADO_API.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_API.write_text("---\n" + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=1000) +
                          "---\n\n# Estado de la API (redactor del servidor)\n\n" + texto + "\n", encoding="utf-8")
    return True


def salud_api(prueba: bool) -> None:
    """Llamada mínima a la API (unos céntimos al mes) para detectar a tiempo saldo agotado, clave o modelo."""
    try:
        claude("Responde solo «ok».", "ok", max_tokens=64)
        ok, detalle = True, ""
    except ValueError:
        ok, detalle = True, ""   # respuesta cortada por max_tokens: la API ha aceptado la petición
    except ErrorAPI as e:
        ok, detalle = False, str(e)
    except Reintentar as e:
        # Fallo pasajero (red, 429, 5xx): una segunda prueba antes de dar la alarma
        time.sleep(60)
        try:
            claude("Responde solo «ok».", "ok", max_tokens=64)
            ok, detalle = True, ""
        except ValueError:
            ok, detalle = True, ""
        except Reintentar as e2:
            ok, detalle = False, f"{e2} (reintentado tras {e})"
    log(f"API: {'responde' if ok else 'CAÍDA: ' + detalle}")
    if _estado_api(ok, detalle) and not prueba:
        git("add", str(ESTADO_API.relative_to(RAIZ)))
        git("commit", "-q", "-m", f"Estado API: {'restablecida' if ok else 'CAÍDA'} [servidor]")
        if git("push", "-q", "origin", "HEAD:main", ok=True).returncode:
            git("pull", "-q", "--rebase", "origin", "main")
            git("push", "-q", "origin", "HEAD:main")


def informar_gasto() -> None:
    coste = GASTO["entrada"] / 1e6 * float(os.environ.get("NEWTIMES_PRECIO_ENTRADA", 0.10)) + \
        GASTO["salida"] / 1e6 * float(os.environ.get("NEWTIMES_PRECIO_SALIDA", 0.50))
    log(f"Tokens: {GASTO['entrada']} entrada, {GASTO['salida']} salida (≈ {coste:.4f} $)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true", help="no hace commit ni push")
    ap.add_argument("--max", type=int, default=int(os.environ.get("NEWTIMES_MAX", 3)))
    ap.add_argument("--horas", type=int, default=4, help="antigüedad máxima de los titulares RSS")
    ap.add_argument("--edicion", choices=["es", "en"], default=os.environ.get("NEWTIMES_EDICION", "es"))
    ap.add_argument("--encargos", action="store_true", help="escribe los encargos pendientes en vez de elegir temas")
    ap.add_argument("--feeds", action="store_true", help="comprueba cada RSS configurado y sale")
    ap.add_argument("--titulares", action="store_true", help="guarda los titulares de los RSS para el jefe de redacción")
    ap.add_argument("--salud-api", action="store_true", help="comprueba que la API responde y deja el estado en docs/estado-api.md")
    a = ap.parse_args()
    global EDICION
    EDICION = a.edicion
    if a.feeds:
        comprobar_feeds()
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY")

    if not a.prueba:
        git("pull", "-q", "--rebase", "origin", "main")
    if a.salud_api:
        salud_api(a.prueba)
        return
    cfg = yaml.safe_load((RAIZ / "config/site.yaml").read_text(encoding="utf-8"))
    secciones = [s["slug"] for s in cfg["ediciones"][EDICION]["secciones"]]
    agentes = {x["seccion"]: x for x in yaml.safe_load((RAIZ / "config/agentes.yaml").read_text(encoding="utf-8"))[EDICION]}
    guia = (RAIZ / GUIAS[EDICION]).read_text(encoding="utf-8")
    if a.titulares:
        publicar_titulares(a.horas)
        return
    if a.encargos:
        procesar_encargos(secciones, agentes, guia, a.prueba)
        return
    log(f"Edición: {EDICION}")

    # Ventana amplia para encontrar la segunda fuente del mismo hecho (ver FUENTES_MINIMAS).
    items = leer_feeds(max(a.horas, VENTANA_FUENTES_H))
    log(f"{len(items)} titulares en los RSS")
    items = solo_legibles([i for i in items if clasificar(i["url"])])
    for n, i in enumerate(items):
        i["id"] = n
    log(f"{len(items)} piezas legibles")
    if not items:
        return
    try:
        # Se piden 2 temas de más: si la verificación descarta alguno, el turno no se pierde
        temas = elegir_temas(items, recientes(48), secciones, a.max + 2)
    except (Reintentar, ValueError) as e:
        log(f"Fallo de la API al elegir temas: {e}")
        return
    log(f"{len(temas)} temas elegidos: " + " | ".join(f"[{t['seccion']}] {t['tema']}" for t in temas))

    hechas = []
    for t in temas:
        t["pool"] = items   # por si la noticia necesita una segunda fuente (ver redactar)
        if len(hechas) >= a.max:
            break
        log(f"Redactando [{t['seccion']}] {t['tema']}")
        try:
            r = redactar(t, agentes[t["seccion"]], guia)
        except Reintentar as e:
            log(f"  fallo de la API: {e}")
            continue
        if r:
            hechas.append((agentes[t["seccion"]]["slug"], r))

    informar_gasto()
    if not hechas or a.prueba:
        log(f"{len(hechas)} noticias escritas" + (" (modo prueba, sin commit)" if a.prueba else ""))
        return
    _publicar(hechas, [], "")
    log(f"Publicadas {len(hechas)} noticias")


if __name__ == "__main__":
    main()
