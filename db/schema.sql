-- ============================================================
--  ESQUEMA MySQL — Sistema de Gestión de Medicamentos
--  Red de Salud Coronel Portillo
--
--  Diseño en 3 niveles:
--    1. stg_*   → staging: el DBF entra TAL CUAL, en texto, sin validar
--    2. limpias → tipadas, con llaves foráneas (lo que SISMED no tiene)
--    3. calc_*  → precalculadas tras cada importación (el front solo lee)
-- ============================================================

CREATE DATABASE IF NOT EXISTS sismed_red
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sismed_red;

-- ============================================================
--  NIVEL 1 — STAGING
--  Todo en TEXTO. Aquí no se valida nada. Espejo crudo del DBF.
--  Esto nos permite auditar qué llegó exactamente, y reprocesar.
-- ============================================================

CREATE TABLE importacion (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    archivo         VARCHAR(255) NOT NULL,
    establecimiento_cod VARCHAR(20),          -- de qué establecimiento viene
    periodo         DATE,                     -- a qué mes corresponde
    version         INT DEFAULT 1,            -- recarga del mismo periodo
    filas_cabecera  INT DEFAULT 0,
    filas_detalle   INT DEFAULT 0,
    incidencias     INT DEFAULT 0,
    estado          ENUM('PENDIENTE','PROCESANDO','OK','ERROR') DEFAULT 'PENDIENTE',
    usuario         VARCHAR(100),
    creado          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- IDEMPOTENCIA: recargar el mismo periodo/establecimiento reemplaza,
    -- no duplica. Sin esto creamos stock negativo nosotros mismos.
    UNIQUE KEY uk_import (establecimiento_cod, periodo, version)
) ENGINE=InnoDB;

-- Espejo crudo de tmovim (cabecera). TODO varchar, como en FoxPro.
CREATE TABLE stg_tmovim (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    importacion_id  INT NOT NULL,
    movnumero       VARCHAR(20),
    movcoditip      VARCHAR(5),
    almcodiorg      VARCHAR(20),
    almcodidst      VARCHAR(20),
    movfechemi      VARCHAR(20),
    movfechreg      VARCHAR(20),
    movnumedco      VARCHAR(30),
    movrefe         VARCHAR(400),
    movfecanul      VARCHAR(20),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id) ON DELETE CASCADE,
    INDEX idx_stg_mov (movnumero, movcoditip)
) ENGINE=InnoDB;

-- Espejo crudo de tmovindet (detalle). TODO varchar.
-- OJO: movcantid/movprecio/movtotal son TEXTO en SISMED. Aquí también,
-- a propósito: la conversión a número ocurre en la validación.
CREATE TABLE stg_tmovindet (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    importacion_id  INT NOT NULL,
    movnumero       VARCHAR(20),
    movcoditip      VARCHAR(5),
    movnumeite      VARCHAR(10),
    medcod          VARCHAR(20),
    medlote         VARCHAR(80),
    medfechvto      VARCHAR(20),
    movcantid       VARCHAR(80),      -- ← texto que DEBE ser número
    movprecio       VARCHAR(80),      -- ← texto que DEBE ser número
    movtotal        VARCHAR(80),      -- ← texto que DEBE ser número
    medregsan       VARCHAR(80),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id) ON DELETE CASCADE,
    INDEX idx_stg_det (movnumero, movcoditip)
) ENGINE=InnoDB;

-- Todo lo que NO pasó la validación queda AQUÍ, con su motivo.
-- Nunca se descarta en silencio, nunca se fuerza a cero.
CREATE TABLE incidencia (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    importacion_id  INT NOT NULL,
    tabla_origen    VARCHAR(30),
    fila_id         BIGINT,
    tipo            VARCHAR(50),      -- CANTIDAD_NO_NUMERICA, PRODUCTO_INEXISTENTE,
                                      -- ESTABLECIMIENTO_INEXISTENTE, FECHA_INVALIDA,
                                      -- CANTIDAD_NEGATIVA, DUPLICADO...
    detalle         TEXT,             -- el valor problemático y su contexto
    creado          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (importacion_id) REFERENCES importacion(id) ON DELETE CASCADE,
    INDEX idx_inc_tipo (tipo)
) ENGINE=InnoDB;

