"""Páginas de ocio aisladas de las rutas editoriales."""
def construir(c, base_ctx):
    paginas = [
        ("juegos", "juegos", "Juegos diarios", "Tres retos para disfrutar de una pausa."),
        ("juegos/sudoku", "sudoku", "Sudoku", "Completa la cuadrícula sin repetir números en filas, columnas ni bloques."),
        ("juegos/sopa-de-letras", "sopa-de-letras", "Sopa de letras", "Encuentra las palabras: marca su primera y última letra en línea recta."),
        ("juegos/conexiones", "conexiones", "Conexiones", "Elige cuatro palabras que tengan algo en común y encuentra los cuatro grupos."),
        ("horoscopo", "horoscopo", "Horóscopo diario", "Doce lecturas breves para el día, solo como entretenimiento."),
    ]
    for ruta, modo, titulo, descripcion in paginas:
        c.escribir("/" + ruta + "/", c.render("es/ocio.html", **base_ctx,
                   ocio_ruta=ruta, modo=modo, titulo=titulo, descripcion=descripcion),
                   prioridad="0.4", lastmod=c.ahora)
