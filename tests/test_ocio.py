import importlib.util
import sys
import re
import tempfile
import unittest
from pathlib import Path

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
            for route in ("juegos", "juegos/sudoku", "juegos/sopa-de-letras", "juegos/conexiones", "horoscopo"):
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
