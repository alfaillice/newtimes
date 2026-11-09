#!/usr/bin/env python3
"""Informe diario de salud editorial y SEO de NewTimes.news. No usa la API ni gasta plan de Claude.

Mide lo que sí se puede medir sin Search Console: volumen y ritmo de publicación (la frescura es la señal
que más pesa en Google News y Discover), equilibrio por sección, calidad de titulares y fuentes, y estado
del sitemap de noticias en producción. Lo ejecuta el servidor cada noche y la revisión semanal lo lee.

Uso: python3 redaccion/seo_salud.py [--escribir] [--dias N]
     --escribir  guarda docs/salud-seo.md (el temporizador del servidor lo hace y publica)
"""
import argparse
import re
import statistics
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Madrid")


def cargar(ed):
    arts = []
    for ruta in (RAIZ / "content" / ed).glob("[0-9]*/[0-9]*/[0-9]*/*.md"):
        try:
            meta = yaml.safe_load(ruta.read_text(encoding="utf-8").split("\n---", 1)[0][3:]) or {}
            f = meta["fecha"]
            f = datetime.fromisoformat(f) if isinstance(f, str) else f
            meta["_f"] = (f if f.tzinfo else f.replace(tzinfo=TZ)).astimezone(TZ)
            arts.append(meta)
        except Exception:  # noqa: BLE001
            continue
    return sorted(arts, key=lambda m: m["_f"])


def mayor_hueco(arts, desde, hasta):
    """Mayor intervalo sin publicar entre las 7 y las 23 h (en horas)."""
    horas = [m["_f"] for m in arts if desde <= m["_f"] <= hasta and 7 <= m["_f"].hour < 23]
    if len(horas) < 2:
        return None
    return max((b - a).total_seconds() / 3600 for a, b in zip(horas, horas[1:]))


def informe(dias):
    ahora = datetime.now(TZ)
    out = [f"# Salud editorial y SEO · {ahora:%d/%m/%Y %H:%M}", ""]
    for ed, objetivo in (("es", 14), ("en", 8)):
        arts = cargar(ed)
        d1 = [m for m in arts if m["_f"] >= ahora - timedelta(hours=24)]
        dn = [m for m in arts if m["_f"] >= ahora - timedelta(days=dias)]
        out += [f"## Edición {ed.upper()}", "",
                f"- Últimas 24 h: **{len(d1)}** noticias (objetivo ≥ {objetivo}). Últimos {dias} días: {len(dn)}.",
                f"- Última publicación: {arts[-1]['_f']:%d/%m %H:%M}" if arts else "- Sin noticias."]
        hueco = mayor_hueco(arts, ahora - timedelta(hours=24), ahora)
        if hueco is not None:
            out.append(f"- Mayor hueco entre 7 y 23 h en las últimas 24 h: {hueco:.1f} h" + (" ⚠ (más de 3 h)" if hueco > 3 else ""))
        por_sec = Counter(m.get("seccion", "?") for m in dn)
        out.append("- Por sección (" + f"{dias} d): " + ", ".join(f"{s} {n}" for s, n in sorted(por_sec.items(), key=lambda x: -x[1])))
        if por_sec:
            flojas = [s for s, n in por_sec.items() if n * len(por_sec) < sum(por_sec.values()) / 2]
            if flojas:
                out.append(f"- ⚠ Secciones por debajo de la mitad de la media: {', '.join(flojas)}")
        largos = [m for m in d1 if len(m.get("titulo", "")) > 110]
        lt = [len(m.get("titulo", "")) for m in dn]
        if lt:
            out.append(f"- Titulares: mediana {int(statistics.median(lt))} caracteres; {sum(l > 70 for l in lt)} de {len(lt)} pasan de 70 (Google corta hacia los 60).")
        if largos:
            out.append(f"- ⚠ {len(largos)} titulares de las últimas 24 h pasan de 110 caracteres.")
        dominios = Counter()
        una = 0
        for m in dn:
            fs = m.get("fuentes") or []
            una += len(fs) == 1
            for f in fs:
                dominios[(urllib.parse.urlsplit(str(f.get("url", ""))).hostname or "?").removeprefix("www.")] += 1
        if dominios:
            out.append("- Fuentes más citadas: " + ", ".join(f"{d} {n}" for d, n in dominios.most_common(6)) + f". Noticias con una sola fuente: {una} de {len(dn)}.")
        out.append("")
    # Producción
    out += ["## Producción", ""]
    for url in ("https://newtimes.news/sitemap-noticias.xml", "https://newtimes.news/en/sitemap-noticias.xml"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "NewTimesSalud/1.0"}), timeout=20) as r:
                xml = r.read().decode("utf-8", "replace")
            n = xml.count("<url>")
            fechas = re.findall(r"<news:publication_date>([^<]+)", xml)
            ult = max(datetime.fromisoformat(f) for f in fechas).astimezone(TZ) if fechas else None
            out.append(f"- {url.split('.news')[1]}: HTTP 200, {n} URLs; última {ult:%d/%m %H:%M}" if ult else f"- {url}: 200 pero sin noticias ⚠")
        except Exception as e:  # noqa: BLE001
            out.append(f"- {url}: no se pudo leer ({e})")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--dias", type=int, default=7)
    a = ap.parse_args()
    t = informe(a.dias)
    print(t)
    if a.escribir:
        (RAIZ / "docs/salud-seo.md").write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main()
