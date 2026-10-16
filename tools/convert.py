"""
Convierte las pantallas del mockup (.dc.html, el formato del lienzo de diseño)
a páginas HTML comunes que funcionan en cualquier hosting estático (GitHub Pages).

Uso (desde la carpeta del repo):
    python tools/convert.py

Lee src/socio.dc.html y src/panel.dc.html y escribe socio.html y panel.html.

Cómo funciona, en tres pasos:
1. Separa el archivo .dc.html en sus tres partes: los estilos (<helmet>),
   el template (lo que está dentro de <x-dc>) y la lógica (la clase Component).
2. Traduce la sintaxis del template a la de Vue 3, que es casi igual:
     <sc-if value="{{x}}">          ->  <template v-if="x">
     <sc-for list="{{xs}}" as="x">  ->  <template v-for="x in xs">
     onClick="{{fn}}"               ->  @click="fn"
     onChange="{{fn}}"              ->  @input="fn"   (en React, onChange salta con cada tecla)
     attr="{{x}}"                   ->  :attr="x"     (incluye ref="{{fn}}": Vue acepta refs con función)
     attr="texto {{x}} más"         ->  :attr="`texto ${x} más`"
   El texto con {{ x }} queda igual: Vue usa la misma sintaxis.
3. Arma una página con Vue (copiado en vendor/, sin depender de un CDN),
   una mini clase DCLogic que imita al componente de React del lienzo
   (setState, forceUpdate y los eventos de ciclo de vida) y la clase Component
   original, tal cual está en el mockup.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Eventos del formato del lienzo (estilo React) -> eventos de Vue
EVENTS = {"onClick": "@click", "onChange": "@input", "onInput": "@input"}

HOLE = re.compile(r"\{\{\s*(.*?)\s*\}\}")
TAG = re.compile(r"<([a-zA-Z][\w-]*)((?:\s+[^\s=<>\"']+(?:=\"[^\"]*\")?)*)\s*(/?)>")
ATTR = re.compile(r"([^\s=<>\"']+)(?:=\"([^\"]*)\")?")


def convert_attr(name, value):
    """Traduce un atributo. Devuelve el texto nuevo o None si hay que sacarlo."""
    if name.startswith("hint-"):          # pistas para el editor, no hacen falta
        return None
    if name == "defaultValue":            # valor inicial de un input
        name = "value"
    if value is None:
        return name
    whole = re.fullmatch(r"\{\{\s*(.*?)\s*\}\}", value)
    if name in EVENTS:
        if not whole:
            raise ValueError(f"Evento sin {{{{función}}}}: {name}={value}")
        return f'{EVENTS[name]}="{whole.group(1)}"'
    if whole:                              # attr="{{x}}" -> :attr="x"
        return f':{name}="{whole.group(1)}"'
    if "{{" in value:                      # texto mezclado -> template string de JS
        js = HOLE.sub(lambda m: "${" + m.group(1) + "}", value.replace("`", "\\`"))
        return f':{name}="`{js}`"'
    return f'{name}="{value}"'


def convert_tag(m):
    tag, attrs, selfclose = m.group(1), m.group(2) or "", m.group(3)
    pairs = [(a.group(1), a.group(2)) for a in ATTR.finditer(attrs)]
    d = dict(pairs)
    if tag == "sc-if":
        return f'<template v-if="{HOLE.fullmatch(d["value"]).group(1)}">'
    if tag == "sc-for":
        lst = HOLE.fullmatch(d["list"]).group(1)
        return f'<template v-for="{d.get("as", "item")} in {lst}">'
    out = [x for x in (convert_attr(n, v) for n, v in pairs) if x]
    return "<" + tag + "".join(" " + x for x in out) + (" /" if selfclose else "") + ">"


def convert_template(html):
    html = html.replace("</sc-if>", "</template>").replace("</sc-for>", "</template>")
    return TAG.sub(convert_tag, html)


def split_dc(src):
    helmet = re.search(r"<helmet>(.*?)</helmet>", src, re.S).group(1)
    body = re.search(r"<x-dc>(.*?)</x-dc>", src, re.S).group(1)
    body = re.sub(r"<helmet>.*?</helmet>", "", body, flags=re.S).strip()
    title = re.search(r"<title>(.*?)</title>", src, re.S).group(1)
    script = re.search(r"<script type=\"text/x-dc\"[^>]*>(.*?)</script>", src, re.S).group(1)
    return title, helmet, body, script


RUNTIME = r"""
// Imita lo mínimo del componente del lienzo (que es de React):
// props, state, setState, forceUpdate y los eventos de ciclo de vida.
class DCLogic {
  constructor(props) { this.props = props || {}; this.state = {}; }
  setState(patch) {
    if (typeof patch === 'function') patch = patch(this.state, this.props);
    if (this.__mark) this.__mark();     // guarda cómo estaba el state, para componentDidUpdate
    Object.assign(this.state, patch);   // el state es reactivo: Vue redibuja solo
  }
  // Redibuja aunque el state no cambie (lo usa el reloj del Modo entrenar)
  forceUpdate() { if (this.__force) this.__force(); }
}
"""

MOUNT = r"""
// Arranque: el state pasa a ser reactivo y renderVals() se recalcula cuando cambia.
(function () {
  var V = Vue;
  var inst = new Component({});
  inst.state = V.reactive(inst.state);
  var tick = V.ref(0);      // sube con forceUpdate y obliga a recalcular renderVals()
  var version = V.ref(0);   // sube con cada cambio, para avisar componentDidUpdate
  var prev = null;
  inst.__mark = function () {
    if (!prev) prev = Object.assign({}, inst.state);
    version.value++;
  };
  inst.__force = function () { inst.__mark(); tick.value++; };
  var vals = V.computed(function () { tick.value; return inst.renderVals(); });
  var keys = Object.keys(inst.renderVals());
  V.createApp({
    template: '#tpl',
    setup: function () {
      var out = {};
      keys.forEach(function (k) { out[k] = V.computed(function () { return vals.value[k]; }); });
      // Después de que Vue actualiza la pantalla, igual que React
      V.watch(version, function () {
        var p = prev; prev = null;
        if (inst.componentDidUpdate) inst.componentDidUpdate(inst.props, p || {});
      }, { flush: 'post' });
      V.onMounted(function () { if (inst.componentDidMount) inst.componentDidMount(); });
      V.onBeforeUnmount(function () { if (inst.componentWillUnmount) inst.componentWillUnmount(); });
      return out;
    }
  }).mount('#app');
})();
"""


def build(src_name, out_name, extra_css="", extra_js=""):
    src = (ROOT / "src" / src_name).read_text(encoding="utf-8")
    title, helmet, body, script = split_dc(src)
    # La imagen del logo vive en assets/ en vez del almacenamiento del lienzo
    body = re.sub(r"/_blob/[0-9a-f]{32}", "assets/logo.png", body)
    # Las fuentes van incluidas en el sitio en vez de pedirlas a Google Fonts
    helmet = re.sub(r'<link[^>]*fonts\.googleapis\.com[^>]*>',
                    '<link rel="stylesheet" href="assets/fonts/fonts.css">', helmet)
    tpl = convert_template(body)
    page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#0B0B0D">
<title>{title}</title>
<link rel="icon" href="assets/logo.png">
{helmet.strip()}
<style>{extra_css}</style>
</head>
<body>
<div id="app"></div>
<script type="text/x-template" id="tpl">
{tpl}
</script>
<script src="vendor/vue.global.prod.js"></script>
<script>{RUNTIME}</script>
<script>{script}</script>
<script>{MOUNT}</script>
<script>{extra_js}</script>
</body>
</html>
"""
    (ROOT / out_name).write_text(page, encoding="utf-8")
    print(f"OK  src/{src_name} -> {out_name}")


