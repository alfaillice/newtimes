#!/usr/bin/env python3
"""Redactor automático de NewTimes.news que corre en el propio servidor.

Sustituye a la tarea programada de Claude (que gasta el plan Pro) por llamadas
directas y baratas a la API de Anthropic (por defecto, Claude Haiku):

  1. Lee los RSS de config/fuentes_rss.yaml (gratis, sin IA).
  2. Pide al modelo que elija 2-3 temas nuevos que no estén en las últimas 48 h.
  3. Descarga el texto de las piezas de origen y pide al agente de cada sección
     (config/agentes.yaml) que escriba la noticia siguiendo redaccion/GUIA.md.
  4. Valida cada noticia con build.py --check, hace commit y push a GitHub.
     El servidor la publica en el siguiente ciclo de actualizar.sh (5 min).

Variables de entorno (en /etc/newtimes/redactor.env):
  ANTHROPIC_API_KEY   clave de la API (obligatoria)
  NEWTIMES_MODELO     modelo (por defecto claude-haiku-5-5)
  NEWTIMES_MAX        noticias máximas por ejecución (por defecto 3)

Uso:  python3 redaccion/servidor/redactor.py [--prueba] [--max N]
      --prueba  escribe los archivos pero no hace commit ni push
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


def log(*a):
    print(datetime.now(TZ).strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ red

def descargar(url: str, limite: int = 2_000_000) -> bytes:
    pet = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(pet, timeout=25) as r:
        return r.read(limite)


def claude(sistema: str, usuario: str, max_tokens: int = 4000) -> str:
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
    with urllib.request.urlopen(pet, timeout=180) as r:
        resp = json.loads(r.read())
    uso = resp.get("usage", {})
    GASTO["entrada"] += uso.get("input_tokens", 0)
    GASTO["salida"] += uso.get("output_tokens", 0)
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
    cfg = yaml.safe_load((RAIZ / "config/fuentes_rss.yaml").read_text(encoding="utf-8"))
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
    for ruta in (RAIZ / "content/es").glob("[0-9]*/[0-9]*/[0-9]*/*.md"):
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
    vacias = {"el", "la", "los", "las", "de", "del", "en", "y", "a", "un", "una", "por", "con", "que", "se", "al", "su", "para"}
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


# ------------------------------------------------------------------ redacción

def elegir_temas(items, publicadas, secciones, maximo) -> list[dict]:
    hace12 = datetime.now(TZ) - timedelta(hours=12)
    cobertura = {s: sum(1 for f, sec, _ in publicadas if sec == s and f >= hace12) for s in secciones}
    lista = "\n".join(f"[{i['id']}] ({i['seccion']} · {i['medio']}) {i['titulo']}" for i in items)
    ya = "\n".join(f"- [{s}] {t}" for _, s, t in publicadas)
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
    datos = extraer_json(claude(sistema, usuario, 1500))
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
        texto = texto_pagina(it["url"]) or it["resumen"]
        if len(texto) > 200:
            fuentes.append({**it, "texto": texto})
    if sum(len(f["texto"]) for f in fuentes) < 800:
        log(f"  descartado (sin texto suficiente en las fuentes): {tema['tema']}")
        return None
    bloque = "\n\n".join(f"### FUENTE {n}: {f['medio']} — {f['titulo']}\nURL: {f['url']}\n{f['texto']}"
                         for n, f in enumerate(fuentes, 1))
    ahora = datetime.now(TZ)
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
 "fuentes_usadas": [números de FUENTE usadas],
 "cuerpo": "texto en Markdown, 250-500 palabras, párrafos separados por línea en blanco"}}
Si las fuentes no bastan para una noticia rigurosa, responde {{"descartar": "motivo"}}."""
    try:
        d = extraer_json(claude(sistema, usuario, 3000))
    except Exception as e:  # noqa: BLE001
        log(f"  error al redactar: {e}")
        return None
    if d.get("descartar"):
        log(f"  el agente descarta el tema: {d['descartar']}")
        return None
    usadas = [fuentes[n - 1] for n in d.get("fuentes_usadas", []) if isinstance(n, int) and 0 < n <= len(fuentes)] or fuentes
    cuerpo = (d.get("cuerpo") or "").strip()
    if len(cuerpo.split()) < 150 or not d.get("titulo"):
        log("  descartado: texto demasiado corto o sin titular")
        return None
    pie = d.get("imagen_pie") or "Imagen de archivo."
    if not pie.startswith("Imagen de archivo"):
        pie = "Imagen de archivo. " + pie
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
    carpeta = RAIZ / "content/es" / ahora.strftime("%Y/%m/%d")
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{slugify(meta['titulo'])}.md"
    if ruta.exists():
        log(f"  ya existe {ruta.name}; se descarta")
        return None
    ruta.write_text("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + cuerpo + "\n", encoding="utf-8")
    ok, salida = check()
    if not ok:
        log(f"  no pasa build.py --check, se borra:\n{salida}")
        ruta.unlink()
        return None
    log(f"  OK {ruta.relative_to(RAIZ)} — {meta['titulo']}")
    return str(ruta.relative_to(RAIZ))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true", help="no hace commit ni push")
    ap.add_argument("--max", type=int, default=int(os.environ.get("NEWTIMES_MAX", 3)))
    ap.add_argument("--horas", type=int, default=4, help="antigüedad máxima de los titulares RSS")
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY")

    if not a.prueba:
        git("pull", "-q", "--rebase", "origin", "main")
    cfg = yaml.safe_load((RAIZ / "config/site.yaml").read_text(encoding="utf-8"))
    secciones = [s["slug"] for s in cfg["ediciones"]["es"]["secciones"]]
    agentes = {x["seccion"]: x for x in yaml.safe_load((RAIZ / "config/agentes.yaml").read_text(encoding="utf-8"))["es"]}
    guia = (RAIZ / "redaccion/GUIA.md").read_text(encoding="utf-8")

    items = leer_feeds(a.horas)
    log(f"{len(items)} titulares en los RSS")
    if not items:
        return
    temas = elegir_temas(items, recientes(48), secciones, a.max)
    log(f"{len(temas)} temas elegidos: " + " | ".join(f"[{t['seccion']}] {t['tema']}" for t in temas))

    hechas = []
    for t in temas:
        log(f"Redactando [{t['seccion']}] {t['tema']}")
        r = redactar(t, agentes[t["seccion"]], guia)
        if r:
            hechas.append((agentes[t["seccion"]]["slug"], r))

    coste = GASTO["entrada"] / 1e6 * float(os.environ.get("NEWTIMES_PRECIO_ENTRADA", 0.10)) + \
        GASTO["salida"] / 1e6 * float(os.environ.get("NEWTIMES_PRECIO_SALIDA", 0.50))
    log(f"Tokens: {GASTO['entrada']} entrada, {GASTO['salida']} salida (≈ {coste:.4f} $)")
    if not hechas or a.prueba:
        log(f"{len(hechas)} noticias escritas" + (" (modo prueba, sin commit)" if a.prueba else ""))
        return
    ahora = datetime.now(TZ)
    nombres = ", ".join(sorted({s for s, _ in hechas}))
    git("add", *[r for _, r in hechas])
    git("commit", "-q", "-m", f"Redacción {ahora:%Y-%m-%d %H}:00: {len(hechas)} noticias (agentes: {nombres}) [servidor]")
    if git("push", "-q", "origin", "HEAD:main", ok=True).returncode:
        git("pull", "-q", "--rebase", "origin", "main")
        git("push", "-q", "origin", "HEAD:main")
    log(f"Publicadas {len(hechas)} noticias")


if __name__ == "__main__":
    main()
