/* NewTimes.news: comportamiento mínimo. La web funciona sin JavaScript. */
(function () {
  "use strict";

  /* Textos según el idioma de la página (edición española o inglesa) */
  var EN = (document.documentElement.lang || "").slice(0, 2) === "en";
  function tx(es, en) { return EN ? en : es; }

  /* Horas relativas: "hace 12 min" para lo publicado hoy */
  function relativo(fecha) {
    var min = Math.round((Date.now() - fecha.getTime()) / 60000);
    if (min < 1) return tx("ahora", "just now");
    if (min < 60) return EN ? min + " min ago" : "hace " + min + " min";
    var h = Math.floor(min / 60);
    if (h < 24 && new Date().toDateString() === fecha.toDateString()) return EN ? h + " h ago" : "hace " + h + " h";
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

    /* Avance automático cada 7 segundos, siempre. Solo se detiene mientras alguien
       navega el carrusel con el teclado o lo arrastra con el dedo, y con la pestaña oculta. */
    if (total < 2) return;
    var teclado = false;
    var reloj = null;
    var pausado = false;
    var bPausa = c.querySelector("[data-pausa]");
    if (bPausa) bPausa.addEventListener("click", function () {
      pausado = !pausado;
      bPausa.setAttribute("aria-pressed", pausado ? "true" : "false");
      bPausa.setAttribute("aria-label", bPausa.dataset[pausado ? "textoReanudar" : "textoPausa"]);
      bPausa.querySelector(".i-pausa").hidden = pausado;
      bPausa.querySelector(".i-play").hidden = !pausado;
      pausado ? parar() : arrancar();
    });
    /* El ratón encima del carrusel también lo detiene (WCAG 2.2.2) */
    c.addEventListener("mouseenter", function () { parar(); });
    c.addEventListener("mouseleave", function () { arrancar(); });
    function arrancar() {
      parar();
      if (teclado || pausado || document.hidden) return;
      reloj = setInterval(function () { ir(indice() + 1); }, 7000);
    }
    function parar() { if (reloj) { clearInterval(reloj); reloj = null; } }
    c.addEventListener("focusin", function (e) {
      if (e.target.matches && e.target.matches(":focus-visible")) { teclado = true; parar(); }
    });
    c.addEventListener("focusout", function (e) { if (!c.contains(e.relatedTarget)) { teclado = false; arrancar(); } });
    pista.addEventListener("touchstart", function () { parar(); }, { passive: true });
    pista.addEventListener("touchend", function () { arrancar(); }, { passive: true });
    document.addEventListener("visibilitychange", arrancar);
    c.querySelectorAll("[data-dir]").forEach(function (b) { b.addEventListener("click", arrancar); });
    arrancar();
  });

  /* Directo: el vídeo arranca solo y sin sonido (los navegadores lo exigen) y se
     activa el sonido con un toque. Se habla con el reproductor por su API (postMessage). */
  var marcoVideo = document.querySelector("[data-video-directo]");
  if (marcoVideo) {
    var ifr = marcoVideo.querySelector("iframe");
    var capaSonido = marcoVideo.querySelector("[data-activar-sonido]");
    var avisoSonido = document.querySelector("[data-aviso-sonido]");
    var origenYT = "https://www.youtube-nocookie.com";
    var yt = { conectado: false, silenciado: true, estado: -1 };
    var conSonidoYa = false;
    var enviar = function (obj) {
      try { ifr.contentWindow.postMessage(JSON.stringify(obj), origenYT); } catch (e) { /* sin reproductor */ }
    };
    var orden = function (func, args) { enviar({ event: "command", func: func, args: args || [], id: 1, channel: "widget" }); };
    var escuchar = function () { enviar({ event: "listening", id: 1, channel: "widget" }); };
    window.addEventListener("message", function (e) {
      if (e.origin !== origenYT || e.source !== ifr.contentWindow) return;
      var d; try { d = typeof e.data === "string" ? JSON.parse(e.data) : e.data; } catch (x) { return; }
      if (!d || !d.event) return;
      yt.conectado = true;
      if (d.event === "infoDelivery" && d.info) {
        if (typeof d.info.muted === "boolean") yt.silenciado = d.info.muted;
        if (typeof d.info.playerState === "number") yt.estado = d.info.playerState;
      }
      if (d.event === "onStateChange" && typeof d.info === "number") yt.estado = d.info;
      if (pedido && yt.silenciado === false && yt.estado === 1) conSonido();
    });
    ifr.addEventListener("load", escuchar);
    var intentos = 0;
    var reloj = setInterval(function () { if (yt.conectado || ++intentos > 20) { clearInterval(reloj); return; } escuchar(); }, 500);

    var pedido = false;
    var conSonido = function () {
      conSonidoYa = true;
      if (capaSonido) capaSonido.hidden = true;
      if (avisoSonido) avisoSonido.hidden = true;
    };
    var activarSonido = function (conGesto) {
      if (conSonidoYa) return;
      pedido = true;
      orden("unMute"); orden("setVolume", [100]); orden("playVideo");
      setTimeout(function () {
        if (conSonidoYa) return;
        if (yt.silenciado === false && yt.estado === 1) { conSonido(); return; }
        // El navegador no lo ha permitido: el vídeo sigue en marcha sin sonido
        if (yt.estado !== 1) { orden("mute"); orden("playVideo"); }
        if (conGesto) {
          // Se retira el botón para dejar a mano los controles del propio reproductor
          if (capaSonido) capaSonido.hidden = true;
          if (avisoSonido) avisoSonido.hidden = false;
        }
      }, 1500);
    };
    if (capaSonido) {
      capaSonido.hidden = false;
      capaSonido.addEventListener("click", function (e) { e.preventDefault(); activarSonido(true); });
    }
    // El primer toque o tecla en cualquier parte de la página también activa el sonido
    var primerGesto = function () {
      document.removeEventListener("pointerdown", primerGesto, true);
      document.removeEventListener("keydown", primerGesto, true);
      activarSonido(false);
    };
    document.addEventListener("pointerdown", primerGesto, true);
    document.addEventListener("keydown", primerGesto, true);
    // Si el navegador ya permite sonido automático (algunos lo hacen con webs que visitas a menudo), se intenta sin esperar
    if (navigator.getAutoplayPolicy && navigator.getAutoplayPolicy("mediaelement") === "allowed") {
      var esperaInicio = setInterval(function () { if (yt.estado === 1) { clearInterval(esperaInicio); activarSonido(false); } }, 500);
      setTimeout(function () { clearInterval(esperaInicio); }, 15000);
    }
  }

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
          estadoDirecto.textContent = (nuevas.length ? nuevas.length + (nuevas.length === 1 ? tx(" noticia nueva. ", " new story. ") : tx(" noticias nuevas. ", " new stories. ")) : "") +
            tx("Comprobado a las ", "Checked at ") + ("0" + ahora.getHours()).slice(-2) + ":" + ("0" + ahora.getMinutes()).slice(-2);
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
          b.textContent = tx("Enlace copiado", "Link copied");
          setTimeout(function () { b.textContent = tx("Copiar enlace", "Copy link"); }, 2500);
        });
      }
    });
  });

  /* Instagram y TikTok no tienen enlace web para compartir: en el móvil se abre el menú
     de compartir del sistema (donde aparecen sus apps); en el ordenador se copia el enlace. */
  document.querySelectorAll("[data-red]").forEach(function (b) {
    b.addEventListener("click", function () {
      var caja = b.closest("[data-compartir]");
      var url = caja.dataset.url;
      var red = b.dataset.red;
      if (navigator.share) {
        navigator.share({ title: caja.dataset.titulo, url: url }).catch(function () {});
        return;
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          b.textContent = tx("Enlace copiado: pégalo en " + red, "Link copied: paste it in " + red);
          setTimeout(function () { b.textContent = red; }, 3000);
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
      estado.textContent = tx("Buscando…", "Searching…");
      cargar().then(function (idx) {
        var res = idx.filter(function (a) { return palabras.every(function (p) { return a._n.indexOf(p) !== -1; }); })
          .map(function (a) { var s = 0; palabras.forEach(function (p) { if (a._t.indexOf(p) !== -1) s += 2; }); return [s, a]; })
          .sort(function (x, y) { return y[0] - x[0]; })
          .slice(0, 50).map(function (x) { return x[1]; });
        estado.textContent = res.length ? (EN ? res.length + (res.length === 1 ? " result" : " results") + " for “" + q + "”"
               : res.length + (res.length === 1 ? " resultado" : " resultados") + " para «" + q + "»")
          : tx("No hay noticias con «" + q + "». Prueba con menos palabras o con otra forma de decirlo.",
               "No stories match “" + q + "”. Try fewer words or a different wording.");
        lista.innerHTML = res.map(function (a) {
          return '<li><a href="' + a.u + '">' + esc(a.t) + "</a><p>" + esc(a.e) + '</p><p class="meta"><span>' + esc(a.s) + "</span><span>" + a.f + "</span></p></li>";
        }).join("");
      }).catch(function () { estado.textContent = tx("No se ha podido cargar el buscador. Recarga la página para intentarlo de nuevo.", "The search could not be loaded. Reload the page to try again."); });
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
