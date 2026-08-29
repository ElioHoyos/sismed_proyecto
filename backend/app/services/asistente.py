"""
Asistente de consultas 100% local, por REGLAS — sin LLM, sin servicios externos,
sin internet.

Principio no negociable: el asistente NUNCA calcula ni inventa datos. Reconoce la
intención de la pregunta (palabras clave / sinónimos en español), llama a los
repositorios ya existentes y probados, y redacta la respuesta con los datos que
devolvió el backend. Todos los números salen del código ya validado contra SISMED.

Es determinista: misma pregunta → misma clasificación y misma respuesta.
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calc_cpma import CalcCpma
from app.models.producto import Producto
from app.models.stock_almacen import ORIGEN_ALMACEN, Stock
from app.repositories.disponibilidad_repository import (
    listar_disponibilidad_red,
    obtener_requisicion,
)
from app.repositories.asistente_repository import marcar_reformulacion, registrar_no_reconocida
from app.repositories.importacion_repository import listar_pendientes
from app.repositories.stock_repository import (
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    VENTANA_PROXIMO_DIAS,
    listar_stock,
    listar_vencimientos,
)
from app.services.cpma import MESES_A_CUBRIR_DEFAULT

LIMITE_FILAS = 15

SUGERENCIAS = [
    "¿Qué vence pronto?",
    "¿Qué está en negativo?",
    "¿Qué está desabastecido?",
    "¿Quién falta cargar?",
    "Stock de metamizol",
]

# ── Normalización y utilidades ────────────────────────────────────────────

def _norm(texto: str) -> str:
    """Normaliza como escribe el doc de verdad: minúsculas, sin tildes/ñ, sin
    signos de puntuación, espacios colapsados. Así '¿Qué está x vencer?' y
    'que esta por vencer' se tratan igual."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)  # puntuación → espacio
    return re.sub(r"\s+", " ", t).strip()


def _num(valor) -> str:
    """Formato es-PE: miles con punto, decimales con coma; sin decimales si es entero."""
    try:
        d = Decimal(str(valor))
    except Exception:
        return str(valor)
    if d == d.to_integral_value():
        return f"{int(d):,}".replace(",", ".")
    return f"{d:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if isinstance(d, date) else "—"


def _tabla(columnas: list[str], filas: list[list[str]], total: int) -> dict:
    return {"columnas": columnas, "filas": filas[:LIMITE_FILAS], "total": total}


def _vacia() -> dict:
    return {"columnas": [], "filas": [], "total": 0}


# ── Diccionario de intención (fácil de ampliar con lo que salga del registro de
#    preguntas no reconocidas). Orden = prioridad: lo más específico primero.
#    Cada frase se compara como subcadena; además, las palabras sueltas (una sola
#    palabra, ≥5 letras) se comparan de forma difusa para tolerar errores de
#    tipeo. Parte de variantes obvias del español, jerga y abreviaturas del
#    rubro; NO de frases inventadas del doc — esas se enseñan con el registro. ──

