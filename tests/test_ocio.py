import importlib.util
import sys
import re
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build

class OcioTests(unittest.TestCase):
    def test_pages_render_in_existing_layout(self):
        cfg = build.cargar_config()
        with tempfile.TemporaryDirectory() as tmp:
            c = build.Constructor(cfg, Path(tmp))
            for code, ed in cfg["ediciones"].items():
                if ed.get("activa"):
                    c.edicion(code, [])
            c.finalizar()
            for route in ("juegos", "juegos/sudoku", "juegos/sopa-de-letras", "juegos/conexiones"):
                page = (Path(tmp) / route / "index.html").read_text()
                self.assertIn('class="cabecera"', page)
                self.assertIn('class="pie"', page)
                self.assertIn('href="' + cfg["url"] + "/" + route + '/"', page)
                self.assertIn('id="nt-ocio"', page)
            for route in ("index.html", "en/index.html", "directo/index.html", "buscar/index.html", "hemeroteca/index.html"):
                self.assertTrue((Path(tmp) / route).exists(), route)
            self.assertTrue((Path(tmp) / "ocio/ocio.js").exists())
            en = (Path(tmp) / "en/index.html").read_text()
            self.assertNotIn('href="/juegos/"', en)
            sitemap = (Path(tmp) / "sitemap.xml").read_text()
            self.assertIn(cfg["url"] + "/juegos/sudoku/", sitemap)
            self.assertFalse((Path(tmp) / "horoscopo" / "index.html").exists())
            self.assertNotIn("horoscopo", en)
            self.assertNotIn("/horoscopo/", (Path(tmp) / "index.html").read_text())
            self.assertNotIn("/tema/", sitemap)
            self.assertNotIn("/topic/", sitemap)

    def test_tag_pages_are_noindex_and_out_of_sitemap(self):
        cfg = build.cargar_config()
        tz = ZoneInfo(cfg["zona_horaria"])
        with tempfile.TemporaryDirectory() as tmp:
            c = build.Constructor(cfg, Path(tmp))
            for code, ed in cfg["ediciones"].items():
                if ed.get("activa"):
                    arts = build.cargar_articulos(cfg, code, tz, [], [])
                    c.edicion(code, arts)
            c.finalizar()
            def es_tema(p):
                rel = p.parent.relative_to(Path(tmp)).parts
                return rel[:1] == ("tema",) or rel[:2] == ("en", "topic")
            paginas_tema = [p for p in Path(tmp).rglob("index.html") if es_tema(p)]
            self.assertTrue(paginas_tema, "no se generaron páginas de tema")
            for p in paginas_tema:
                self.assertIn('content="noindex', p.read_text(), p)

    def test_styles_do_not_target_existing_layout(self):
        css = (ROOT / "static/ocio/ocio.css").read_text()
        for rule in re.sub(r"@media[^{}]+\{", "", css).split("}"):
            if not rule.strip():
                continue
            selectors = rule.split("{")[0]
            for selector in selectors.split(","):
                self.assertTrue(selector.strip().startswith("#nt-ocio"), selector)

if __name__ == "__main__":
    unittest.main()