-- ============================================================
--  NIVEL 2 — TABLAS LIMPIAS (tipadas, con FKs)
-- ============================================================

-- SISMED: m_establecimiento
CREATE TABLE establecimiento (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cod_2000        VARCHAR(20) NOT NULL UNIQUE,   -- código único oficial
    nombre          VARCHAR(255) NOT NULL,
    clasificacion   VARCHAR(100),
    tipo            VARCHAR(100),
    categoria       VARCHAR(20),                   -- I-1, I-2, I-3, I-4...
    cod_microrred   VARCHAR(20),
    nom_microrred   VARCHAR(255),
    cod_red         VARCHAR(20),
    red             VARCHAR(255),
    ubigeo          VARCHAR(10),
    distrito        VARCHAR(100),
    provincia       VARCHAR(100),
    departamento    VARCHAR(100),
    tiene_sismed    BOOLEAN DEFAULT FALSE,         -- TRUE para los 9
    es_almacen      BOOLEAN DEFAULT FALSE,         -- TRUE para el almacén central
    activo          BOOLEAN DEFAULT TRUE,
    INDEX idx_est_microrred (cod_microrred)
) ENGINE=InnoDB;

-- SISMED: mproducto
-- Estado de la compra centralizada de CENARES (fuente: XLSX periódico).
-- Una fila por (año, código SISMED). Recargar el mismo año reemplaza sus filas.
CREATE TABLE compra_centralizada (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    anio                  SMALLINT NOT NULL,             -- 2025 / 2026 (de la hoja)
    codigo_sismed         VARCHAR(20) NOT NULL,          -- col B, zfill(5) — llave de cruce
    codigo_siga           VARCHAR(20),                   -- col C — cruce alternativo
    tipo_producto         VARCHAR(60),                   -- E
    procedimiento         VARCHAR(255),                  -- F
    estado_situacion      VARCHAR(80),                   -- G (Situación)
    observacion_estado    TEXT,                          -- H
    reg_siga_situacion    VARCHAR(120),                  -- I (Situación)
    reg_siga_observacion  TEXT,                          -- J
    contratista           VARCHAR(255),                  -- K
    nro_contrato          VARCHAR(60),                   -- L
    fecha_convocatoria    DATE,                          -- M
    fecha_buena_pro       DATE,                          -- N
    fecha_entrega         DATE,                          -- O (si es fecha real)
    fecha_entrega_texto   VARCHAR(120),                  -- O tal cual (ej. "NOVIEMBRE 2026")
    observacion           TEXT,                          -- P
    importado             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_compra_cruce (codigo_sismed, anio),
    INDEX idx_compra_anio (anio)
) ENGINE=InnoDB;

-- Ediciones del doc sobre campos de CENARES (aparte del valor del archivo).
-- Sobreviven a la reimportación; ganan sobre el archivo. Presencia = editado.
CREATE TABLE compra_edicion (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    anio           SMALLINT NOT NULL,
    codigo_sismed  VARCHAR(20) NOT NULL,
    campo          VARCHAR(40) NOT NULL,
    valor          TEXT,
    editado_en     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_compra_edicion (anio, codigo_sismed, campo)
) ENGINE=InnoDB;

CREATE TABLE producto (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    medcod          VARCHAR(20) NOT NULL UNIQUE,
    codigo_siga     VARCHAR(20),                   -- MPRODUCTO: CODIGO_SIG (columna CODIGO SIGA)
    nombre          VARCHAR(200) NOT NULL,
    nombre_abrev    VARCHAR(100),
    presentacion    VARCHAR(100),
    concentracion   VARCHAR(60),
    forma_farma     VARCHAR(30),                   -- ICI: FF (forma farmacéutica, código crudo)
    tipo            VARCHAR(5),                    -- ICI: MEDTIP (M=medicamento, I=insumo)
    es_petitorio    BOOLEAN,                       -- pertenece al petitorio nacional (MEDPET=='P')
    medpet          VARCHAR(5),                    -- ICI: MEDPET crudo (P=petitorio, _=SIS)
    medest          VARCHAR(5),                    -- ICI: MEDEST crudo (E / S / _)
    es_estrategico  BOOLEAN,
    controlado      BOOLEAN,                       -- fiscalizado / narcótico
    stock_min       INT,                           -- SISMED: PRDSTKMIN
    stock_max       INT,                           -- SISMED: PRDSTKMAX
    punto_reposicion INT,                          -- SISMED: PRDPTOREP
    reg_sanitario   VARCHAR(30),
    origen          VARCHAR(10),                   -- 'MPRODUCTO' (catálogo oficial) o 'ICI' (solo en ICI)
    activo          BOOLEAN DEFAULT TRUE,
    INDEX idx_prod_nombre (nombre)
) ENGINE=InnoDB;

