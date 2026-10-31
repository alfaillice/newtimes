/* NewTimes.news: comportamiento mínimo. La web funciona sin JavaScript. */
(function () {
  "use strict";

  /* Horas relativas: "hace 12 min" para lo publicado hoy */
  function relativo(fecha) {
    var min = Math.round((Date.now() - fecha.getTime()) / 60000);
    if (min < 1) return "ahora";
    if (min < 60) return "hace " + min + " min";
    var h = Math.floor(min / 60);
    if (h < 24 && new Date().toDateString() === fecha.toDateString()) return "hace " + h + " h";
    return null;
  }
  function actualizarHoras() {
    document.querySelectorAll("time[data-rel]").forEach(function (t) {
      var d = new Date(t.getAttribute("datetime"));
      if (isNaN(d)) return;
      var r = relativo(d);
      if (!t.dataset.original) t.dataset.original = t.textContent;
      t.textContent = r || t.dataset.original;
      t.title = d.toLocaleString("es-ES", { dateStyle: "long", timeStyle: "short" });
    });
  }
  actualizarHoras();
  setInterval(actualizarHoras, 60000);

  /* Menú fijo: sombra y logo compacto cuando la cabecera sale de la pantalla */
  var centinela = document.querySelector(".centinela-menu");
  var menu = document.querySelector(".secciones");
  if (centinela && menu && "IntersectionObserver" in window) {
    new IntersectionObserver(function (e) {
      menu.classList.toggle("secciones--fijo", !e[0].isIntersecting);
    }).observe(centinela);
  }

  /* Carrusel de la portada */
  document.querySelectorAll(".carrusel").forEach(function (c) {
    var pista = c.querySelector(".carrusel__pista");
    var actual = c.querySelector("[data-actual]");
    if (!pista) return;
    var total = pista.children.length;
    /* Posiciones calculadas sobre las diapositivas reales: con zoom o escalado
       de pantalla el ancho puede ser fraccionario y clientWidth (entero) dejaba
       el texto a medio píxel, con aspecto borroso. */
    function ancho() { return pista.getBoundingClientRect().width || pista.clientWidth; }
    function indice() { return Math.round(pista.scrollLeft / ancho()); }
    function ir(i) {
      i = (i + total) % total;
      var d = pista.children[i];
      pista.scrollTo({ left: d ? d.offsetLeft - pista.children[0].offsetLeft : i * ancho() });
    }
    c.querySelectorAll("[data-dir]").forEach(function (b) {
      b.addEventListener("click", function () { ir(indice() + Number(b.dataset.dir)); });
    });
    pista.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); ir(indice() + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); ir(indice() - 1); }
    });
    var espera;
    pista.addEventListener("scroll", function () {
      clearTimeout(espera);
      espera = setTimeout(function () { if (actual) actual.textContent = indice() + 1; }, 80);
    }, { passive: true });

    /* Avance automático cada 7 segundos. Se detiene con el ratón o el foco encima,
       con la pestaña oculta, con el botón de pausa o si el sistema pide menos movimiento. */
    var boton = c.querySelector("[data-pausa]");
    if (total < 2) return;
    var reducir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var pausadoUsuario = reducir;
    var encima = false;
    var reloj = null;
    function pintarBoton() {
      if (!boton) return;
      boton.setAttribute("aria-label", pausadoUsuario ? "Reanudar el pase automático" : "Pausar el pase automático");
      boton.setAttribute("aria-pressed", pausadoUsuario ? "true" : "false");
      boton.classList.toggle("carrusel__boton--pausado", pausadoUsuario);
    }
    function arrancar() {
      parar();
      if (pausadoUsuario || encima || document.hidden) return;
      reloj = setInterval(function () { ir(indice() + 1); }, 7000);
    }
    function parar() { if (reloj) { clearInterval(reloj); reloj = null; } }
    c.addEventListener("mouseenter", function () { encima = true; parar(); });
    c.addEventListener("mouseleave", function () { encima = false; arrancar(); });
    c.addEventListener("focusin", function () { encima = true; parar(); });
    c.addEventListener("focusout", function (e) { if (!c.contains(e.relatedTarget)) { encima = false; arrancar(); } });
    pista.addEventListener("touchstart", function () { parar(); }, { passive: true });
    pista.addEventListener("touchend", function () { arrancar(); }, { passive: true });
    document.addEventListener("visibilitychange", arrancar);
    if (boton) {
      boton.hidden = false;
      boton.addEventListener("click", function () { pausadoUsuario = !pausadoUsuario; pintarBoton(); arrancar(); });
    }
    c.querySelectorAll("[data-dir]").forEach(function (b) { b.addEventListener("click", arrancar); });
    pintarBoton();
    arrancar();
  });

  /* Directo: la lista de última hora se actualiza sola cada minuto */
  var feed = document.querySelector("[data-feed]");
  if (feed) {
    var estadoDirecto = document.querySelector("[data-estado-directo]");
    var escapar = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
    var refrescar = function () {
      fetch(feed.dataset.feed + "?t=" + Date.now(), { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (d) {
        var conocidas = {};
        feed.querySelectorAll("[data-url]").forEach(function (li) { conocidas[li.dataset.url] = true; });
        var nuevas = (d.noticias || []).filter(function (n) { return !conocidas[n.u]; });
        nuevas.reverse().forEach(function (n) {
          var li = document.createElement("li");
          li.className = "minuto__item minuto__item--nuevo";
          li.dataset.url = n.u;
          var h = new Date(n.h);
          var hh = ("0" + h.getHours()).slice(-2) + ":" + ("0" + h.getMinutes()).slice(-2);
          li.innerHTML = '<time datetime="' + escapar(n.h) + '">' + hh + '</time><div><span class="minuto__seccion">' +
            escapar(n.s) + '</span><a href="' + escapar(n.u) + '">' + escapar(n.t) + "</a></div>";
          feed.insertBefore(li, feed.firstChild);
        });
        var ahora = new Date();
        if (estadoDirecto) {
          estadoDirecto.textContent = (nuevas.length ? nuevas.length + (nuevas.length === 1 ? " noticia nueva. " : " noticias nuevas. ") : "") +
            "Comprobado a las " + ("0" + ahora.getHours()).slice(-2) + ":" + ("0" + ahora.getMinutes()).slice(-2);
        }
      }).catch(function () {});
    };
    setInterval(refrescar, 60000);
  }

  /* Publicidad: activa cada bloque de AdSense de la página (sin scripts en línea) */
  document.querySelectorAll("ins.adsbygoogle").forEach(function () {
    try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) { /* sin anuncio */ }
  });

  /* Reabrir la ventana de consentimiento de cookies (Google Privacidad y mensajes) */
  document.querySelectorAll("[data-consentimiento]").forEach(function (b) {
    b.addEventListener("click", function () {
      window.googlefc = window.googlefc || {};
      window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
      window.googlefc.callbackQueue.push(function () {
        if (window.googlefc.showRevocationMessage) window.googlefc.showRevocationMessage();
      });
    });
  });

  /* Copiar enlace */
  document.querySelectorAll("[data-copiar]").forEach(function (b) {
    b.addEventListener("click", function () {
      var caja = b.closest("[data-compartir]");
      var url = caja.dataset.url;
      if (navigator.share) {
        navigator.share({ title: caja.dataset.titulo, url: url }).catch(function () {});
        return;
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          b.textContent = "Enlace copiado";
          setTimeout(function () { b.textContent = "Copiar enlace"; }, 2500);
        });
      }
    });
  });

  /* Búsqueda */
  var form = document.querySelector(".buscador");
  if (form) {
    var input = form.querySelector("input");
    var estado = document.querySelector("[data-estado]");
    var lista = document.querySelector("[data-resultados]");
    var indice = null;
    function norm(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
    function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    function cargar() {
      if (indice) return Promise.resolve(indice);
      return fetch(form.dataset.indice).then(function (r) { return r.json(); }).then(function (d) {
        indice = d.map(function (a) { a._n = norm(a.t + " " + a.e + " " + a.s + " " + (a.g || []).join(" ")); a._t = norm(a.t); return a; });
        return indice;
      });
    }
    function buscar(q) {
      var palabras = norm(q).split(/\s+/).filter(function (p) { return p.length > 1; });
      if (!palabras.length) { estado.textContent = ""; lista.innerHTML = ""; return; }
      estado.textContent = "Buscando…";
      cargar().then(function (idx) {
        var res = idx.filter(function (a) { return palabras.every(function (p) { return a._n.indexOf(p) !== -1; }); })
          .map(function (a) { var s = 0; palabras.forEach(function (p) { if (a._t.indexOf(p) !== -1) s += 2; }); return [s, a]; })
          .sort(function (x, y) { return y[0] - x[0]; })
          .slice(0, 50).map(function (x) { return x[1]; });
        estado.textContent = res.length ? res.length + (res.length === 1 ? " resultado" : " resultados") + " para «" + q + "»"
          : "No hay noticias con «" + q + "». Prueba con menos palabras o con otra forma de decirlo.";
        lista.innerHTML = res.map(function (a) {
          return '<li><a href="' + a.u + '">' + esc(a.t) + "</a><p>" + esc(a.e) + '</p><p class="meta"><span>' + esc(a.s) + "</span><span>" + a.f + "</span></p></li>";
        }).join("");
      }).catch(function () { estado.textContent = "No se ha podido cargar el buscador. Recarga la página para intentarlo de nuevo."; });
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      history.replaceState(null, "", "?q=" + encodeURIComponent(q));
      buscar(q);
    });
    var inicial = new URLSearchParams(location.search).get("q");
    if (inicial) { input.value = inicial; buscar(inicial); }
  }
})();
