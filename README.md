# Sistema de Gestión de Medicamentos — Red de Salud Coronel Portillo

Automatización y gestión del CPMA, disponibilidad, DME, stock e importaciones a partir de datos de SISMED.

---

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado en la computadora:

1. **Git**: Para clonar el repositorio.
2. **XAMPP**: Con el servicio de **MySQL** activo.
3. **Python**: Versión 3.10 o superior (recomendado **3.12**).
   * *En Windows*: Asegúrate de marcar la opción **"Add python.exe to PATH"** durante la instalación.
4. **Node.js**: Versión 18 o superior y **npm** (incluido con Node).

---

## 🚀 Guía de Instalación y Despliegue Paso a Paso

### 1. Clonar el Repositorio

Abre una terminal y clona el proyecto en tu equipo:

```bash
git clone <URL_DEL_REPOSITORIO> sismed_proyecto
cd sismed_proyecto
```

---

### 2. Configurar la Base de Datos (MySQL con XAMPP)

1. Abre el **Panel de Control de XAMPP** e inicia el módulo **MySQL**.
2. Ingresa a phpMyAdmin desde el navegador: [http://localhost/phpmyadmin](http://localhost/phpmyadmin).
3. Crea una nueva base de datos con los siguientes datos:
   * **Nombre:** `sismed_red`
   * **Cotejamiento:** `utf8mb4_general_ci` (o `utf8mb4_unicode_ci`)
4. Selecciona la base de datos `sismed_red` en el panel izquierdo y haz clic en la pestaña **Importar**.
5. Haz clic en **Seleccionar archivo** y elige el respaldo ubicado en:
   * `backend/backup_sismed_red.sql`
6. Presiona el botón **Importar** (al final de la página) y espera hasta que confirme que todas las tablas fueron creadas exitosamente.

---

### 3. Levantar el Backend (FastAPI)

Abre una terminal en la raíz del proyecto y dirígete a la carpeta `backend`:

```bash
cd backend
```

#### A. Crear el Entorno Virtual de Python

* **En Windows (CMD o PowerShell):**
  ```cmd
  python -m venv venv
  ```
* **En Linux / macOS:**
  ```bash
  python3 -m venv venv
  ```
  *(En Ubuntu/Debian, si te pide instalar el módulo: `sudo apt install python3-venv`)*

#### B. Activar el Entorno Virtual

* **En Windows:**
  * CMD:
    ```cmd
    venv\Scripts\activate
    ```
  * PowerShell:
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
    *(Si PowerShell bloquea la ejecución de scripts, ejecuta una vez: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

* **En Linux / macOS:**
  ```bash
  source venv/bin/activate
  ```

> Al activarse correctamente, verás el prefijo `(venv)` al inicio de tu terminal.

#### C. Instalar Dependencias de Python

```bash
pip install -r requirements.txt
```

#### D. Configuración de Base de Datos (.env) — Opcional

Por defecto, el backend se conecta automáticamente a:
`mysql+pymysql://root:@localhost:3306/sismed_red` (usuario `root`, sin contraseña, puerto estándar 3306).

Si tu servidor MySQL tiene contraseña o corre en otro puerto, crea un archivo `.env` dentro de `backend/`:
```env
DATABASE_URL=mysql+pymysql://root:TU_PASSWORD@localhost:3306/sismed_red
```

#### E. Ejecutar el Servidor Backend

```bash
uvicorn app.main:app --reload
```

* **Servidor backend activo en:** [http://localhost:8000](http://localhost:8000)
* **Documentación interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 4. Levantar el Frontend (React + Vite)

Abre **otra ventana de terminal** (mantén la del backend abierta) y dirígete a la carpeta `frontend`:

```bash
cd frontend
```

#### A. Instalar Paquetes de Node.js

```bash
npm install
```

#### B. Ejecutar el Servidor de Desarrollo

```bash
npm run dev
```

* **Aplicación web activa en:** [http://localhost:5173](http://localhost:5173)

---

## 🌐 Resumen de Accesos Locales

| Servicio | URL | Descripción |
|---|---|---|
| **Frontend** | [http://localhost:5173](http://localhost:5173) | Interfaz gráfica de usuario |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | Servidor FastAPI |
| **Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Documentación y pruebas de endpoints |
| **phpMyAdmin** | [http://localhost/phpmyadmin](http://localhost/phpmyadmin) | Administrador de MySQL |

---

## ⚙️ Arquitectura del Sistema

```
SISMED (FoxPro) → Archivos DBF
        ↓
FastAPI Backend (API REST: api → services → repositories → models, + etl)
        ↓
MySQL XAMPP (Tablas maestras, stock, movimientos, staging e ICI)
        ↓
React + Vite Frontend (Consumo de API en tiempo real)
```

---

## ⚠️ Recomendación para Git (.gitignore)

Para evitar incompatibilidades entre sistemas operativos (como Windows y Linux), **nunca subas a Git** los entornos virtuales ni los paquetes compilados. Tu archivo `.gitignore` en la raíz debe contener:

```gitignore
# Python
backend/venv/
backend/__pycache__/
backend/*.pyc
backend/.env

# Node.js
frontend/node_modules/
frontend/dist/
```
Cada máquina debe generar su propio `venv` (`pip install -r requirements.txt`) y su propio `node_modules` (`npm install`).
