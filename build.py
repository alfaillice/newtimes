#!/usr/bin/env python3
"""Generador estático de NewTimes.news.

Uso:
  python3 build.py            construye la web en public/
  python3 build.py --check    solo valida los artículos (sale con error si alguno falla)
  python3 build.py --out DIR  construye en otra carpeta

Cada noticia es un archivo Markdown en content/<edición>/AAAA/MM/DD/<slug>.md
con metadatos YAML al principio (ver redaccion/GUIA.md).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).resolve().parent
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
CAMPOS_OBLIGATORIOS = ["titulo", "entradilla", "seccion", "fecha", "fuentes"]
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LICENCIAS_VALIDAS = {"cc0", "cc-by", "cc-by-sa", "dominio-publico", "kit-de-prensa", "propia"}


# ---------------------------------------------------------------- utilidades

def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:80].strip("-")


def fecha_larga(d: datetime) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(d: datetime) -> str:
    return f"{d.day} {MESES[d.month - 1][:3]}"


def fecha_dia(d) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def leer_markdown(ruta: Path) -> tuple[dict, str]:
    texto = ruta.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        raise ValueError("falta el bloque de metadatos (---) al principio")
    partes = texto.split("\n---", 1)
    if len(partes) != 2:
        raise ValueError("el bloque de metadatos no está cerrado con ---")
    meta = yaml.safe_load(partes[0][3:]) or {}
    if not isinstance(meta, dict):
        raise ValueError("los metadatos no son un diccionario YAML")
    cuerpo = partes[1].lstrip("-").lstrip("\n")
    return meta, cuerpo


def md_a_html(texto: str) -> str:
    # El texto lo escriben agentes: no se permite HTML incrustado.
    seguro = texto.replace("<", "&lt;")
    return markdown.markdown(seguro, extensions=["extra", "sane_lists"], output_format="html")


def texto_plano(htmltxt: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", htmltxt)).strip()


# ---------------------------------------------------------------- modelo

@dataclass
class Articulo:
    edicion: str
    slug: str
    titulo: str
    entradilla: str
    seccion: dict
    fecha: datetime
    actualizado: datetime | None
    fuentes: list
    cuerpo_html: str
    palabras: int
    etiquetas: list = field(default_factory=list)
    destacado: bool = False
    lugar: str = ""
    imagen: dict | None = None
    autor: str = "Redacción NewTimes"
    ruta_fuente: str = ""
    url: str = ""          # ruta relativa al sitio, empieza y acaba en /
    og: str = ""           # ruta de la imagen para compartir

    @property
    def minutos(self) -> int:
        return max(1, math.ceil(self.palabras / 220))

    @property
    def fecha_iso(self) -> str:
        return self.fecha.isoformat()


def cargar_config() -> dict:
    return yaml.safe_load((RAIZ / "config/site.yaml").read_text(encoding="utf-8"))


def cargar_articulos(cfg: dict, codigo: str, tz: ZoneInfo, avisos: list, errores: list) -> list[Articulo]:
    ed = cfg["ediciones"][codigo]
    secciones = {s["slug"]: s for s in ed["secciones"]}
    base = RAIZ / "content" / codigo
    articulos: list[Articulo] = []
    vistos: dict[str, str] = {}
    for ruta in sorted(base.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.md")):
        rel = ruta.relative_to(RAIZ).as_posix()
        try:
            meta, cuerpo = leer_markdown(ruta)
            faltan = [c for c in CAMPOS_OBLIGATORIOS if not meta.get(c)]
            if faltan:
                raise ValueError("faltan campos: " + ", ".join(faltan))
            slug = ruta.stem
            if not SLUG_RE.match(slug):
                raise ValueError(f"nombre de archivo no válido '{slug}': usa minúsculas, números y guiones")
            if meta["seccion"] not in secciones:
                raise ValueError(f"sección desconocida '{meta['seccion']}'. Válidas: {', '.join(secciones)}")
            fecha = meta["fecha"]
            if isinstance(fecha, str):
                fecha = datetime.fromisoformat(fecha)
            if not isinstance(fecha, datetime):
                raise ValueError("'fecha' debe incluir hora: AAAA-MM-DDTHH:MM:SS+01:00")
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=tz)
            fecha = fecha.astimezone(tz)
            carpeta = ruta.parent.relative_to(base).as_posix()
            if carpeta != fecha.strftime("%Y/%m/%d"):
                raise ValueError(f"la carpeta {carpeta} no coincide con la fecha {fecha:%Y/%m/%d}")
            if fecha > datetime.now(tz) + timedelta(minutes=10):
                avisos.append(f"{rel}: fecha en el futuro, se publicará cuando llegue")
                continue
            act = meta.get("actualizado")
            if isinstance(act, str):
                act = datetime.fromisoformat(act)
            if isinstance(act, datetime):
                act = (act if act.tzinfo else act.replace(tzinfo=tz)).astimezone(tz)
            else:
                act = None
            fuentes = meta["fuentes"]
            if not isinstance(fuentes, list) or not fuentes:
                raise ValueError("'fuentes' debe ser una lista con al menos una fuente")
            for f in fuentes:
                if not isinstance(f, dict) or not f.get("medio") or not str(f.get("url", "")).startswith("https://"):
                    raise ValueError("cada fuente necesita 'medio' y 'url' (https://)")
            imagen = meta.get("imagen")
            if imagen:
                if not isinstance(imagen, dict) or not imagen.get("archivo") or not imagen.get("autor") \
                        or str(imagen.get("licencia", "")).lower() not in LICENCIAS_VALIDAS:
                    raise ValueError("'imagen' necesita archivo, autor y una licencia válida: "
                                     + ", ".join(sorted(LICENCIAS_VALIDAS)))
                if not (RAIZ / "static" / imagen["archivo"].lstrip("/")).is_file():
                    raise ValueError(f"no existe la imagen static/{imagen['archivo']}")
            cuerpo_html = md_a_html(cuerpo)
            palabras = len(texto_plano(cuerpo_html).split())
            if palabras < 120:
                raise ValueError(f"cuerpo demasiado corto ({palabras} palabras; mínimo 120)")
            url = f"/{ed['prefijo'] + '/' if ed['prefijo'] else ''}{fecha:%Y/%m/%d}/{slug}/"
            if url in vistos:
                raise ValueError(f"URL duplicada con {vistos[url]}")
            vistos[url] = rel
            articulos.append(Articulo(
                edicion=codigo, slug=slug, titulo=str(meta["titulo"]).strip(),
                entradilla=str(meta["entradilla"]).strip(), seccion=secciones[meta["seccion"]],
                fecha=fecha, actualizado=act, fuentes=fuentes, cuerpo_html=cuerpo_html,
                palabras=palabras, etiquetas=[str(e) for e in meta.get("etiquetas") or []],
                destacado=bool(meta.get("destacado")), lugar=str(meta.get("lugar") or ""),
                imagen=imagen or None, autor=str(meta.get("autor") or "Redacción NewTimes"),
                ruta_fuente=rel, url=url,
            ))
        except Exception as e:  # noqa: BLE001 — un artículo roto no debe tirar la web
            errores.append(f"{rel}: {e}")
    articulos.sort(key=lambda a: a.fecha, reverse=True)
    return articulos


# ---------------------------------------------------------------- imágenes para compartir

def generar_og(art: Articulo, salida: Path, cache: Path) -> str:
    """Tarjeta 1200x630 tipográfica (sin fotos de terceros)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return ""
    clave = hashlib.sha1(f"v2|{art.titulo}|{art.seccion['slug']}|{art.fecha_iso}".encode()).hexdigest()[:16]
    nombre = f"{clave}.png"
    destino = salida / "og" / nombre
    cacheado = cache / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not cacheado.exists():
        cache.mkdir(parents=True, exist_ok=True)
        W, H = 1200, 630
        color = art.seccion["color"]
        img = Image.new("RGB", (W, H), color)
        d = ImageDraw.Draw(img)
        lora = ImageFont.truetype(str(RAIZ / "assets/og/Lora.ttf"), 64)
        try:
            lora.set_variation_by_axes([600])
        except Exception:  # noqa: BLE001
            pass
        inter = ImageFont.truetype(str(RAIZ / "assets/og/Inter-SemiBold.otf"), 28)
        marca = ImageFont.truetype(str(RAIZ / "assets/og/Inter-SemiBold.otf"), 34)
        d.text((80, 70), f"{art.seccion['nombre']}  ·  {art.fecha:%d/%m/%Y %H:%M}", font=inter, fill="#E8ECF2")
        # titular con ajuste de línea
        palabras, lineas, actual = art.titulo.split(), [], ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if d.textlength(prueba, font=lora) > W - 160:
                lineas.append(actual)
                actual = p
            else:
                actual = prueba
        lineas.append(actual)
        if len(lineas) > 5:
            lineas = lineas[:5]
            lineas[-1] = lineas[-1].rstrip(".,;:") + "…"
        y = 150
        for linea in lineas:
            d.text((80, y), linea, font=lora, fill="#FFFFFF")
            y += 80
        d.rectangle([0, H - 96, W, H], fill="#FFFFFF")
        d.text((80, H - 70), "NEWTIMES", font=marca, fill="#14284B")
        ancho = d.textlength("NEWTIMES", font=marca)
        d.text((80 + ancho, H - 70), ".NEWS", font=marca, fill="#D21F2B")
        img.save(cacheado, "PNG", optimize=True)
    shutil.copyfile(cacheado, destino)
    return f"/og/{nombre}"