-- SISMED: tmovim  (cabecera, ya validada)
CREATE TABLE movimiento (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    mov_numero      VARCHAR(20) NOT NULL,
    mov_tipo        CHAR(1) NOT NULL,              -- E = entrada, S = salida
    est_origen_id   INT,
    est_destino_id  INT,
    fecha_emision   DATE,
    fecha_registro  DATE,
    guia_numero     VARCHAR(30),
    motivo          VARCHAR(400),                  -- SISMED: movrefe
    -- clase derivada del motivo. SOLO 'CONSUMO' entra al cálculo de CPMA.
    clase           ENUM('CONSUMO','AJUSTE','TRANSFERENCIA','COMPRA','OTRO')
                    DEFAULT 'OTRO',
    anulado         BOOLEAN DEFAULT FALSE,
    origen          ENUM('DBF','DIGITADO','DESPACHO') NOT NULL,
    importacion_id  INT,
    CONSTRAINT chk_tipo CHECK (mov_tipo IN ('E','S')),
    FOREIGN KEY (est_origen_id)  REFERENCES establecimiento(id),
    FOREIGN KEY (est_destino_id) REFERENCES establecimiento(id),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id),
    -- evita cargar dos veces el mismo movimiento
    UNIQUE KEY uk_mov (mov_numero, mov_tipo, origen),
    INDEX idx_mov_dest_fecha (est_destino_id, fecha_emision),
    INDEX idx_mov_clase (clase)
) ENGINE=InnoDB;

-- SISMED: tmovindet  (detalle, ya validado y TIPADO)
CREATE TABLE movimiento_detalle (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    movimiento_id   INT NOT NULL,
    item            INT,
    producto_id     INT NOT NULL,
    lote            VARCHAR(80),
    fecha_vcto      DATE,                          -- permite control de vencimientos
    -- ↓ AQUÍ está la corrección clave frente a SISMED: número, no texto.
    cantidad        DECIMAL(14,2) NOT NULL,
    precio          DECIMAL(14,4),
    total           DECIMAL(16,2),
    reg_sanitario   VARCHAR(80),
    FOREIGN KEY (movimiento_id) REFERENCES movimiento(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id)   REFERENCES producto(id),
    INDEX idx_det_prod (producto_id),
    INDEX idx_det_vcto (fecha_vcto)
) ENGINE=InnoDB;

-- ============================================================
--  NIVEL 3 — TABLAS CALCULADAS
--  Se recalculan tras cada importación. El front SOLO lee de aquí.
--  Nada de esto se calcula al vuelo en cada request.
-- ============================================================

-- Stock actual por establecimiento / producto / lote
CREATE TABLE calc_stock (
    establecimiento_id INT NOT NULL,
    producto_id     INT NOT NULL,
    lote            VARCHAR(80) NOT NULL DEFAULT '',
    fecha_vcto      DATE,
    cantidad        DECIMAL(14,2) NOT NULL,
    actualizado     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (establecimiento_id, producto_id, lote),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento(id),
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    INDEX idx_stock_prod (producto_id)
) ENGINE=InnoDB;