INTENCIONES: list[tuple[str, list[str]]] = [
    ("faltantes", [
        "falta cargar", "faltan cargar", "falta por cargar", "quien falta", "quienes faltan",
        "que falta", "puestos faltan", "que puestos", "quien no ha cargado", "quienes no han cargado",
        "pendientes de carga", "establecimientos faltan", "no cargaron", "no han cargado",
        "sin cargar", "por cargar", "quien no cargo", "quienes no cargaron", "pendientes",
    ]),
    ("vencidos", [
        "vencido", "vencidos", "vencida", "vencidas", "caducado", "caducados", "caduco",
        "expirado", "expirados", "ya vencio", "ya vencieron", "vencio", "malogrado",
    ]),
    ("proximos_vencer", [
        "proximo a vencer", "proximos a vencer", "por vencer", "vence pronto", "vencen pronto",
        "van a vencer", "va a vencer", "pronto a vencer", "proximos vencimientos", "que vence",
        "por caducar", "caducan", "vencimientos", "vencer", "a punto de vencer", "proximos",
        "por caducarse", "por vto", "por vcto", "prox vto", "proximo vencimiento", "vencimiento",
    ]),
    ("stock_negativo", [
        "negativ", "negativo", "negativos", "en rojo", "saldo negativo", "en negativo",
        "numeros rojos", "rojos", "por debajo de cero", "menos de cero", "bajo cero",
    ]),
    ("desabastecidos", [
        "desabastec", "desabastecido", "desabastecidos", "sin stock", "sin stk", "agotado",
        "agotados", "agotada", "agotadas", "no hay", "hace falta", "sin existencias",
        "falta de", "desabasto", "no queda", "ya no hay", "se acabo", "sin unidades",
    ]),
    ("requisicion", [
        "requisic", "requisicion", "requisiciones", "cuanto pido", "cuanto pedir",
        "cuanto solicito", "cuanto compro", "cuanto comprar", "cuanto debo pedir", "pedido de",
        "cuanto ordeno", "cuanto requiero", "cuanto necesito", "cuanto hay que pedir",
        "que pido de", "pedir de",
    ]),
    ("cpma", [
        "cpma", "cpa", "consumo promedio", "promedio de consumo", "consumo mensual",
        "promedio mensual", "consumo medio",
    ]),
    ("situacion_producto", [
        "como esta", "como estan", "como anda", "situacion de", "situacion del",
        "disponibilidad de", "estado de", "como se encuentra", "que tal esta", "como va",
    ]),
    ("stock_producto", [
        "stock", "stk", "unidades", "cuanto hay", "cuantas unidades", "cuanto tengo",
        "existencias", "saldo de", "cuanto queda", "cuanta cantidad", "que cantidad",
        "cuantos hay", "inventario de",
    ]),
]

# Frase canónica por intención, para el "¿quisiste decir…?" (clicable → se reconoce).
INTENCION_EJEMPLO: dict[str, str] = {
    "faltantes": "¿Quién falta cargar?",
    "vencidos": "¿Qué está vencido?",
    "proximos_vencer": "¿Qué está por vencer?",
    "stock_negativo": "¿Qué está en negativo?",
    "desabastecidos": "¿Qué está desabastecido?",
    "requisicion": "¿Cuánto pido de paracetamol?",
    "cpma": "CPMA de paracetamol",
    "situacion_producto": "¿Cómo está el paracetamol?",
    "stock_producto": "Stock de paracetamol",
}

UMBRAL_CLASIF = 0.86  # similitud para dar por buena una palabra mal escrita
UMBRAL_CERCANA = 0.72  # similitud (menor) para sugerir "¿quisiste decir?"


def _fuzzy_token(tokens: list[str], palabra: str, umbral: float) -> float:
    """Mejor similitud entre `palabra` y algún token de la pregunta."""
    return max((_sim(tok, palabra) for tok in tokens if len(tok) >= 4), default=0.0)


def _clasificar(t: str) -> str | None:
    tokens = t.split()
    for intencion, claves in INTENCIONES:
        # 1) Subcadena exacta (cubre frases y prefijos como "negativ", "desabastec").
        if any(clave in t for clave in claves):
            return intencion
        # 2) Palabra suelta mal escrita (fuzzy) — "desabastesido", "vencidoss".
        for clave in claves:
            if " " not in clave and len(clave) >= 5 and _fuzzy_token(tokens, clave, UMBRAL_CLASIF) >= UMBRAL_CLASIF:
                return intencion
    return None


def _cercanas(t: str, n: int = 3) -> list[str]:
    """Intenciones más parecidas cuando nada calzó del todo — para sugerir en vez
    de rendirse. Devuelve intenciones con similitud en la banda 'cerca pero no'."""
    tokens = [tok for tok in t.split() if len(tok) >= 4]
    if not tokens:
        return []
    puntuadas: list[tuple[float, str]] = []
    for intencion, claves in INTENCIONES:
        mejor = 0.0
        for clave in claves:
            for parte in clave.split():
                if len(parte) >= 4:
                    mejor = max(mejor, _fuzzy_token(tokens, parte, UMBRAL_CERCANA))
        puntuadas.append((mejor, intencion))
    puntuadas.sort(reverse=True)
    return [intencion for score, intencion in puntuadas if score >= UMBRAL_CERCANA][:n]


