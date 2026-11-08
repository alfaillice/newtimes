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

Uso:  python3 redaccion/servidor/redactor.py [--prueba] [--max N] [--edicion es|en] [--encargos] [--titulares]
      --prueba   escribe los archivos pero no hace commit ni push
      --edicion  es (por defecto; RSS de config/fuentes_rss.yaml, guía GUIA.md) o
                 en (RSS de config/fuentes_rss_en.yaml, guía GUIDE.md, escribe en content/en/)
"""
import argparse
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
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
MOTIVO = ""   # por qué se descartó la última noticia


class Reintentar(Exception):
    """Fallo pasajero de la API: el encargo se puede volver a intentar."""


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

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "aside", "nav", "footer", "figure"):
            self.salto += 1
        elif tag == "p":
            self.dentro += 1

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


def texto_pagina(url: str) -> str:
    try:
        p = _Parrafos()
        p.feed(descargar(url).decode("utf-8", "replace"))
        return "\n".join(p.parrafos)[:7000]
    except Exception as e:  # noqa: BLE001
        log(f"AVISO no se pudo leer {url}: {e}")
        return ""


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


def solidez(fuentes: list[dict]) -> str:
    """ok: agencia, fuente oficial o dos medios. atribuir: un solo medio. no: ninguna admitida."""
    clases = [c for c in (clasificar(f["url"]) for f in fuentes) if c]
    if any(c == "fuerte" for c, _ in clases) or len({d for _, d in clases}) >= 2:
        return "ok"
    return "atribuir" if clases else "no"


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
    usuario = f"""FUENTES:
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
For each story give the ids of 1 to 3 headlines about that same event (ideally from different outlets).
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
Para cada tema da los ids de 1 a 3 titulares que traten ese mismo hecho (mejor de medios distintos).
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


def redactar(tema, agente, guia) -> str | None:
    fuentes = []
    for it in tema["items"]:
        if not clasificar(it["url"]):
            log(f"  fuente no admitida, se ignora: {it['url']}")
            continue
        texto = texto_pagina(it["url"]) or it["resumen"]
        if len(texto) > 200:
            fuentes.append({**it, "texto": texto})
    if sum(len(f["texto"]) for f in fuentes) < 800:
        descartar(f"sin texto suficiente en las fuentes: {tema['tema']}")
        return None
    if solidez(fuentes) == "no":
        descartar(f"ninguna fuente admitida: {tema['tema']}")
        return None
    bloque = "\n\n".join(f"### FUENTE {n}: {f['medio']} — {f['titulo']}\nURL: {f['url']}\n{f['texto']}"
                         for n, f in enumerate(fuentes, 1))
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
attribute each version. Explain Spanish institutions and parties briefly for international readers.

{bloque}

Answer only with this JSON:
{{"titulo": "headline in sentence case", "entradilla": "standfirst", "lugar": "city or empty", "etiquetas": ["...", "..."],
 "imagen_buscar": ["Wikimedia Commons search in English, 2-5 words, most precise first", "..."],
 "imagen_alt": "what can be seen", "imagen_pie": "File image of ...",
 "cuerpo": "Markdown text, 250-500 words, paragraphs separated by a blank line"}}
If the sources are not enough for a rigorous story, answer {{"descartar": "reason"}}."""
        bloque = bloque.replace("### FUENTE", "### SOURCE")
        usuario = usuario.replace("### FUENTE", "### SOURCE")
    else:
        sistema, usuario = _prompts_es(agente, tema, guia, ahora, bloque)
    if solidez(fuentes) == "atribuir":
        medio = fuentes[0]["medio"]
        usuario += (f"\n\nAll the facts come from a single outlet: attribute them explicitly in the text to {medio}."
                    if EDICION == "en" else
                    f"\n\nTodos los datos proceden de un solo medio: atribúyelos expresamente en el texto a {medio} (por ejemplo, «según publica {medio}»).")
    return _escribir(tema, agente, fuentes, sistema, usuario, ahora)


def _prompts_es(agente, tema, guia, ahora, bloque):
    sistema = f"""Eres {agente['nombre']}, redactor de la sección {tema['seccion']} de NewTimes.news.
Tu estilo: {agente['estilo']}

Sigue estrictamente esta guía editorial (manda sobre tu estilo):
{guia}"""
    usuario = f"""Hoy es {ahora.strftime('%A %d/%m/%Y, %H:%M')} (hora de Madrid). Escribe una noticia sobre: {tema['tema']}

