CSS compilado de AdminLTE 4.0.0, copiado desde `frontend/AdminLTE-4.0.0/dist/css/`.
Ya incluye Bootstrap 5 compilado — no hace falta el paquete `bootstrap` aparte.

**No se usa `adminlte.js`**: sus componentes (PushMenu, Treeview) consultan
el DOM una sola vez al cargar (`querySelectorAll` + `addEventListener` por
elemento), lo que no funciona de forma confiable contra el DOM de una SPA
de React. El layout (`src/components/layout/`) reimplementa el único
comportamiento que se necesitaba (colapsar el sidebar) como estado de
React + clase en `<body>` — es exactamente lo que hacía ese JS.

Para actualizar: reconstruir `frontend/AdminLTE-4.0.0` y volver a copiar
`dist/css/adminlte.css` (+ `.map`) aquí.