-- Consumo mensual — la BASE del CPMA
CREATE TABLE calc_consumo_mensual (
    establecimiento_id INT NOT NULL,
    producto_id     INT NOT NULL,
    anio            SMALLINT NOT NULL,
    mes             TINYINT NOT NULL,
    cantidad        DECIMAL(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (establecimiento_id, producto_id, anio, mes),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento(id),
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    INDEX idx_cons_periodo (anio, mes)
) ENGINE=InnoDB;

-- CPMA calculado por establecimiento — ESTO es lo que reemplaza los 2-3 días del doc
CREATE TABLE calc_cpma (
    establecimiento_id INT NOT NULL,
    producto_id     INT NOT NULL,
    periodo         DATE NOT NULL,        -- último mes de la ventana de 12
    sumames         DECIMAL(16,2) NOT NULL,   -- suma de consumo de 12 meses
    contador        TINYINT NOT NULL,         -- meses CON consumo > 0
    cpma            DECIMAL(14,2) NOT NULL,   -- = sumames / contador
    stock_red       DECIMAL(14,2) DEFAULT 0,      -- Red (establecimiento) — antes 'stock_aem'
    stock_aem       DECIMAL(14,2) DEFAULT 0,      -- AEM = almacén central — antes 'stock'
    dispo           DECIMAL(10,2) DEFAULT 0,      -- = stock_red / cpma
    dispo_total     DECIMAL(10,2) DEFAULT 0,      -- = (stock_red+stock_aem)/cpma
    situacion       ENUM('SIN ROTACION','DESABASTECIDO','CRITICO',
                         'SUBSTOCK','NORMOSTOCK','SOBRESTOCK') NOT NULL,      -- sobre dispo (Red) — base del % DME
    situacion_total ENUM('SIN ROTACION','DESABASTECIDO','CRITICO',
                         'SUBSTOCK','NORMOSTOCK','SOBRESTOCK') NOT NULL,      -- sobre dispo_total (Red+AEM)
    calculado       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (establecimiento_id, producto_id, periodo),
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    INDEX idx_cpma_situacion (situacion),
    INDEX idx_cpma_periodo (periodo)
) ENGINE=InnoDB;

-- Vista consolidada de RED por producto. NO es la suma de los CPMA
-- individuales de calc_cpma (el CPMA no es lineal: si cada
-- establecimiento tiene meses distintos con/sin consumo, promediar los
-- promedios da un número distinto a sumar el consumo de TODA la red mes
-- a mes y recién ahí aplicar SUMAMES/CONTADOR). Se calcula aparte y se
-- guarda aquí — igual que calc_cpma, nunca al vuelo.
CREATE TABLE calc_cpma_red (
    producto_id     INT NOT NULL,
    periodo         DATE NOT NULL,
    sumames         DECIMAL(16,2) NOT NULL,
    contador        TINYINT NOT NULL,
    cpma            DECIMAL(14,2) NOT NULL,
    stock_red       DECIMAL(14,2) DEFAULT 0,      -- Red = suma del stock de TODOS los establecimientos
    stock_aem       DECIMAL(14,2) DEFAULT 0,      -- AEM = almacén central
    dispo           DECIMAL(10,2) DEFAULT 0,      -- = stock_red / cpma
    dispo_total     DECIMAL(10,2) DEFAULT 0,      -- = (stock_red+stock_aem)/cpma
    situacion       ENUM('SIN ROTACION','DESABASTECIDO','CRITICO',
                         'SUBSTOCK','NORMOSTOCK','SOBRESTOCK') NOT NULL,
    situacion_total ENUM('SIN ROTACION','DESABASTECIDO','CRITICO',
                         'SUBSTOCK','NORMOSTOCK','SOBRESTOCK') NOT NULL,
    calculado       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (producto_id, periodo),
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    INDEX idx_cpma_red_situacion (situacion),
    INDEX idx_cpma_red_periodo (periodo)
) ENGINE=InnoDB;

-- % DME (Disponibilidad de Medicamentos Esenciales) por establecimiento.
-- Solo sobre productos del petitorio (producto.es_petitorio), calculado
-- desde calc_cpma.situacion_eess — nunca al vuelo. Ver app/services/dme.py.
CREATE TABLE calc_dme (
    establecimiento_id INT NOT NULL,
    periodo         DATE NOT NULL,
    total_evaluados SMALLINT UNSIGNED NOT NULL,   -- petitorio, sin contar "sin rotación"
    total_disponibles SMALLINT UNSIGNED NOT NULL, -- normostock + sobrestock (situacion_eess)
    porcentaje      DECIMAL(5,2) NOT NULL,
    semaforo        ENUM('VERDE_OSCURO','VERDE','AMARILLO','ROJO') NOT NULL,
    calculado       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (establecimiento_id, periodo),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento(id)
) ENGINE=InnoDB;

-- Consolidado de red: mismo cálculo pero contando situacion_eess de
-- TODOS los establecimientos juntos (válido agregar por establecimiento
-- aquí porque stock_aem NO se repite entre ellos, a diferencia del
-- stock del almacén central — ver la nota de calc_cpma_red).
CREATE TABLE calc_dme_red (
    periodo         DATE NOT NULL PRIMARY KEY,
    total_evaluados SMALLINT UNSIGNED NOT NULL,
    total_disponibles SMALLINT UNSIGNED NOT NULL,
    porcentaje      DECIMAL(5,2) NOT NULL,
    semaforo        ENUM('VERDE_OSCURO','VERDE','AMARILLO','ROJO') NOT NULL,
    calculado       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
--  ICI — INFORME DE CONSUMO INTEGRADO
--  *** LA FUENTE PRINCIPAL DEL SISTEMA ***
--
--  Estructura REAL (verificada contra un .dbf real de SISMED,
--  C.S SAN FERNANDO.DBF, 552 productos) — un archivo POR
--  ESTABLECIMIENTO, una fila por producto, ancho (MES01..MES12), NO el
--  formato largo de tformdet que se había asumido antes de ver un
--  archivo real. El establecimiento NO viene en el archivo
--  (CODIGO_PRE/CODIGO_EJE vacíos en las 552 filas): se resuelve por
--  fuera (parámetro de la importación), nunca por el nombre del
--  archivo ni por contenido del DBF.
--
--  MES01..MES12 no traen el año — se asume MES12 = mes de cierre
--  (periodo, el más reciente) y MES01 = 11 meses atrás; pendiente de
--  confirmar la convención exacta con el doc.
--
--  SISMED trae su propio CPA/SITUACION ya calculados, pero se guardan
--  SOLO como referencia — el sistema recalcula el CPMA desde
--  MES01..MES12 con la fórmula de app/services/cpma.py (opción B).
--  El resto de columnas del DBF (SUMAMES, CUENTA, MESES_PROV, UND_NEC,
--  VALORES, DESABASTEC, SUBSTOCK, NORMOSTOCK, SOBRESTOCK, SOBSTKCRIT,
--  CPM, NUMPROV, TRAZADOR, ALMTIPO) son residuo del reporte de SISMED
--  — confirmado con datos reales que no aportan nada (constantes,
--  vacías o inconsistentes) y no se importan.
-- ============================================================

-- Staging del ICI: entra tal cual, sin validar. Un establecimiento por
-- importación (ver `importacion.establecimiento_cod`), una fila por producto.
CREATE TABLE stg_ici (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    importacion_id  INT NOT NULL,
    codigo_med      VARCHAR(20),      -- producto
    descrip         VARCHAR(255),
    medtip          VARCHAR(5),       -- M=medicamento, I=insumo
    medpet          VARCHAR(5),       -- P=petitorio
    medest          VARCHAR(5),
    ff              VARCHAR(20),      -- forma farmacéutica
    -- consumo mensual crudo, la fuente del CPMA (MES01=más antiguo .. MES12=cierre):
    mes01 VARCHAR(20), mes02 VARCHAR(20), mes03 VARCHAR(20), mes04 VARCHAR(20),
    mes05 VARCHAR(20), mes06 VARCHAR(20), mes07 VARCHAR(20), mes08 VARCHAR(20),
    mes09 VARCHAR(20), mes10 VARCHAR(20), mes11 VARCHAR(20), mes12 VARCHAR(20),
    stock           VARCHAR(20),      -- Stock_AEM actual del establecimiento
    precio          VARCHAR(20),
    -- referencia de SISMED, NUNCA se usa para calcular:
    cpa             VARCHAR(20),
    situacion       VARCHAR(20),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id) ON DELETE CASCADE,
    INDEX idx_stg_ici (codigo_med)
) ENGINE=InnoDB;

-- ICI validado y tipado. UNA fila por establecimiento/producto/mes.
CREATE TABLE ici (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    establecimiento_id INT NOT NULL,
    producto_id     INT NOT NULL,
    anio            SMALLINT NOT NULL,
    mes             TINYINT NOT NULL,

    consumo         DECIMAL(14,2) NOT NULL DEFAULT 0,  -- MES0X crudo — alimenta el CPMA
    -- Solo se conocen para el mes de cierre (periodo) de la importación
    -- que trajo ese mes; en los otros 11 de la ventana quedan NULL (no
    -- se inventan ceros para historia que no tenemos).
    stock_final     DECIMAL(14,2) DEFAULT NULL,        -- ← Stock_AEM, solo en el cierre
    precio          DECIMAL(14,4) DEFAULT 0,

    -- Referencia de SISMED — SOLO para comparar, jamás para calcular
    -- (opción B). También solo se conocen en el mes de cierre.
    cpa_sismed      DECIMAL(14,2) DEFAULT NULL,
    situacion_sismed VARCHAR(20) DEFAULT NULL,         -- encoding no confiable, no usar para lógica

    importacion_id  INT,
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento(id),
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id),
    -- IDEMPOTENCIA: un solo registro por EESS/producto/mes.
    -- Recargar el mismo periodo REEMPLAZA, no duplica.
    UNIQUE KEY uk_ici (establecimiento_id, producto_id, anio, mes),
    INDEX idx_ici_periodo (anio, mes),
    INDEX idx_ici_prod (producto_id)
) ENGINE=InnoDB;

