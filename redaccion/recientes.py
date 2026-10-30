#!/usr/bin/env python3
"""Lista las noticias publicadas en las últimas horas (por defecto 48)
para que la redacción no repita asuntos.

Uso: python3 redaccion/recientes.py [horas] [edicion]
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ = Path(__file__).resolve().parent.parent
horas = int(sys.argv[1]) if len(sys.argv) > 1 else 48
edicion = sys.argv[2] if len(sys.argv) > 2 else "es"
tz = ZoneInfo("Europe/Madrid")
limite = datetime.now(tz) - timedelta(hours=horas)

filas = []
for ruta in (RAIZ / "content" / edicion).glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.md"):
    texto = ruta.read_text(encoding="utf-8")
    try:
        meta = yaml.safe_load(texto.split("\n---", 1)[0][3:]) or {}
        f = meta["fecha"]
        f = datetime.fromisoformat(f) if isinstance(f, str) else f
        f = (f if f.tzinfo else f.replace(tzinfo=tz)).astimezone(tz)
    except Exception:  # noqa: BLE001
        continue
    if f >= limite:
        filas.append((f, meta.get("seccion", "?"), meta.get("titulo", ruta.stem)))

filas.sort(reverse=True)
print(f"{len(filas)} noticias en las últimas {horas} h ({edicion}):")
for f, s, t in filas:
    print(f"{f:%d/%m %H:%M}  [{s}]  {t}")
