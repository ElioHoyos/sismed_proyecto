# CONTEXTO DEL PROYECTO — Sistema de Gestión de Medicamentos
## Red de Salud Coronel Portillo

> **Claude Code: lee este archivo COMPLETO antes de escribir código.**
>
> **Versión 2** — actualizado tras analizar la BD completa (`sismed.sql`).
> El hallazgo del **ICI (`tformdet`)** cambió la prioridad del ETL. Ver §5.

---

## 1. EL PROBLEMA

El almacén de medicamentos de la Red de Salud Coronel Portillo usa **SISMED**
(Sistema Integrado de Medicamentos), un sistema del gobierno hecho en **FoxPro**.

Problemas de SISMED:
- Para ver el stock de un producto hay que entrar a varias ventanas.
- Tiene stock negativo y stock fantasma **dentro de sus propios datos**.
- **No calcula el CPMA** (Consumo Promedio Mensual Ajustado).

**El dolor principal:** el químico ("el doc") calcula el CPMA de los 89
establecimientos **a mano en Excel**, filtrando puesto por puesto.
Le toma **2 a 3 días** cada vez.

**Objetivo:** convertir esos 2-3 días en una consulta instantánea.

---

## 2. RESTRICCIONES (no negociables)

- **SISMED no se toca.** Es un sistema del gobierno. Nuestro sistema es de
  **solo lectura** sobre sus datos exportados.
- **El stock negativo/fantasma YA VIENE dentro de SISMED.** No podemos corregir
  la fuente. Se trata como **incidencia detectada y reportada**, nunca como dato
  válido silencioso.
- SISMED sigue siendo el sistema oficial para **DIREMID/DIGEMID**.
  Nuestro sistema **complementa**, no reemplaza.

---

## 3. LA RED

- **89 establecimientos** de salud + almacén central.
- **9 tienen SISMED instalado.** Se entra por **AnyDesk** a cada máquina, se
  exporta su DBF, y se sube al SISMED del almacén.
- **80 son rurales.** Vienen presencialmente al cierre mensual. El doc les
  imprime un formato desde SISMED, ellos lo "sinceran" (corrigen contra lo
  físico), y un informático de TI lo **digita a mano**.
- **Los 89 están registrados en el SISMED del almacén**, con código de
  establecimiento, micro red y red.

---

## 4. FÓRMULA DEL CPMA — ✅ VERIFICADA (397/397 productos, 100%)

Extraída del Excel real del doc (`DISPO_RED_mayoV2_ConCompra2026EXH.xlsx`,
hoja `DISPO_RED`) y **validada por código contra sus 397 productos: calza 100%**.

> ⚠️ El Excel del doc **no tiene ni una fórmula** — todos los valores están
> pegados a mano. Por eso le toma días. La fórmula se reconstruyó de los números.

```
SUMAMES  = suma del consumo de los últimos 12 meses
CONTADOR = nº de meses (de esos 12) con consumo > 0
CPMA     = SUMAMES / CONTADOR        ← NO se divide entre 12
```

**El "ajuste" está en el denominador:** se divide entre los meses que
*efectivamente tuvieron consumo*. Así un producto desabastecido o de rotación
estacional no sale con un promedio artificialmente bajo.

*Verificado:* Ácido Acetilsalicílico 500mg — 671 de consumo en solo 4 meses
→ CPMA = 671 / 4 = **167.75** (no 671/12 = 55.9).

**Ventana histórica: 12 meses fijos.** (Confirmado por Elio.)

### Disponibilidad
```
DISPO       = STOCK / CPMA                    → meses de stock
DISPO_TOTAL = (STOCK + Stock_AEM) / CPMA
```

### Clasificación (SITUACION) — umbrales derivados de los datos reales
| Condición            | Situación       |
|----------------------|-----------------|
| CPMA = 0             | SIN ROTACION    |
| DISPO = 0 y CPMA > 0 | DESABASTECIDO   |
| 0 < DISPO < 1        | CRITICO         |
| 1 ≤ DISPO ≤ 2        | SUBSTOCK        |
| 2 < DISPO ≤ 6        | NORMOSTOCK      |
| DISPO > 6            | SOBRESTOCK      |

### Requisición sugerida
```
Cantidad a requerir = (CPMA × meses_a_cubrir) − stock_disponible
```
`meses_a_cubrir` es **parámetro editable**, por defecto **3** (caso típico: el
motivo más frecuente en los datos es "REQ X 3 MESES"). Nunca negativo.

Implementado y probado en: `backend/app/services/cpma.py`

---

## 5. 🔑 HALLAZGO CLAVE: EL ICI (`tformdet`) ES LA FUENTE PRINCIPAL

**Esto cambió la arquitectura del ETL.** Al analizar la BD completa apareció
`tformdet` — el **Informe de Consumo Integrado**, el formato oficial de SISMED.

