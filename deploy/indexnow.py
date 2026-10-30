#!/usr/bin/env python3
"""Envía a IndexNow las URL nuevas o modificadas del sitemap.
Lo ejecuta actualizar.sh tras cada construcción. Guarda lo ya enviado."""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WEB = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "public"
ESTADO = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / ".cache" / "indexnow.json"

cfg = yaml.safe_load((REPO / "config/site.yaml").read_text(encoding="utf-8"))
clave = cfg.get("indexnow_clave")
if not clave:
    sys.exit(0)
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
arbol = ET.parse(WEB / "sitemap.xml")
actual = {}
for u in arbol.getroot().findall("s:url", ns):
    loc = u.findtext("s:loc", namespaces=ns)
    actual[loc] = u.findtext("s:lastmod", default="", namespaces=ns)
enviado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
pendientes = [loc for loc, mod in actual.items() if enviado.get(loc) != mod][:10000]
if not pendientes:
    sys.exit(0)
host = cfg["url"].split("//", 1)[1].rstrip("/")
cuerpo = json.dumps({"host": host, "key": clave, "keyLocation": f"{cfg['url']}/{clave}.txt",
                     "urlList": pendientes}).encode()
pet = urllib.request.Request("https://api.indexnow.org/indexnow", data=cuerpo,
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(pet, timeout=20) as r:
        print(f"IndexNow: {len(pendientes)} URL enviadas (HTTP {r.status})")
    enviado.update({loc: actual[loc] for loc in pendientes})
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(enviado))
except Exception as e:  # noqa: BLE001 — se reintentará en la siguiente actualización
    print(f"IndexNow: error al enviar ({e})")