Usa ÚNICAMENTE los hechos de estas fuentes. No añadas ningún dato, cifra, nombre ni cita que no aparezca en ellas.
Escribe con tus palabras y tu propia estructura: no copies ni parafrasees frase a frase. Citas literales: máximo dos,
cortas, solo si están en la fuente. Si las fuentes discrepan, atribuye cada versión.

{bloque}

Responde solo con este JSON:
{{"titulo": "...", "entradilla": "...", "lugar": "ciudad o vacío", "etiquetas": ["...", "..."],
 "imagen_buscar": ["búsqueda Wikimedia Commons en inglés, 2-5 palabras, de la más precisa a la más general", "..."],
 "imagen_alt": "qué se ve", "imagen_pie": "Imagen de archivo de ...",
 "cuerpo": "texto en Markdown, 250-500 palabras, párrafos separados por línea en blanco"}}
Si las fuentes no bastan para una noticia rigurosa, responde {{"descartar": "motivo"}}."""
    return sistema, usuario


def _escribir(tema, agente, fuentes, sistema, usuario, ahora):
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
    if solidez(fuentes) == "atribuir" and fuentes[0]["medio"].lower() not in articulo.lower():
        descartar(f"dato de un solo medio sin atribuir a {fuentes[0]['medio']}")
        return None
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


# ------------------------------------------------------------------ encargos

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
        try:
            encargo = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            encargo, error = None, f"YAML no válido: {e}"
        else:
            error = _validar_encargo(encargo, secciones)
        if error:
            log(f"Encargo {ruta.name} rechazado: {error}")
            if not prueba:
                _archivar(ruta, encargo, error)
                cambios += 1
            continue
        tema = {"seccion": encargo["seccion"], "tema": str(encargo["tema"]).strip(),
                "destacado": bool(encargo.get("destacado")),
                "items": [{"medio": f.get("medio") or urllib.parse.urlsplit(f["url"]).hostname, "url": f["url"],
                           "titulo": f.get("titulo") or "", "resumen": ""} for f in encargo["fuentes"]]}
        log(f"Encargo {ruta.name}: [{tema['seccion']}] {tema['tema']}")
        try:
            hecha = redactar(tema, agentes[tema["seccion"]], guia)
        except Reintentar as e:
            intentos = int(encargo.get("intentos", 0)) + 1
            log(f"  fallo de la API (intento {intentos} de {MAX_INTENTOS}): {e}")
            if prueba:
                continue
            if intentos >= MAX_INTENTOS:
                _archivar(ruta, encargo, f"la API falló {intentos} veces: {e}")
            else:
                ruta.write_text(yaml.safe_dump({**encargo, "intentos": intentos}, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
            cambios += 1
            continue
        if hecha:
            hechas.append((agentes[tema["seccion"]]["slug"], hecha))
            if not prueba:
                ruta.unlink()
        elif not prueba:
            _archivar(ruta, encargo, MOTIVO)
            cambios += 1
    informar_gasto()
    if prueba:
        log(f"{len(hechas)} noticias escritas (modo prueba, sin commit ni cambios en los encargos)")
    elif hechas or cambios:
        _publicar(hechas, ["redaccion/encargos"], f"Encargos: {cambios} sin publicar")
        log(f"Publicadas {len(hechas)} noticias; {cambios} encargos sin publicar")


def publicar_titulares(horas: int) -> None:
    """Deja en el repositorio los titulares recientes de los RSS para que el jefe elija. No usa la API."""
    items = [i for i in leer_feeds(horas) if clasificar(i["url"])]
    ahora = datetime.now(TZ).replace(second=0, microsecond=0)
    datos = {"generado": ahora.isoformat(), "titulares": [
        {k: i[k] for k in ("seccion", "medio", "titulo", "url", "resumen")} for i in items]}
    ruta = RAIZ / "redaccion/encargos/titulares.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    log(f"{len(items)} titulares guardados")
    _publicar([], [str(ruta.relative_to(RAIZ))], f"Titulares {ahora:%Y-%m-%d %H:%M}")


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
    ap.add_argument("--titulares", action="store_true", help="guarda los titulares de los RSS para el jefe de redacción")
    a = ap.parse_args()
    global EDICION
    EDICION = a.edicion
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY")

    if not a.prueba:
        git("pull", "-q", "--rebase", "origin", "main")
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

    items = leer_feeds(a.horas)
    log(f"{len(items)} titulares en los RSS")
    if not items:
        return
    try:
        temas = elegir_temas(items, recientes(48), secciones, a.max)
    except (Reintentar, ValueError) as e:
        log(f"Fallo de la API al elegir temas: {e}")
        return
    log(f"{len(temas)} temas elegidos: " + " | ".join(f"[{t['seccion']}] {t['tema']}" for t in temas))

    hechas = []
    for t in temas:
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
