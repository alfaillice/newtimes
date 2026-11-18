import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build

AHORA = datetime(2026, 11, 18, 20, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def art(horas, seccion="espana", destacado=False, nombre=None):
    return SimpleNamespace(fecha=AHORA - timedelta(hours=horas), seccion={"slug": seccion},
                           destacado=destacado, nombre=nombre or f"{seccion}-{horas}")


class PortadaTests(unittest.TestCase):
    def test_nunca_noticias_de_hace_mas_de_36_horas(self):
        arts = [art(1), art(2), art(3), art(60, destacado=True), art(50, destacado=True)]
        elegidas = build.elegir_portada(arts, AHORA)
        self.assertTrue(all(a.fecha >= AHORA - timedelta(hours=36) for a in elegidas))

    def test_destacada_antigua_no_desplaza_a_la_fresca(self):
        vieja = art(20, "internacional", destacado=True)
        fresca = art(1, "economia")
        elegidas = build.elegir_portada([fresca, art(2, "sociedad"), art(3, "cultura"), vieja], AHORA)
        self.assertIs(elegidas[0], fresca)

    def test_destacada_reciente_abre_la_portada(self):
        grande = art(4, "internacional", destacado=True)
        elegidas = build.elegir_portada([art(1, "economia"), art(2, "sociedad"), grande], AHORA)
        self.assertIs(elegidas[0], grande)

    def test_maximo_dos_por_seccion_y_cinco_en_total(self):
        arts = [art(h, "espana") for h in range(1, 6)] + [art(h + 0.5, "deportes") for h in range(1, 5)]
        elegidas = build.elegir_portada(arts, AHORA)
        self.assertLessEqual(len(elegidas), 5)
        self.assertLessEqual(sum(a.seccion["slug"] == "espana" for a in elegidas), 2)

    def test_amplia_a_36_horas_solo_si_hay_pocas(self):
        elegidas = build.elegir_portada([art(1), art(30, "economia"), art(33, "sociedad")], AHORA)
        self.assertEqual(len(elegidas), 3)
        elegidas = build.elegir_portada([art(1), art(2, "economia"), art(3, "sociedad"), art(30, "cultura")], AHORA)
        self.assertEqual(len(elegidas), 3)

    def test_sin_noticias_recientes_no_deja_la_portada_vacia(self):
        self.assertEqual(len(build.elegir_portada([art(100, "espana"), art(101, "economia"), art(102, "cultura"), art(103, "sociedad")], AHORA)), 3)


if __name__ == "__main__":
    unittest.main()