# En la PC la app del socio se ve como un celular centrado, achicado si la ventana es baja.
# En el celular ocupa toda la pantalla, como una app de verdad.
SOCIO_CSS = """
html,body{height:100%}
body{background:radial-gradient(60% 50% at 50% 0%,rgba(150,18,26,.18),rgba(0,0,0,0) 70%),#050506;margin:0;height:100vh;overflow:hidden;display:flex;align-items:center;justify-content:center}
.ph{flex:none;border-radius:36px;box-shadow:0 0 0 10px #18181B,0 30px 80px rgba(0,0,0,.6);transform:scale(var(--s,1));transform-origin:center}
@media (max-width:500px){
  body{display:block;overflow:auto;height:auto;background:#0B0B0D}
  .ph{width:100vw;height:100vh;height:100dvh;border-radius:0;box-shadow:none;transform:none}
  .inp{font-size:16px}  /* con menos de 16px, el iPhone hace zoom al tocar un campo */
}
"""

# Achica el "celular" para que entre entero en pantallas de notebook
SOCIO_JS = r"""
(function () {
  function fit() {
    var s = Math.min(1, (window.innerHeight - 48) / 844, (window.innerWidth - 48) / 390);
    document.documentElement.style.setProperty('--s', String(Math.max(.5, s)));
  }
  fit(); window.addEventListener('resize', fit);
})();
"""

if __name__ == "__main__":
    try:
        build("socio.dc.html", "socio.html", SOCIO_CSS, SOCIO_JS)
        build("panel.dc.html", "panel.html")
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