**Es el formato que se les imprime a los rurales para que "sinceren".**

### Por qué es la fuente principal (y no `tmovim`)

| Verificado en `tformdet_2024` | Resultado |
|---|---|
| Establecimientos distintos | **93** ← ¡TODA la red, no solo los 9! |
| Periodos | **12 meses completos de 2024** |
| Filas | 215.232 |

- `tmovim`/`tmovindet` = lo que el **almacén despachó** (visión del almacén).
- `tformdet` = lo que **cada establecimiento realmente tiene y consume**.

**El ICI resuelve DOS pendientes que bloqueaban el diseño:**

1. **`Stock_AEM` ya no hay que estimarlo.** Está en el ICI, por establecimiento
   y por mes. Usar **`STOCK_FIN`** (stock final del mes), no `SALDO` (que es el
   saldo *inicial*).
2. **La clasificación consumo-vs-ajuste ya viene resuelta** por el formato
   oficial. No hay que adivinarla de los `movrefe` (que era la parte más frágil
   del diseño).

### Estructura de `tformdet` (columnas reales)

**Llave:** `CODIGO_EJE` + `CODIGO_PRE` (establecimiento) + `TIPSUM` +
`ANNOMES` (periodo AAAAMM) + `CODIGO_MED` (producto)

| Grupo | Columnas |
|---|---|
| Saldos | `SALDO` (inicial), **`STOCK_FIN`** (final ← *este es el Stock_AEM*) |
| Ingresos | `INGRE`, `REINGRE` |
| **CONSUMO** ✅ | `VENTA`, `SIS`, `INTERSAN`, `EXO`, `SOAT`, `CREDHOSP`, `OTR_CONV`, `VENTAINST` |
| **NO es consumo** ❌ | `DEVOL`, `VENCIDO`, `MERMA`, `DISTRI`, `TRANSF`, `OTRAS_SAL`, `FAC_PERD`, `DEFNAC` |
| Otros | `REQ` (requerimiento), `PRECIO`, `TOTAL`, `FEC_EXP` |

```
consumo_mensual = VENTA + SIS + INTERSAN + EXO + SOAT
                  + CREDHOSP + OTR_CONV + VENTAINST
```
**Excluir mermas y transferencias del consumo** — si entran, el CPMA sale mal.
*(Confirmar la lista exacta con el doc antes de cerrar.)*

### ⚠️ Ojo con esto
- `tformdet` (sin sufijo) está **vacía**. Los datos viven en `tformdet_2024`
  (215.232 filas) y `tformdet_2025` (28.153 filas).
- **`tformdet_2025` tiene un solo periodo (`202605`).** O el resto de 2025 está
  en otra tabla, o la carga está incompleta. **Elio debe verificarlo.**

---

## 6. LOS DATOS (tablas relevantes de `sismed.sql`)

### ✅ SÍ importar
| Tabla | Qué es | Prioridad |
|---|---|---|
| `tformato` + `tformdet_*` | **ICI — la fuente principal** | **1** |
| `tmovim` + `tmovindet` | Movimientos del almacén (cabecera/detalle) | 2 |
| `mproducto` | Catálogo de productos | 2 |
| `mstkalmde` | **Stock del ALMACÉN** (= el `STOCK` de la fórmula) | 2 |
| `mmicrored` | Catálogo de micro redes | 3 |

### ❌ NO importar — carga manual única
- **`m_establecimiento`** — **la creó Elio a mano**, SISMED **no la genera**.
  Se carga una sola vez. El importador **no la toca**.

### ❌ NO importar — son basura histórica
La BD tiene ~150 tablas. La mayoría son **residuo del proceso manual** y el
sistema nuevo existe justamente para eliminarlas:

- **Reportes congelados como tablas:** `disponibilidad`, `aem_consumo`,
  `gestion_stock_red`, `disponibilidad_m`, `porc_dispo`, `porc_sismed`,
  `pfim_critico`, `pfim_substock`, `pfmi_normostock`, `pfim_stock`...
  → *Cada reporte que hizo Elio quedó como tabla.* Ya traen `sumames`, `cuenta`,
  `cpa`, `situacion` calculados a mano. **Nuestro sistema los reemplaza.**
- **Una tabla por establecimiento:** `abujao`, `yanamayo`, `bellavista`,
  `masisea`, `iparia`, `curiaca`... (decenas)
- **Versionadas por año:** `tmovim_2022/2023/2024/2025`, `mproducto_2022/2023/2024`,
  `consumo_2021/2022/2024/2025`, `mstockalm_*`, `precios_*`, `ici*` (por mes)...

> **Principio:** en el sistema nuevo **no hay tablas por reporte, ni por
> establecimiento, ni por año.** Un solo modelo; las vistas se calculan.

