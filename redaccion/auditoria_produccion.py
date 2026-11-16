#!/usr/bin/env python3
"""Auditoría SEO técnica de NewTimes.news en producción. No usa la API ni gasta plan de Claude.

La ejecuta GitHub Actions (.github/workflows/auditoria-produccion.yml) cada lunes antes de la revisión
semanal y bajo demanda: así la revisión puede comprobar producción aunque su navegador no pueda abrir
newtimes.news. Lee robots.txt, sitemaps, ads.txt, portadas y las últimas noticias, y comprueba cabeceras,
etiquetas y datos estructurados. Solo lee: no cambia nada.

Uso: python3 redaccion/auditoria_produccion.py [--base https://newtimes.news] [--noticias 3]
Sale con código 1 si falla algo crítico (portada o sitemap de noticias inaccesibles o vacíos).
"""
import argparse
import gzip
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "NewTimes-auditoria/1.0 (+https://newtimes.news/como-trabajamos/)", "Accept-Encoding": "gzip"}
CABECERAS = ("content-encoding", "cache-control", "strict-transport-security", "x-content-type-options",
             "content-security-policy", "referrer-policy")


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def pedir(url, seguir=True):
    """(estado, cabeceras en minúsculas, texto, bytes transferidos)."""
    abridor = urllib.request.build_opener() if seguir else urllib.request.build_opener(SinRedireccion)
    try:
        with abridor.open(urllib.request.Request(url, headers=UA), timeout=30) as r:
            crudo, cab, estado = r.read(), {k.lower(): v for k, v in r.headers.items()}, r.status
    except urllib.error.HTTPError as e:
        crudo, cab, estado = e.read() or b"", {k.lower(): v for k, v in e.headers.items()}, e.code
    except Exception as e:  # noqa: BLE001
        return None, {}, str(e), 0
    texto = gzip.decompress(crudo) if cab.get("content-encoding") == "gzip" else crudo
    return estado, cab, texto.decode("utf-8", "replace"), len(crudo)


def meta(html, nombre):
    m = re.search(rf'<meta[^>]+(?:name|property)="{re.escape(nombre)}"[^>]+content="([^"]*)"', html)
    return m.group(1) if m else None


def tipos_ld(html):
    tipos = []
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            datos = json.loads(bloque)
        except ValueError:
            tipos.append("JSON-LD INVÁLIDO")
            continue
        for d in datos if isinstance(datos, list) else datos.get("@graph", [datos]):
            t = d.get("@type")
            tipos += t if isinstance(t, list) else [t]
    return tipos


def ld_articulo(html):
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(bloque)
        except ValueError:
            continue
        for x in d if isinstance(d, list) else d.get("@graph", [d]):
            if x.get("@type") in ("NewsArticle", ["NewsArticle"]):
                return x
    return {}