-- ============================================================
--  STOCK DEL ALMACÉN CENTRAL — SISMED: MSTKALMDE.DBF (stock por LOTE)
--
--  Se importa por lote (no el consolidado): verificado que la suma por
--  lote calza 100% con el consolidado, así que no se pierde nada y se
--  gana control de vencimientos (ver idx_stkalm_vcto).
--
--  ALMCOD ('034S0501') es el almacén central — una entidad aparte, NO
--  uno de los 89 establecimientos, por eso `almacen_cod` es texto
--  libre y no una FK a `establecimiento`.
--
--  Es una FOTO del stock actual, no una serie mensual como `ici`: cada
--  importación REEMPLAZA por completo el stock de ese almacén (un lote
--  que ya no aparece en el archivo nuevo es un lote agotado/consumido,
--  no se queda fantasma con el valor viejo).
-- ============================================================

CREATE TABLE stg_stock_almacen (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    importacion_id  INT NOT NULL,
    almcod          VARCHAR(20),
    medcod          VARCHAR(20),
    medlote         VARCHAR(80),
    medfechvto      VARCHAR(20),
    stksaldode      VARCHAR(20),
    stkprecio       VARCHAR(20),
    medregsan       VARCHAR(80),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id) ON DELETE CASCADE,
    INDEX idx_stg_stkalm (medcod, medlote)
) ENGINE=InnoDB;

