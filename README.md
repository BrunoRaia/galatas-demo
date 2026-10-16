# Gálatas Rutinas · Demo

Prototipo navegable de la app de rutinas para Gálatas Gym.

- `index.html`: portada con los dos accesos.
- `socio.html`: app del socio (pensada para celular; en la PC se ve como un teléfono centrado).
- `panel.html`: panel de rutinas para los profes (pensado para PC).

Los datos son de ejemplo y no se guardan en ningún lado: si recargás la página, la demo vuelve a empezar.

DNIs de prueba: 11111111 (socio nuevo), 22222222 (sin mail en el legajo) y 33333333 (cuota vencida). Código: 123456.

## Estructura

```
index.html, socio.html, panel.html   páginas publicadas
assets/logo.png                      logo del gimnasio
assets/fonts/                        Anton y Poppins (licencia SIL OFL 1.1), sin depender de Google Fonts
vendor/vue.global.prod.js            Vue 3.4.38 (copiado, sin depender de un CDN)
src/*.dc.html                        pantallas originales del mockup (formato del lienzo de diseño)
tools/convert.py                     conversor src/*.dc.html -> socio.html / panel.html
.nojekyll                            le dice a GitHub Pages que publique los archivos tal cual
```

## Actualizar después de cambiar el mockup

1. Reemplazá `src/socio.dc.html` y/o `src/panel.dc.html` por la versión nueva.
2. Desde la carpeta del repo, corré `python tools/convert.py`.
3. Hacé commit y push. GitHub Pages publica solo, en uno o dos minutos.

`index.html` no se genera: se edita a mano.