# ── Extracción de parámetros ──────────────────────────────────────────────

_STOPWORDS_PROD = {
    "stock", "saldo", "saldos", "unidades", "cuanto", "cuanta", "cuantas", "cuantos", "hay",
    "tengo", "queda", "quedan", "existencias", "situacion", "estado", "disponibilidad",
    "como", "esta", "estan", "anda", "vence", "vencer", "vencido", "vencidos", "proximo",
    "proximos", "negativo", "negativos", "desabastecido", "desabastecidos", "requisicion",
    "cuento", "pido", "pedir", "pedido", "solicito", "compro", "comprar", "cpma", "consumo",
    "promedio", "mensual", "producto", "medicamento", "medicamentos", "insumo", "insumos",
    "petitorio", "sis", "para", "del", "los", "las", "que", "con", "por", "una", "uno",
    "quiero", "necesito", "dame", "muestra", "ver", "cual", "cuales", "esta", "hoy", "pronto",
}


def _tokens(texto: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", texto) if w]


def _sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def _resolver_producto(db: Session, t: str) -> Producto | None:
    """Busca el producto por nombre parcial o código en el catálogo, tolerante a
    errores de tipeo (similitud difusa). Devuelve None si nada calza razonable."""
    palabras = [w for w in _tokens(t) if len(w) >= 4 and w not in _STOPWORDS_PROD]
    if not palabras:
        return None

    productos = db.scalars(select(Producto)).all()

    # 1) Match exacto por código (medcod o código SIGA)
    for w in palabras:
        for p in productos:
            if w == (p.medcod or "").lower() or w == (p.codigo_siga or "").lower():
                return p

    # 2) Match difuso por token del nombre
    mejor: Producto | None = None
    mejor_score = 0.0
    for p in productos:
        nombre_tokens = [x for x in _tokens(_norm(p.nombre)) if len(x) >= 3]
        for w in palabras:
            for nt in nombre_tokens:
                s = _sim(w, nt)
                if s > mejor_score:
                    mejor_score, mejor = s, p
    return mejor if mejor_score >= 0.82 else None


def _detectar_tipo(t: str) -> str | None:
    tokens = t.split()
    if re.search(r"\binsumos?\b", t) or _fuzzy_token(tokens, "insumos", UMBRAL_CLASIF) >= UMBRAL_CLASIF:
        return "I"
    # Tolera "medicamnto", "medicamentos", "medicina".
    if re.search(r"\bmedic", t) or any(
        _fuzzy_token(tokens, w, UMBRAL_CLASIF) >= UMBRAL_CLASIF for w in ("medicamento", "medicamentos", "medicina")
    ):
        return "M"
    return None


def _detectar_financiamiento(t: str) -> str | None:
    if re.search(r"\bpetitorio\b", t):
        return "P"
    if re.search(r"\bsis\b", t):
        return "_"
    return None


# ── Handlers por intención ────────────────────────────────────────────────

def _h_proximos(db, t):
    tipo, fin = _detectar_tipo(t), _detectar_financiamiento(t)
    filas = listar_vencimientos(db, date.today(), ESTADO_PROXIMO, tipo=tipo, financiamiento=fin)
    if not filas:
        texto = f"No hay lotes próximos a vencer en los próximos {VENTANA_PROXIMO_DIAS} días."
    else:
        p = filas[0]
        texto = (
            f"Hay {len(filas)} lote(s) próximos a vencer en los próximos {VENTANA_PROXIMO_DIAS} días. "
            f"El más urgente es {p['producto_nombre']} (lote {p['lote']}), {_num(p['saldo'])} unidades, "
            f"vence el {_fecha(p['fecha_vcto'])} — en {p['dias_restantes']} días."
        )
    tabla = _tabla(
        ["Medicamento", "Lote", "Vence", "Días", "Unidades"],
        [[f["producto_nombre"], f["lote"], _fecha(f["fecha_vcto"]), str(f["dias_restantes"]), _num(f["saldo"])] for f in filas],
        len(filas),
    )
    enlace = {"pagina": "vencimientos", "filtros": _limpio({"estado": "PROXIMO_A_VENCER", "tipo": tipo, "financiamiento": fin})}
    return texto, tabla, enlace


def _h_vencidos(db, t):
    tipo, fin = _detectar_tipo(t), _detectar_financiamiento(t)
    filas = listar_vencimientos(db, date.today(), ESTADO_VENCIDO, tipo=tipo, financiamiento=fin)
    if not filas:
        texto = "No hay lotes vencidos con stock disponible en el almacén."
    else:
        p = filas[0]
        texto = (
            f"Hay {len(filas)} lote(s) vencidos con stock en el almacén. El más antiguo es "
            f"{p['producto_nombre']} (lote {p['lote']}), venció el {_fecha(p['fecha_vcto'])} "
            f"(hace {abs(p['dias_restantes'])} días), {_num(p['saldo'])} unidades."
        )
    tabla = _tabla(
        ["Medicamento", "Lote", "Venció", "Días", "Unidades"],
        [[f["producto_nombre"], f["lote"], _fecha(f["fecha_vcto"]), str(f["dias_restantes"]), _num(f["saldo"])] for f in filas],
        len(filas),
    )
    enlace = {"pagina": "vencimientos", "filtros": _limpio({"estado": "VENCIDO", "tipo": tipo, "financiamiento": fin})}
    return texto, tabla, enlace


def _h_stock_negativo(db, t):
    tipo, fin = _detectar_tipo(t), _detectar_financiamiento(t)
    filas = listar_stock(db, ORIGEN_ALMACEN, solo_negativos=True, tipo=tipo, financiamiento=fin)
    if not filas:
        texto = "No hay saldos negativos en el almacén."
    else:
        p = filas[0]
        texto = (
            f"Hay {len(filas)} saldo(s) negativo(s) a nivel de lote en el almacén. "
            f"El más negativo es {p['producto_nombre']} (lote {p['lote']}): {_num(p['saldo'])} "
            f"— el total del producto es {_num(p['saldo_consolidado'])}, por eso queda oculto en el consolidado."
        )
    tabla = _tabla(
        ["Medicamento", "Lote", "Saldo", "Consolidado"],
        [[f["producto_nombre"], f["lote"] or "—", _num(f["saldo"]), _num(f["saldo_consolidado"])] for f in filas],
        len(filas),
    )
    enlace = {"pagina": "stock", "filtros": _limpio({"origen": "ALMACEN", "soloNegativos": True, "tipo": tipo, "financiamiento": fin})}
    return texto, tabla, enlace


def _h_stock_producto(db, t):
    producto = _resolver_producto(db, t)
    if producto is None:
        return (
            "¿De qué producto quieres el stock? Escribe el nombre o el código, por ejemplo: “stock de metamizol”.",
            _vacia(),
            None,
        )
    lotes = db.execute(
        select(Stock)
        .where(Stock.origen == ORIGEN_ALMACEN, Stock.producto_id == producto.id)
        .order_by(Stock.fecha_vcto)
    ).scalars().all()
    total = sum((Decimal(str(l.cantidad)) for l in lotes), Decimal(0))
    con_saldo = [l for l in lotes if Decimal(str(l.cantidad)) != 0]
    siga = producto.codigo_siga or "—"
    texto = (
        f"{producto.nombre} (SIGA {siga}): {_num(total)} unidades en el almacén, "
        f"en {len(con_saldo)} lote(s) con saldo."
    )
    tabla = _tabla(
        ["Lote", "Vence", "Unidades"],
        [[l.lote or "—", _fecha(l.fecha_vcto), _num(l.cantidad)] for l in con_saldo],
        len(con_saldo),
    )
    enlace = {"pagina": "stock", "filtros": {"origen": "ALMACEN", "soloNegativos": False, "busqueda": producto.medcod}}
    return texto, tabla, enlace


def _h_desabastecidos(db, t):
    tipo, fin = _detectar_tipo(t), _detectar_financiamiento(t)
    filas = listar_disponibilidad_red(db, situacion="DESABASTECIDO")[1]
    if tipo:
        filas = [f for f in filas if f.get("medtip") == tipo]
    if fin:
        filas = [f for f in filas if f.get("medpet") == fin]
    if not filas:
        texto = "No hay productos desabastecidos en la red (con los datos cargados)."
    else:
        texto = f"Hay {len(filas)} producto(s) desabastecidos en la red."
    tabla = _tabla(
        ["Medicamento", "Stock Red", "Almacén (AEM)", "CPMA", "Cobertura total (meses)"],
        [[f["producto_nombre"], _num(f["stock_red"]), _num(f["stock_aem"]), _num(f["cpma"]), _num(f["dispo_total"])] for f in filas],
        len(filas),
    )
    enlace = {"pagina": "disponibilidad", "filtros": _limpio({"vista": "red", "situacion": "DESABASTECIDO", "tipo": tipo, "financiamiento": fin})}
    return texto, tabla, enlace


def _fila_red_producto(db, producto):
    filas = listar_disponibilidad_red(db, producto_cod=producto.medcod)[1]
    return filas[0] if filas else None


def _h_situacion_producto(db, t):
    producto = _resolver_producto(db, t)
    if producto is None:
        return ("¿De qué producto quieres la situación? Por ejemplo: “cómo está el aciclovir”.", _vacia(), None)
    f = _fila_red_producto(db, producto)
    if f is None:
        return (f"No hay datos de disponibilidad para {producto.nombre} (aún no se calculó su CPMA).", _vacia(), None)
    texto = (
        f"{producto.nombre}: situación {f['situacion']} (Red). "
        f"Stock Red {_num(f['stock_red'])}, Almacén AEM {_num(f['stock_aem'])}, "
        f"cobertura total {_num(f['dispo_total'])} meses, CPMA {_num(f['cpma'])}/mes."
    )
    tabla = _tabla(
        ["Medicamento", "Situación (Red)", "Stock Red", "Almacén (AEM)", "Cobertura total (meses)", "CPMA"],
        [[f["producto_nombre"], f["situacion"], _num(f["stock_red"]), _num(f["stock_aem"]), _num(f["dispo_total"]), _num(f["cpma"])]],
        1,
    )
    enlace = {"pagina": "disponibilidad", "filtros": {"vista": "red", "busqueda": producto.medcod}}
    return texto, tabla, enlace


def _h_cpma(db, t):
    producto = _resolver_producto(db, t)
    if producto is None:
        return ("¿De qué producto quieres el CPMA? Por ejemplo: “cpma de metamizol”.", _vacia(), None)
    f = _fila_red_producto(db, producto)
    if f is None:
        return (f"No hay CPMA calculado para {producto.nombre}.", _vacia(), None)
    texto = (
        f"El CPMA de {producto.nombre} es {_num(f['cpma'])} unidades/mes "
        f"(consumo de 12 meses = {_num(f['sumames'])} en {f['contador']} meses con consumo)."
    )
    tabla = _tabla(
        ["Medicamento", "CPMA", "Consumo 12m", "Meses con consumo"],
        [[f["producto_nombre"], _num(f["cpma"]), _num(f["sumames"]), str(f["contador"])]],
        1,
    )
    enlace = {"pagina": "disponibilidad", "filtros": {"vista": "red", "busqueda": producto.medcod}}
    return texto, tabla, enlace


def _h_requisicion(db, t):
    producto = _resolver_producto(db, t)
    if producto is None:
        return ("¿De qué producto quieres saber cuánto pedir? Por ejemplo: “cuánto pido de dextrosa”.", _vacia(), None)
    r = obtener_requisicion(db, producto_cod=producto.medcod, establecimiento_cod=None, periodo=None, meses_a_cubrir=MESES_A_CUBRIR_DEFAULT)
    if r is None:
        return (f"No hay CPMA calculado para {producto.nombre}, no puedo sugerir una requisición.", _vacia(), None)
    texto = (
        f"Para {producto.nombre}, la requisición sugerida a nivel red (cubrir {r['meses_a_cubrir']} meses) "
        f"es {_num(r['cantidad_requerida'])} unidades. CPMA {_num(r['cpma'])}/mes, "
        f"stock disponible {_num(r['stock_disponible'])}."
    )
    tabla = _tabla(
        ["Medicamento", "CPMA", "Stock disponible", "Meses a cubrir", "Cantidad sugerida"],
        [[producto.nombre, _num(r["cpma"]), _num(r["stock_disponible"]), str(r["meses_a_cubrir"]), _num(r["cantidad_requerida"])]],
        1,
    )
    enlace = {"pagina": "disponibilidad", "filtros": {"vista": "red", "busqueda": producto.medcod}}
    return texto, tabla, enlace


def _h_faltantes(db, t):
    periodo = db.scalar(select(func.max(CalcCpma.periodo))) or date.today().replace(day=1)
    r = listar_pendientes(db, periodo)
    faltan = r["faltantes"]
    per = periodo.strftime("%Y-%m")
    if not faltan:
        texto = f"Todos los establecimientos ({r['total_establecimientos']}) ya cargaron su ICI de {per}."
    else:
        texto = (
            f"En {per} faltan {len(faltan)} de {r['total_establecimientos']} establecimientos por cargar "
            f"({r['cargados']} cargados)."
        )
    tabla = _tabla(
        ["Código", "Establecimiento"],
        [[e["cod_2000"], e["nombre"]] for e in faltan],
        len(faltan),
    )
    return texto, tabla, None


_HANDLERS = {
    "proximos_vencer": _h_proximos,
    "vencidos": _h_vencidos,
    "stock_negativo": _h_stock_negativo,
    "stock_producto": _h_stock_producto,
    "desabastecidos": _h_desabastecidos,
    "situacion_producto": _h_situacion_producto,
    "cpma": _h_cpma,
    "requisicion": _h_requisicion,
    "faltantes": _h_faltantes,
}


def _limpio(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ── Entrada principal ─────────────────────────────────────────────────────

def responder(db: Session, pregunta: str, sesion_id: str | None = None) -> dict:
    t = _norm(pregunta)
    intencion = _clasificar(t) if t else None

    if intencion is not None:
        # Si venía de una no reconocida en esta sesión, esto es su reformulación.
        marcar_reformulacion(db, sesion_id, pregunta, intencion)
        texto, tabla, enlace = _HANDLERS[intencion](db, t)
        return {
            "intencion_detectada": intencion,
            "respuesta_texto": texto,
            "datos": tabla,
            "sugerencias": SUGERENCIAS,
            "enlace": enlace,
        }

    # No se reconoció: se registra (fuente real para enseñarle) y, si se acerca a
    # alguna intención, se sugiere en vez de rendirse.
    cercanas = _cercanas(t) if t else []
    registrar_no_reconocida(db, pregunta, t, sesion_id, cercanas)

    if cercanas:
        return {
            "intencion_detectada": "sugerencia",
            "respuesta_texto": "No estoy seguro de lo que necesitas. ¿Quisiste decir alguna de estas?",
            "datos": _vacia(),
            "sugerencias": [INTENCION_EJEMPLO[i] for i in cercanas],
            "enlace": None,
        }

    return {
        "intencion_detectada": "desconocida",
        "respuesta_texto": (
            "No entendí la pregunta. Puedo ayudarte con: qué vence pronto o está vencido, "
            "saldos negativos, stock de un producto, qué está desabastecido, situación o CPMA "
            "de un producto, cuánto pedir de algo, y qué establecimientos faltan cargar."
        ),
        "datos": _vacia(),
        "sugerencias": SUGERENCIAS,
        "enlace": None,
    }