-- Stock UNIFICADO: almacén central (por lote, con vencimiento) + establecimientos
-- (por producto, sin lote — fuente STOCK del ICI). `origen` distingue ambos;
-- lote/fecha_vcto solo para el almacén, establecimiento_id solo para EESS.
CREATE TABLE stock (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    origen          VARCHAR(10) NOT NULL,              -- 'ALMACEN' | 'EESS'
    almacen_cod     VARCHAR(20),                       -- 034S0501 = almacén central (solo ALMACEN)
    establecimiento_id INT,                            -- solo EESS
    producto_id     INT NOT NULL,
    lote            VARCHAR(80),                       -- solo ALMACEN (el ICI no trae lote)
    fecha_vcto      DATE,                              -- solo ALMACEN
    cantidad        DECIMAL(14,2) NOT NULL DEFAULT 0,  -- saldo (puede ser negativo, tal cual SISMED)
    precio          DECIMAL(14,4),
    reg_sanitario   VARCHAR(80),
    periodo         DATE,                              -- foto de stock (cierre EESS / foto almacén)
    importacion_id  INT,
    actualizado     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (producto_id) REFERENCES producto(id),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimiento(id),
    FOREIGN KEY (importacion_id) REFERENCES importacion(id),
    INDEX idx_stock_origen (origen),
    INDEX idx_stock_prod (producto_id),
    INDEX idx_stock_eess (establecimiento_id),
    INDEX idx_stock_neg (cantidad),
    INDEX idx_stkalm_vcto (fecha_vcto)
) ENGINE=InnoDB;
