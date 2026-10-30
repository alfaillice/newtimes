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
import urllib.request
from io import BytesIO
from urllib.parse import urlparse
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
LICENCIAS = {
    "cc0": "CC0",
    "cc-by": "CC BY",
    "cc-by-sa": "CC BY-SA",
    "dominio-publico": "Dominio público",
    "pexels": "Licencia Pexels",
    "unsplash": "Licencia Unsplash",
    "uso-oficial": "Uso libre con atribución",
    "kit-de-prensa": "Material de prensa",
    "propia": "NewTimes.news",
}
LICENCIAS_VALIDAS = set(LICENCIAS)
AGENTE_CABECERA = {"User-Agent": "NewTimesBot/1.0 (+https://newtimes.news/como-trabajamos/; redaccion@newtimes.news)"}


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
    autor: str = "JM Triviño"
    agente: dict | None = None
    foto: dict | None = None     # imagen ya optimizada y servida desde la web
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


def cargar_agentes(codigo: str) -> list[dict]:
    ruta = RAIZ / "config/agentes.yaml"
    if not ruta.exists():
        return []
    return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}).get(codigo, [])


def comprobar_imagen(imagen, cfg: dict) -> None:
    if not isinstance(imagen, dict):
        raise ValueError("'imagen' debe ser un bloque (commons, buscar, url o archivo)")
    if imagen.get("commons") or imagen.get("buscar"):
        if imagen.get("commons") and not str(imagen["commons"]).startswith("File:"):
            raise ValueError("'commons' debe ser el nombre del archivo en Wikimedia Commons, empezando por 'File:'")
        if not imagen.get("alt"):
            raise ValueError("la imagen necesita 'alt' (descripción de lo que se ve)")
        return  # autor y licencia se toman de Commons al construir
    lic = str(imagen.get("licencia", "")).lower()
    if lic not in LICENCIAS_VALIDAS:
        raise ValueError("licencia de imagen no válida. Usa una de: " + ", ".join(sorted(LICENCIAS_VALIDAS)))
    if not imagen.get("autor"):
        raise ValueError("la imagen necesita 'autor'")
    if imagen.get("url"):
        u = urlparse(str(imagen["url"]))
        if u.scheme != "https" or u.hostname not in cfg.get("imagenes_permitidas", []):
            raise ValueError(f"imagen de un servidor no permitido ({u.hostname}). Solo: "
                             + ", ".join(cfg.get("imagenes_permitidas", [])))
        if lic not in {"kit-de-prensa", "propia"} and not imagen.get("fuente"):
            raise ValueError("la imagen necesita 'fuente' (página donde figura su licencia)")
    elif imagen.get("archivo"):
        if not (RAIZ / "static" / str(imagen["archivo"]).lstrip("/")).is_file():
            raise ValueError(f"no existe la imagen static/{imagen['archivo']}")
    else:
        raise ValueError("la imagen necesita 'url' (descarga) o 'archivo' (en static/)")


def cargar_articulos(cfg: dict, codigo: str, tz: ZoneInfo, avisos: list, errores: list) -> list[Articulo]:
    ed = cfg["ediciones"][codigo]
    secciones = {s["slug"]: s for s in ed["secciones"]}
    agentes = cargar_agentes(codigo)
    por_slug = {a["slug"]: a for a in agentes}
    por_seccion = {a["seccion"]: a for a in agentes}
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
                comprobar_imagen(imagen, cfg)
                if imagen.get("licencia"):
                    imagen["licencia"] = str(imagen["licencia"]).lower()
            else:
                avisos.append(f"{rel}: sin imagen")
            agente = por_slug.get(str(meta.get("agente") or ""))
            if agentes:
                esperado = por_seccion.get(meta["seccion"])
                if not meta.get("agente"):
                    raise ValueError(f"falta la firma: 'agente: {esperado['slug'] if esperado else '?'}'")
                if not agente:
                    raise ValueError(f"agente desconocido '{meta.get('agente')}'. Válidos: {', '.join(por_slug)}")
                if esperado and agente["slug"] != esperado["slug"]:
                    raise ValueError(f"la sección {meta['seccion']} la firma {esperado['slug']}, no {agente['slug']}")
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
                imagen=imagen or None, agente=agente,
                autor=agente["nombre"] if agente else str(meta.get("autor") or "JM Triviño"),
                ruta_fuente=rel, url=url,
            ))
        except Exception as e:  # noqa: BLE001 — un artículo roto no debe tirar la web
            errores.append(f"{rel}: {e}")
    articulos.sort(key=lambda a: a.fecha, reverse=True)
    return articulos