### ⚠️ Trampas de los datos (blindar en el ETL)
1. **Cantidades y precios guardados como TEXTO (`varchar`)** en SISMED:
   `movcantid`, `movprecio`, `movtotal`, `stksaldode`. Además vienen con
   **espacios de relleno** (ej. `'           0'`). **En nuestra BD van tipados
   como `DECIMAL`.** La conversión texto→número es el 1er punto de validación.
2. **SISMED no tiene NI UNA llave foránea.** Nada garantiza que un `medcod`
   exista en el catálogo → de ahí el stock fantasma. **Nuestra BD sí tiene FKs.**
3. Nombres crípticos de FoxPro (`movcoditip`, `almcodiorg`) → mapear a nombres
   legibles.

---

## 7. ARQUITECTURA

```
SISMED (FoxPro) → exportar DBF
       ↓
FastAPI (Python)          ← TODO el backend
    ├── etl/          importador DBF + validación
    ├── services/     motor CPMA (✅ ya implementado)
    ├── repositories/ acceso a datos
    ├── models/       entidades
    ├── api/          endpoints REST
    └── core/         config
       ↓
MySQL                     ← staging → limpias → calculadas
       ↓
Frontend (React/Angular)  ← solo consume la API
```

**Es una app WEB, no de escritorio.** Se despliega local (en una PC del almacén)
y se accede por navegador. FastAPI reemplaza a Spring Boot: mismo rol.

**Backend: N capas** (`api → services → repositories → models`, + `etl`).
**Frontend:** `components` (vista) + `services/api` (datos) + `hooks|store` (estado).
*(React/Angular no son MVC literal; esta es la separación equivalente.)*

### Flujo de importación

**Antes:** exportar DBF → importar a MySQL a mano → correr script → abrir otro
programa para ver KPIs.

**Ahora:** un endpoint `POST /api/importaciones`
1. Recibe el `.dbf` (multipart). Se lee con **`dbfread`** — *no hace falta pasar
   por MySQL primero*. Encoding probable: `latin-1` o `cp850`.
2. Vuelca **tal cual, en texto**, a tablas `stg_*`. Sin validar.
3. **Valida y promueve** a las tablas limpias:
   - texto → número (lo que falla va a la tabla `incidencia`)
   - el producto debe existir en el catálogo
   - establecimiento y fechas válidos
   - **lo que no pasa NO se descarta en silencio ni se fuerza a cero**
4. **Recalcula el CPMA** de lo afectado.
5. Devuelve resumen: *"215.232 filas ICI, 93 establecimientos. 12 incidencias.
   CPMA recalculado para 605 productos."*

Al terminar, **el dashboard ya está actualizado**.

### Idempotencia (crítico)
Cada importación tiene identidad (**establecimiento + periodo + versión**).
Recargar el mismo archivo **reemplaza, no duplica**.
Sin esto, el stock negativo lo crearíamos nosotros mismos.

---

## 8. ORDEN DE CONSTRUCCIÓN

1. ✅ Análisis de datos reales
2. ✅ Fórmula CPMA verificada (`backend/app/services/cpma.py`)
3. ✅ Esquema MySQL (`db/schema.sql`) — *falta añadir tablas del ICI*
4. ⬜ **Extender el esquema con `ici` / `stg_ici`** (§5)
5. ⬜ Cargar catálogos: `m_establecimiento` (manual) + `mproducto`
6. ⬜ **Importador ICI** (`app/etl/`) ← prioridad 1
7. ⬜ Importador movimientos (`tmovim`/`tmovindet`)
8. ⬜ API REST: disponibilidad, situación, requisición
9. ⬜ Frontend

---

## 9. PENDIENTES PARA ELIO

- [ ] **¿Por qué `tformdet_2025` solo tiene el periodo `202605`?** ¿Falta cargar
      el resto del año, o está en otra tabla?
- [ ] **Confirmar con el doc las columnas de consumo del ICI** (§5): ¿el consumo
      es `VENTA + SIS + INTERSAN + EXO + SOAT + CREDHOSP + OTR_CONV + VENTAINST`?
- [ ] **Confirmar `STOCK_FIN` vs `SALDO`** como fuente del `Stock_AEM`.
- [ ] Mapeo `CODIGO_PRE` (ICI) ↔ `cod_2000` (m_establecimiento) ↔ `almcodidst`
      (movimientos). ¿Son el mismo código? *Elio ya resolvió esto en sus joins
      manuales — recuperar esas consultas.*
- [ ] Confirmar que los **DBF exportados** tienen los mismos campos que las
      tablas MySQL analizadas.

> 💡 **Elio ya tenía consultas SQL con joins** que producían estos reportes
> (copiaba el resultado a Excel para su jefe). **Esas consultas son la base de
> los endpoints de la API — recuperarlas, no reinventarlas.**
