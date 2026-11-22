"""Regla de las dos fuentes del redactor (sin red ni API).

Una noticia necesita FUENTES_MINIMAS medios distintos y admitidos. Si el tema trae menos,
candidatas_mismo_hecho busca otra pieza del mismo hecho entre los titulares ya leídos.
"""
import importlib.util
import unittest
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "redaccion" / "servidor" / "redactor.py"
spec = importlib.util.spec_from_file_location("redactor", RUTA)
redactor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redactor)


def pieza(url, titulo="", resumen="", medio="x"):
    return {"url": url, "medio": medio, "titulo": titulo, "resumen": resumen}


class SolidezTest(unittest.TestCase):
    def test_dos_medios_distintos_bastan(self):
        fuentes = [pieza("https://www.europapress.es/a"), pieza("https://www.bbc.co.uk/b")]
        self.assertEqual(redactor.solidez(fuentes), "ok")

    def test_una_agencia_sola_ya_no_basta(self):
        self.assertEqual(redactor.solidez([pieza("https://www.europapress.es/a")]), "atribuir")

    def test_el_mismo_medio_dos_veces_cuenta_como_uno(self):
        fuentes = [pieza("https://www.europapress.es/a"), pieza("https://www.europapress.es/b")]
        self.assertEqual(redactor.solidez(fuentes), "atribuir")

    def test_fuente_no_admitida(self):
        self.assertEqual(redactor.solidez([pieza("https://ejemplo-no-admitido.org/x")]), "no")

    def test_subdominio_cuenta_como_su_dominio(self):
        fuentes = [pieza("https://cincodias.elpais.com/a"), pieza("https://elpais.com/b")]
        self.assertEqual(redactor.solidez(fuentes), "atribuir")

    def test_minimo_configurable(self):
        original = redactor.FUENTES_MINIMAS
        try:
            redactor.FUENTES_MINIMAS = 1
            self.assertEqual(redactor.solidez([pieza("https://www.europapress.es/a")]), "ok")
        finally:
            redactor.FUENTES_MINIMAS = original


class CandidatasTest(unittest.TestCase):
    def setUp(self):
        self.tema = {
            "tema": "El Gobierno aprueba el decreto de vivienda para jóvenes",
            "items": [pieza("https://www.europapress.es/a",
                            "El Gobierno aprueba el decreto de vivienda para jóvenes", "")],
        }

    def test_busca_otro_medio_del_mismo_hecho(self):
        pool = [
            pieza("https://www.europapress.es/a", "El Gobierno aprueba el decreto de vivienda para jóvenes", ""),
            pieza("https://elpais.com/x", "Gobierno aprueba decreto de vivienda para jóvenes", ""),
            pieza("https://www.bbc.co.uk/y", "Football results from the weekend", ""),
        ]
        cand = redactor.candidatas_mismo_hecho(self.tema, pool)
        self.assertEqual([c["url"] for c in cand], ["https://elpais.com/x"])

    def test_no_repite_el_mismo_medio(self):
        pool = [pieza("https://www.europapress.es/c", "El Gobierno aprueba el decreto de vivienda", "")]
        self.assertEqual(redactor.candidatas_mismo_hecho(self.tema, pool), [])

    def test_sin_parecido_no_hay_candidatas(self):
        pool = [pieza("https://elpais.com/z", "La selección celebra la victoria en Lisboa", "")]
        self.assertEqual(redactor.candidatas_mismo_hecho(self.tema, pool), [])


if __name__ == "__main__":
    unittest.main()