# ---------------------------------------------------------------- fotos

COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _licencia_commons(meta: dict) -> str | None:
    codigo = str((meta.get("License") or {}).get("value", "")).lower()
    corto = str((meta.get("LicenseShortName") or {}).get("value", "")).lower()
    for t in (codigo, corto):
        if t.startswith("cc-by-sa") or t.startswith("cc by-sa"):
            return "cc-by-sa"
        if t.startswith("cc-by") or t.startswith("cc by"):
            return "cc-by"
        if t.startswith("cc0") or t.startswith("cc-zero"):
            return "cc0"
        if t.startswith("pd") or "public domain" in t or "dominio público" in t:
            return "dominio-publico"
    return None


def resolver_commons(img: dict, cache: Path) -> dict:
    """Busca en Wikimedia Commons y devuelve url, autor, licencia y fuente reales.
    El resultado se guarda para que la foto no cambie entre construcciones."""
    clave = "commons:" + (str(img.get("commons")) if img.get("commons") else "buscar:" + json.dumps(img.get("buscar"), ensure_ascii=False))
    registro = cache / "commons.json"
    datos = json.loads(registro.read_text()) if registro.exists() else {}
    if clave in datos:
        return datos[clave]
    from urllib.parse import urlencode
    base = {"action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime", "iiurlwidth": "1600", "iiextmetadatalanguage": "es"}
    if img.get("commons"):
        consultas = [{**base, "titles": str(img["commons"])}]
    else:
        # Varias búsquedas posibles; cada una se reintenta quitando palabras del final
        terminos = img["buscar"] if isinstance(img["buscar"], list) else [img["buscar"]]
        consultas, vistas = [], set()
        for t in terminos:
            palabras = str(t).split()
            for n in range(len(palabras), max(1, min(2, len(palabras))) - 1, -1):
                q = " ".join(palabras[:n])
                if q.lower() not in vistas:
                    vistas.add(q.lower())
                    consultas.append({**base, "generator": "search", "gsrnamespace": "6", "gsrlimit": "25",
                                      "gsrsearch": f"{q} filetype:bitmap"})
    for params in consultas[:8]:
        pet = urllib.request.Request(COMMONS_API + "?" + urlencode(params), headers=AGENTE_CABECERA)
        with urllib.request.urlopen(pet, timeout=20) as r:
            respuesta = json.load(r)
        paginas = sorted((respuesta.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        encontrado = _elegir_commons(paginas, bool(img.get("commons")))
        if encontrado:
            datos[clave] = encontrado
            cache.mkdir(parents=True, exist_ok=True)
            registro.write_text(json.dumps(datos, ensure_ascii=False, indent=1))
            return encontrado
    raise ValueError("Commons no devolvió ninguna imagen con licencia libre adecuada")


def _limpiar_html(valor) -> str:
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(valor or "")))
    t = re.sub(r"\(\s*(talk|discusión|usuario|contribs|contribuciones)[^)]*\)", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def _elegir_commons(paginas: list, exacto: bool) -> dict | None:
    for pag in paginas:
        info = (pag.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = _licencia_commons(meta)
        if not lic or info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        if not exacto and (info.get("width", 0) < 900 or info.get("width", 0) < info.get("height", 0)):
            continue  # en búsquedas: solo fotos horizontales y con resolución suficiente
        autor = _limpiar_html((meta.get("Artist") or {}).get("value", ""))
        descripcion = _limpiar_html((meta.get("ImageDescription") or {}).get("value", ""))[:180]
        return {
            "url": info.get("thumburl") or info.get("url"),
            "autor": (autor or "Autor desconocido")[:120] + " / Wikimedia Commons",
            "licencia": lic,
            "licencia_url": str((meta.get("LicenseUrl") or {}).get("value", "")),
            "fuente": info.get("descriptionurl", ""),
            "archivo_commons": pag.get("title", ""),
            "descripcion_commons": descripcion,
        }
    return None


def preparar_foto(art: Articulo, salida: Path, cache: Path, avisos: list) -> None:
    """Descarga (una sola vez) y optimiza la foto. Se sirve siempre desde la web propia."""
    img = art.imagen
    if not img:
        return
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return
    if img.get("commons") or img.get("buscar"):
        try:
            img = {**img, **resolver_commons(img, cache)}
            img["autor"] = _limpiar_html(img.get("autor"))
        except Exception as e:  # noqa: BLE001
            avisos.append(f"{art.ruta_fuente}: no se encontró la imagen en Commons ({e})")
            return
    origen = str(img.get("url") or img.get("archivo"))
    clave = hashlib.sha1(origen.encode()).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    original = cache / f"{clave}.orig"
    try:
        if not original.exists():
            if img.get("url"):
                pet = urllib.request.Request(str(img["url"]), headers=AGENTE_CABECERA)
                with urllib.request.urlopen(pet, timeout=20) as r:
                    datos = r.read(25 * 1024 * 1024 + 1)
                if len(datos) > 25 * 1024 * 1024:
                    raise ValueError("imagen de más de 25 MB")
            else:
                datos = (RAIZ / "static" / origen.lstrip("/")).read_bytes()
            Image.open(BytesIO(datos)).verify()
            original.write_bytes(datos)
        destino = salida / "img" / "n"
        destino.mkdir(parents=True, exist_ok=True)
        tamanos = {}
        for ancho in (1200, 640):
            f = destino / f"{clave}-{ancho}.jpg"
            en_cache = cache / f.name
            if not en_cache.exists():
                im = ImageOps.exif_transpose(Image.open(original)).convert("RGB")
                im.thumbnail((ancho, ancho * 2))
                im.save(en_cache, "JPEG", quality=80, optimize=True, progressive=True)
            shutil.copyfile(en_cache, f)
            from PIL import Image as _I
            with _I.open(en_cache) as hecho:
                tamanos[ancho] = hecho.size
        art.foto = {
            "src": f"/img/n/{clave}-1200.jpg", "src_peq": f"/img/n/{clave}-640.jpg",
            "ancho": tamanos[1200][0], "alto": tamanos[1200][1],
            "alt": img.get("alt") or img.get("descripcion_commons") or "", "pie": img.get("pie") or "",
            "autor": img.get("autor"), "licencia": LICENCIAS.get(img["licencia"], img["licencia"]),
            "licencia_url": img.get("licencia_url") or "", "fuente": img.get("fuente") or "",
            "original": original,
        }
    except Exception as e:  # noqa: BLE001 — sin foto se usa la cubierta tipográfica
        avisos.append(f"{art.ruta_fuente}: no se pudo preparar la imagen ({e})")


# ---------------------------------------------------------------- imágenes para compartir

def generar_og(art: Articulo, salida: Path, cache: Path) -> str:
    """Tarjeta 1200x630 tipográfica (sin fotos de terceros)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return ""
    foto = art.foto["original"] if art.foto else None
    clave = hashlib.sha1(f"v4|{art.titulo}|{art.seccion['slug']}|{art.fecha_iso}|{foto}".encode()).hexdigest()[:16]
    nombre = f"{clave}.png"
    destino = salida / "og" / nombre
    cacheado = cache / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not cacheado.exists():
        cache.mkdir(parents=True, exist_ok=True)
        W, H = 1200, 630
        color = art.seccion["color"]
        img = Image.new("RGB", (W, H), color)
        if foto:
            from PIL import ImageOps
            fondo = ImageOps.fit(ImageOps.exif_transpose(Image.open(foto)).convert("RGB"), (W, H - 96))
            img.paste(fondo, (0, 0))
            sombra = Image.new("L", (1, H - 96))
            for yy in range(H - 96):
                sombra.putpixel((0, yy), int(215 * max(0, (yy - 120) / (H - 216))))
            negro = Image.new("RGB", (W, H - 96), "#0B1A33")
            img.paste(negro, (0, 0), sombra.resize((W, H - 96)))
        d = ImageDraw.Draw(img)
        lora = ImageFont.truetype(str(RAIZ / "assets/og/Lora.ttf"), 64)
        try:
            lora.set_variation_by_axes([600])
        except Exception:  # noqa: BLE001
            pass
        inter = ImageFont.truetype(str(RAIZ / "assets/og/Inter-SemiBold.otf"), 28)
        marca = ImageFont.truetype(str(RAIZ / "assets/og/Inter-SemiBold.otf"), 34)
        if not foto:
            d.text((80, 70), f"{art.seccion['nombre']}  ·  {art.fecha:%d/%m/%Y %H:%M}", font=inter, fill="#E8ECF2")
        else:
            d.rectangle([80, 60, 80 + d.textlength(art.seccion["nombre"], font=inter) + 32, 108], fill=color)
            d.text((96, 66), art.seccion["nombre"], font=inter, fill="#FFFFFF")
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
        y = 150 if not foto else (H - 96 - 50 - 80 * len(lineas))
        for linea in lineas:
            d.text((80, y), linea, font=lora, fill="#FFFFFF")
            y += 80
        d.rectangle([0, H - 96, W, H], fill="#FFFFFF")
        logo = Image.open(RAIZ / "assets/og/logo.png").convert("RGBA")
        logo = logo.resize((int(logo.width * 46 / logo.height), 46))
        img.paste(logo, (80, H - 71), logo)
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
        self.avisos: list[str] = []

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
        base_ctx["ultima_hora"] = articulos[0] if articulos else None
        cache_og = RAIZ / ".cache" / "og"
        for a in articulos:
            preparar_foto(a, self.salida, RAIZ / ".cache" / "img", self.avisos)
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

        # Directo: vídeo y noticias minuto a minuto (el feed lo refresca el navegador)
        feed = [{"t": a.titulo, "e": a.entradilla, "u": a.url, "s": a.seccion["nombre"], "c": a.seccion["color"],
                 "h": a.fecha_iso, "a": a.autor, "f": a.foto["src_peq"] if a.foto else ""} for a in articulos[:40]]
        (self.salida / pre.lstrip("/") / "directo").mkdir(parents=True, exist_ok=True)
        (self.salida / pre.lstrip("/") / "directo" / "feed.json").write_text(
            json.dumps({"generado": self.ahora.isoformat(), "noticias": feed}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        self.escribir(f"{pre}/directo/", self.render(f"{t}/directo.html", **base_ctx, lista=articulos[:40],
                                                      seccion_actual="directo"), prioridad="0.9")

        # Equipo: una página general y una por agente
        agentes = cargar_agentes(codigo)
        for ag in agentes:
            ag["seccion_obj"] = next((s for s in ed["secciones"] if s["slug"] == ag["seccion"]), None)
            ag["articulos"] = [a for a in articulos if a.agente and a.agente["slug"] == ag["slug"]]
            self.escribir(f"{pre}/equipo/{ag['slug']}/", self.render(f"{t}/agente.html", **base_ctx, ag=ag,
                                                                     lista=ag["articulos"][:30]), prioridad="0.3")
        self.escribir(f"{pre}/equipo/", self.render(f"{t}/equipo.html", **base_ctx, agentes=agentes), prioridad="0.3")

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
    for a in c.avisos:
        print("aviso:", a)
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
