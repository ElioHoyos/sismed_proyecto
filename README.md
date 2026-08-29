# Sistema de Gestión de Medicamentos — Red de Salud Coronel Portillo

Reemplaza el cálculo manual del CPMA (**2-3 días en Excel**) por un sistema
automatizado que lee los datos exportados de SISMED.

## ⚠️ Empieza por aquí
Lee **`docs/CONTEXTO.md`** (v2) — análisis completo, fórmula verificada del CPMA,
y el hallazgo del **ICI**, que es la fuente principal del sistema.

## Estado
- [x] Análisis de la BD real de SISMED (~150 tablas)
- [x] **Fórmula CPMA verificada: calza 100% con el Excel del doc (397/397 productos)**
- [x] **Hallazgo del ICI (`tformdet`): cubre los 93 establecimientos, 12 meses**
- [x] Esquema MySQL con ICI (`db/schema.sql`)
- [x] Motor CPMA (`backend/app/services/cpma.py`)
- [ ] Importador ICI (`backend/app/etl/`) ← **siguiente**
- [ ] Importador movimientos
- [ ] API REST
- [ ] Frontend

## Arquitectura
```
SISMED (FoxPro) → exportar DBF
       ↓
FastAPI (N capas: api → services → repositories → models, + etl)
       ↓
MySQL (staging → limpias → calculadas)
       ↓
Frontend (React/Angular)
```
App **web** (no escritorio), desplegada local, accesible por navegador.

## Arrancar
```bash
mysql -u root -p < db/schema.sql

cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## La fórmula (el corazón)
```
CPMA = SUMAMES / CONTADOR
  SUMAMES  = suma del consumo de los últimos 12 meses
  CONTADOR = nº de meses (de esos 12) CON consumo > 0   ← no se divide entre 12
```

## Las dos fuentes
| Fuente | Qué aporta |
|---|---|
| **ICI** (`tformdet`) | Consumo y stock **de los 93 establecimientos** ← principal |
| Movimientos (`tmovim`) | Lo que el **almacén despachó** |