def pagina(base, ruta, out, criticos, etiqueta):
    url = f"{base}{ruta}{'&' if '?' in ruta else '?'}c={int(time.time())}"
    estado, cab, html, peso = pedir(url)
    if estado != 200:
        out.append(f"- ❌ {etiqueta} `{ruta}`: HTTP {estado} {html[:120] if estado is None else ''}")
        criticos.append(etiqueta)
        return None
    titulo = re.search(r"<title>(.*?)</title>", html, re.S)
    titulo = html_mod.unescape(" ".join(titulo.group(1).split())) if titulo else ""
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    hreflang = re.findall(r'hreflang="([^"]+)"', html)
    h1 = len(re.findall(r"<h1[\s>]", html))
    out.append(f"- ✅ {etiqueta} `{ruta}`: HTTP 200, {peso / 1024:.0f} KB transferidos"
               f" ({cab.get('content-encoding') or 'sin compresión'})")
    out.append(f"  - title ({len(titulo)} car.): {titulo}")
    desc = meta(html, "description")
    out.append(f"  - description: {len(desc) if desc else 'FALTA'} car. · canonical: {canon.group(1) if canon else 'FALTA'}"
               f" · h1: {h1} · hreflang: {', '.join(hreflang) or 'ninguno'}")
    out.append(f"  - robots: {meta(html, 'robots') or 'sin meta'} · og:image: {'sí' if meta(html, 'og:image') else 'FALTA'}"
               f" · JSON-LD: {', '.join(map(str, tipos_ld(html))) or 'ninguno'}")
    return html, cab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://newtimes.news")
    ap.add_argument("--noticias", type=int, default=3)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    ahora = datetime.now(timezone.utc)
    out = [f"# Auditoría de producción · {ahora:%d/%m/%Y %H:%M} UTC", "", f"Base: {base}", ""]
    criticos = []

    out += ["## Archivos de rastreo", ""]
    estado, _, robots, _ = pedir(f"{base}/robots.txt")
    mapas = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) if estado == 200 else []
    out.append(f"- robots.txt: HTTP {estado}; Sitemap declarados: {', '.join(mapas) or 'ninguno'}")
    if estado == 200 and re.search(r"(?im)^disallow:\s*/\s*$", robots):
        out.append("  - ❌ `Disallow: /` presente")
        criticos.append("robots")
    estado, _, ads, _ = pedir(f"{base}/ads.txt")
    lineas = [l for l in ads.splitlines() if l.strip() and not l.startswith("#")] if estado == 200 else []
    out.append(f"- ads.txt: HTTP {estado}; {len(lineas)} líneas de vendedor")
    estado, _, smap, _ = pedir(f"{base}/sitemap.xml?c={int(time.time())}")
    if estado == 200:
        urls = smap.count("<url>")
        out.append(f"- sitemap.xml: HTTP 200; {urls} URLs; sin lastmod: {urls - smap.count('<lastmod>')};"
                   f" /en/: {len(re.findall(r'<loc>https?://[^/<]+/en/', smap))}; /tema/: {smap.count('/tema/')}")
    else:
        out.append(f"- ❌ sitemap.xml: HTTP {estado}")
        criticos.append("sitemap.xml")

    recientes = []
    for ed, ruta in (("es", "/sitemap-noticias.xml"), ("en", "/en/sitemap-noticias.xml")):
        estado, _, xml, _ = pedir(f"{base}{ruta}?c={int(time.time())}")
        if estado != 200:
            out.append(f"- ❌ {ruta}: HTTP {estado}")
            criticos.append(ruta)
            continue
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        fechas = sorted(re.findall(r"<news:publication_date>([^<]+)</news:publication_date>", xml))
        idiomas = sorted(set(re.findall(r"<news:language>([^<]+)</news:language>", xml)))
        if not locs:
            out.append(f"- ❌ {ruta}: vacío (ninguna noticia en 48 h)")
            criticos.append(ruta)
            continue
        ultima = datetime.fromisoformat(fechas[-1]) if fechas else None
        horas = (ahora - ultima).total_seconds() / 3600 if ultima else None
        out.append(f"- {ruta}: {len(locs)} URLs; idioma {', '.join(idiomas)}; última {fechas[-1] if fechas else '?'}"
                   + (f" (hace {horas:.1f} h)" if horas is not None else ""))
        pares = re.findall(r"<loc>([^<]+)</loc>.*?<news:publication_date>([^<]+)</news:publication_date>", xml, re.S)
        recientes += [(f, l) for l, f in pares]

    out += ["", "## Portadas", ""]
    r = pagina(base, "/", out, criticos, "Portada ES")
    if r:
        out.append("  - Cabeceras: " + "; ".join(f"{c}: {r[1].get(c, 'FALTA')[:60]}" for c in CABECERAS))
    pagina(base, "/en/", out, criticos, "Portada EN")

    out += ["", "## Últimas noticias", ""]
    for _, url in sorted(recientes, reverse=True)[:a.noticias]:
        ruta = re.sub(r"^https?://[^/]+", "", url)
        r = pagina(base, ruta, out, criticos, "Noticia")
        if not r:
            continue
        art = ld_articulo(r[0])
        autor = art.get("author") or {}
        autor = autor[0] if isinstance(autor, list) and autor else autor
        imgs = art.get("image") or []
        out.append(f"  - NewsArticle: autor {autor.get('name', 'FALTA') if isinstance(autor, dict) else autor}"
                   f" · datePublished {art.get('datePublished', 'FALTA')} · dateModified {art.get('dateModified', 'FALTA')}"
                   f" · imágenes {len(imgs) if isinstance(imgs, list) else 1}")

    out += ["", "## Redirecciones heredadas (requieren el instalador del VPS)", ""]
    for ruta in ("/categoria/espana/", "/noticias/1/prueba/", "/es/noticias/1/prueba/"):
        estado, cab, _, _ = pedir(f"{base}{ruta}", seguir=False)
        out.append(f"- `{ruta}`: HTTP {estado} {cab.get('location', '')}")

    out += ["", "Críticos: " + (", ".join(criticos) if criticos else "ninguno")]
    texto = "\n".join(out)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    sys.exit(1 if criticos else 0)


if __name__ == "__main__":
    main()