# ---------------------------------------------------------------- construcción

class Constructor:
    def __init__(self, cfg: dict, salida: Path):
        self.cfg = cfg
        self.salida = salida
        self.tz = ZoneInfo(cfg["zona_horaria"])
        self.ahora = datetime.now(self.tz)
        self.env = Environment(loader=FileSystemLoader(RAIZ / "templates"),
                               autoescape=select_autoescape(["html", "xml"]),
                               trim_blocks=True, lstrip_blocks=True)
        self.env.filters.update(fecha_larga=fecha_larga, fecha_corta=fecha_corta, fecha_dia=fecha_dia)
        self.version = self._version_estaticos()
        self.paginas_sitemap: list[tuple[str, str]] = []

    def _version_estaticos(self) -> str:
        h = hashlib.sha1()
        for p in sorted((RAIZ / "static").rglob("*")):
            if p.is_file() and p.suffix in {".css", ".js"}:
                h.update(p.read_bytes())
        return h.hexdigest()[:8]

    def escribir(self, ruta: str, contenido: str, sitemap: bool = True, prioridad: str = "0.5"):
        destino = self.salida / ruta.lstrip("/")
        if ruta.endswith("/"):
            destino = destino / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
        if sitemap and destino.name == "index.html":
            self.paginas_sitemap.append((ruta, prioridad))

    def render(self, plantilla: str, **ctx) -> str:
        return self.env.get_template(plantilla).render(cfg=self.cfg, ahora=self.ahora, v=self.version, **ctx)

    def edicion(self, codigo: str, articulos: list[Articulo]):
        ed = self.cfg["ediciones"][codigo]
        pre = f"/{ed['prefijo']}" if ed["prefijo"] else ""
        t = codigo  # carpeta de plantillas
        base_ctx = dict(ed=ed, codigo=codigo, pre=pre, secciones=ed["secciones"])
        cache_og = RAIZ / ".cache" / "og"
        for a in articulos:
            a.og = generar_og(a, self.salida, cache_og)

        ultimo = articulos[0].fecha if articulos else self.ahora
        por_seccion = {s["slug"]: [a for a in articulos if a.seccion["slug"] == s["slug"]] for s in ed["secciones"]}

        # Portada
        hace_48h = self.ahora - timedelta(hours=48)
        recientes = [a for a in articulos if a.fecha >= hace_48h] or articulos[:12]
        destacados = [a for a in recientes if a.destacado][:5]
        for a in recientes:
            if len(destacados) >= 5:
                break
            if a not in destacados:
                destacados.append(a)
        resto = [a for a in articulos if a not in destacados]
        hoy = self.ahora.date()
        de_hoy = [a for a in articulos if a.fecha.date() == hoy]
        horas = {}
        for a in sorted(de_hoy, key=lambda x: x.fecha):
            horas.setdefault(a.fecha.hour, []).append(a)
        bloques = []
        for s in ed["secciones"]:
            lista = [a for a in por_seccion[s["slug"]] if a not in destacados][:4]
            if lista:
                bloques.append((s, lista))
        self.escribir(f"{pre}/", self.render(f"{t}/portada.html", **base_ctx, destacados=destacados,
                                               ultima=resto[:10], horas=horas, bloques=bloques,
                                               ultimo=ultimo, total_hoy=len(de_hoy)), prioridad="1.0")

        # Artículos
        for a in articulos:
            relacionados = [x for x in por_seccion[a.seccion["slug"]] if x is not a][:4]
            self.escribir(a.url, self.render(f"{t}/articulo.html", **base_ctx, a=a, relacionados=relacionados),
                          prioridad="0.8")

        # Secciones con paginación
        n = ed.get("por_pagina", 20)
        for s in ed["secciones"]:
            lista = por_seccion[s["slug"]]
            total = max(1, math.ceil(len(lista) / n))
            for p in range(1, total + 1):
                ruta = f"{pre}/seccion/{s['slug']}/" + (f"{p}/" if p > 1 else "")
                self.escribir(ruta, self.render(f"{t}/seccion.html", **base_ctx, s=s, lista=lista[(p - 1) * n:p * n],
                                                pagina=p, total_paginas=total), prioridad="0.7" if p == 1 else "0.3")
            self.escribir(f"{pre}/seccion/{s['slug']}/rss.xml", self.rss(ed, pre, lista[:30], s), sitemap=False)

        # Hemeroteca
        dias: dict = {}
        for a in articulos:
            dias.setdefault(a.fecha.date(), []).append(a)
        meses: dict = {}
        for d in sorted(dias, reverse=True):
            meses.setdefault((d.year, d.month), []).append((d, len(dias[d])))
        self.escribir(f"{pre}/hemeroteca/", self.render(f"{t}/hemeroteca.html", **base_ctx, meses=meses, MESES=MESES))
        for d, lista in dias.items():
            self.escribir(f"{pre}/hemeroteca/{d:%Y/%m/%d}/",
                          self.render(f"{t}/dia.html", **base_ctx, dia=d, lista=sorted(lista, key=lambda x: x.fecha)),
                          prioridad="0.3")

        # Búsqueda (índice de los últimos 3000 artículos)
        indice = [{"t": a.titulo, "e": a.entradilla, "s": a.seccion["nombre"], "u": a.url,
                   "f": a.fecha.strftime("%d/%m/%Y"), "g": a.etiquetas} for a in articulos[:3000]]
        (self.salida / pre.lstrip("/") / "buscar").mkdir(parents=True, exist_ok=True)
        (self.salida / pre.lstrip("/") / "buscar" / "indice.json").write_text(
            json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        self.escribir(f"{pre}/buscar/", self.render(f"{t}/buscar.html", **base_ctx), sitemap=False)

        # Páginas fijas
        for ruta in sorted((RAIZ / "content" / codigo / "paginas").glob("*.md")):
            meta, cuerpo = leer_markdown(ruta)
            cuerpo = self.env.from_string(cuerpo).render(cfg=self.cfg, ed=ed)
            self.escribir(f"{pre}/{ruta.stem}/", self.render(f"{t}/pagina.html", **base_ctx, titulo=meta["titulo"],
                                                              resumen=meta.get("resumen", ""),
                                                              cuerpo=md_a_html(cuerpo), slug=ruta.stem),
                          prioridad="0.2")

        # 404, RSS general, sitemap de noticias
        self.escribir(f"{pre}/404.html", self.render(f"{t}/404.html", **base_ctx, ultima=articulos[:5]), sitemap=False)
        self.escribir(f"{pre}/rss.xml", self.rss(ed, pre, articulos[:50]), sitemap=False)
        self.escribir(f"{pre}/sitemap-noticias.xml",
                      self.render("sitemap-noticias.xml", ed=ed,
                                  lista=[a for a in articulos if a.fecha >= self.ahora - timedelta(hours=48)]),
                      sitemap=False)

    def rss(self, ed: dict, pre: str, lista: list, seccion: dict | None = None) -> str:
        return self.render("rss.xml", ed=ed, pre=pre, lista=lista, seccion=seccion, rfc=format_datetime)

    def finalizar(self):
        self.escribir("/sitemap.xml", self.render("sitemap.xml", paginas=self.paginas_sitemap), sitemap=False)
        self.escribir("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {self.cfg['url']}/sitemap.xml\n"
                                     f"Sitemap: {self.cfg['url']}/sitemap-noticias.xml\n", sitemap=False)
        shutil.copytree(RAIZ / "static", self.salida, dirs_exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="solo validar artículos")
    ap.add_argument("--out", default=str(RAIZ / "public"))
    args = ap.parse_args()

    cfg = cargar_config()
    tz = ZoneInfo(cfg["zona_horaria"])
    avisos: list[str] = []
    errores: list[str] = []
    ediciones = {c: cargar_articulos(cfg, c, tz, avisos, errores)
                 for c, e in cfg["ediciones"].items() if e.get("activa")}

    for a in avisos:
        print("aviso:", a)
    for e in errores:
        print("ERROR:", e)
    pendientes = [k for k, v in cfg["titular"].items() if "pendiente" in str(v)]
    if pendientes:
        print("aviso: faltan datos del titular en config/site.yaml:", ", ".join(pendientes))
    if args.check:
        total = sum(len(v) for v in ediciones.values())
        print(f"{total} artículos válidos, {len(errores)} con errores")
        return 1 if errores else 0

    final = Path(args.out).resolve()
    temporal = final.with_name(final.name + ".nuevo")
    shutil.rmtree(temporal, ignore_errors=True)
    temporal.mkdir(parents=True)
    c = Constructor(cfg, temporal)
    for codigo, arts in ediciones.items():
        c.edicion(codigo, arts)
    c.finalizar()
    # Cambio casi atómico: la web nunca queda a medio construir
    viejo = final.with_name(final.name + ".viejo")
    shutil.rmtree(viejo, ignore_errors=True)
    if final.exists():
        final.rename(viejo)
    temporal.rename(final)
    shutil.rmtree(viejo, ignore_errors=True)
    print(f"web construida en {final}: " + ", ".join(f"{k}={len(v)} artículos" for k, v in ediciones.items())
          + (f" ({len(errores)} omitidos por errores)" if errores else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
