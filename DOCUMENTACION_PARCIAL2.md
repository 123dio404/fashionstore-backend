# FashionStore SaaS — Documentación del Segundo Parcial
**Materia:** Sistemas de Información II (INF412)  
**Docente:** MSc. Ing. Angélica Garzón Cuéllar  
**Plataforma:** FashionStore SaaS (E-Commerce Multitenant con Persistencia Offline e Inteligencia Artificial)

---

## 1. Aspectos Generales y Descripción del Sistema
* **Nombre del Producto:** **FashionStore SaaS**
* **Definición:** Plataforma de comercio electrónico multitenant para empresas de indumentaria textil bajo el modelo Software as a Service (SaaS). Incorpora gestión de suscripciones (Planes Básico y Profesional), clientes con soporte offline (PWA con IndexedDB y Móvil Flutter con SQLite), motor de sincronización e idempotencia para ventas de contado y reservas, políticas postventa para cambio de prendas, analítica inteligente con Machine Learning (datos sintéticos, modelos supervisados y no supervisados) y reportes generativos mediante IA en lenguaje natural (texto y voz).
* **Metodología y Modelado:** Metodología **ICONIX** y estándar **UML 2.5+**.

---

## 2. Actores del Sistema

* **Superadministrador SaaS:** Administra las empresas contratantes (tenants), gestiona planes de suscripción y supervisa la plataforma global.
* **Administrador de Empresa (Tenant Admin):** Gestiona su propia empresa, sucursales, empleados, catálogo, inventario, suscripción, dashboard analítico y reportes con IA.
* **Encargado de Sucursal / Cajero:** Opera la PWA o App Móvil en tienda física, consulta catálogo local, registra ventas y reservas offline, sincroniza operaciones y tramita cambios de prendas.
* **Cliente:** Consulta catálogo en línea o en tienda física, visualiza disponibilidad de prendas y realiza reservas.
* **Sistema (Servicios Backend / IA):** Motor de sincronización automática, resolución de idempotencia, inferencia de modelos ML y procesamiento de lenguaje natural.

---

## 3. Paquetes del Sistema

* **PAQ-01: Gestión SaaS y Multitenant:** Registro de empresas, catálogo de planes y administración de suscripciones.
* **PAQ-02: Organización y Usuarios:** Sucursales por empresa, gestión de empleados, roles y aislamiento lógico de datos.
* **PAQ-03: Catálogo e Inventario:** Productos, variantes (tallas, colores), categorías, temporadas y stock por sucursal.
* **PAQ-04: Operaciones Offline y Sincronización:** Persistencia local (IndexedDB / SQLite), ventas de contado offline, reservas offline y cola de sincronización resiliente.
* **PAQ-05: Políticas Postventa:** Gestión de cambios de prendas dentro de un plazo límite.
* **PAQ-06: Analítica con Machine Learning:** Generación de datos sintéticos, modelo supervisado, modelo no supervisado y dashboard analítico.
* **PAQ-07: Reportes Generativos con IA:** Consultas en lenguaje natural (texto y voz), visualización dinámica (tablas/gráficos) y exportación a PDF y Excel.

---

## 4. Requisitos del Sistema

### 4.1 Requisitos Funcionales (RF)

#### PAQ-01: Gestión SaaS y Multitenant
* **RF01:** Registrar empresas contratantes (tenants) con datos fiscales y administrador inicial.
* **RF02:** Administrar catálogo de planes de suscripción (Básico y Profesional).
* **RF03:** Asignar y cambiar planes de suscripción con fechas de inicio y vencimiento.
* **RF04:** Restringir operaciones y recursos automáticamente según los límites del plan contratado.

#### PAQ-02: Organización y Usuarios
* **RF05:** Registrar y administrar sucursales por empresa (máximo 2 en Básico, máximo 10 en Profesional).
* **RF06:** Gestionar usuarios con roles (`Superadmin`, `Tenant Admin`, `Cajero`, `Cliente`).
* **RF07:** Aislar la información impidiendo accesos cruzados entre empresas en todo el backend.

#### PAQ-03: Catálogo e Inventario
* **RF08:** Administrar prendas con categorías, temporadas y variantes de talla, color y precio.
* **RF09:** Controlar existencias de inventario independientes por cada sucursal física.

#### PAQ-04: Operaciones Offline y Sincronización
* **RF10:** Descargar y almacenar localmente el catálogo y stock conocido (IndexedDB en PWA, SQLite en Móvil).
* **RF11:** Registrar ventas de contado sin conexión a Internet generando un UUID único en cliente.
* **RF12:** Registrar reservas de prendas sin conexión a Internet.
* **RF13:** Consultar lista de ventas y reservas locales pendientes de sincronización.
* **RF14:** Sincronizar cola de operaciones pendientes al recuperar conectividad a Internet.
* **RF15:** Validar idempotencia en backend para no duplicar ventas ante reintentos de envío.
* **RF16:** Detectar y gestionar conflictos de inventario cuando el stock central sea insuficiente.

#### PAQ-05: Políticas Postventa
* **RF17:** Registrar cambios de prendas de vestir adquiridas dentro de un tiempo determinado (30 días).
* **RF18:** Actualizar inventario por reingreso de la prenda devuelta y egreso de la nueva prenda.

#### PAQ-06: Analítica con Machine Learning
* **RF19:** Generar conjunto de datos sintéticos de ventas y transacciones para entrenamiento.
* **RF20:** Entrenar y consultar un modelo supervisado para predecir ventas o demanda futura.
* **RF21:** Entrenar y consultar un modelo no supervisado para segmentación de clientes o detección de anomalías.
* **RF22:** Desplegar un dashboard analítico con gráficos interactivos e indicadores de los modelos.

#### PAQ-07: Reportes Generativos con IA
* **RF23:** Recibir solicitudes de reportes en lenguaje natural mediante texto escrito o comandos de voz.
* **RF24:** Interpretar la solicitud y generar consultas dinámicas filtradas estrictamente por el tenant.
* **RF25:** Disponer de al menos 4 tipos de reportes demostrables con datos reales de la base de datos.
* **RF26:** Visualizar resultados en tablas y gráficos seleccionados dinámicamente.
* **RF27:** Exportar los reportes generados a formatos PDF y Excel.
* **RF28:** Restringir el acceso a reportes con IA únicamente a tenants con Plan Profesional.

---

### 4.2 Requisitos No Funcionales (RNF)

* **RNF01 (Seguridad):** Autenticación y autorización mediante JWT con validación de rol y tenant.
* **RNF02 (Aislamiento de datos):** Ninguna consulta debe acceder a datos de otro tenant sin autorización.
* **RNF03 (Persistencia offline):** Los datos locales deben mantenerse tras cerrar o reiniciar el navegador o la app.
* **RNF04 (Integridad transaccional):** Consistencia atómica en ventas y movimientos de inventario central.
* **RNF05 (Idempotencia):** El reenvío de una misma transacción por UUID no duplicará registros.
* **RNF06 (Recuperación ante fallos):** Operaciones pendientes se conservan en cliente si falla la red.
* **RNF07 (Mantenibilidad):** Separación limpia de capas (presentación, negocio, datos y sincronización).
* **RNF08 (Compatibilidad):** PWA funcional en navegadores web modernos; Móvil en Flutter Android.
* **RNF09 (Rendimiento):** Consultas indexadas por tenant y tiempos de respuesta ágiles.
* **RNF10 (Observabilidad):** Registro de logs detallados en el proceso de sincronización.
* **RNF11 (Calidad):** Pruebas automatizadas de reglas críticas en backend.
* **RNF12 (Coherencia documental):** Modelado UML/ICONIX fiel a la solución implementada.

---

## 5. Reglas de Negocio (RN)

* **RN-01 (Aislamiento Estricto):** Ningún usuario de una Empresa A podrá ver, modificar o eliminar registros de una Empresa B.
* **RN-02 (Límites por Plan de Suscripción):**
  * **Plan Básico:** Hasta 2 sucursales activas. Sin reportes generativos de IA.
  * **Plan Profesional:** Hasta 10 sucursales activas. Con reportes generativos de IA habilitados.
* **RN-03 (Ventas Offline):** Las ventas registradas sin conexión son obligatoriamente de contado (efectivo).
* **RN-04 (Idempotencia Transaccional):** Toda operación offline lleva un UUID v4 generado en cliente. Transacciones repetidas se confirman sin reprocesar inventario.
* **RN-05 (Gestión de Conflictos):** Si al sincronizar una venta offline no hay stock central suficiente, la operación se marca en estado `CONFLICTO` para ajuste administrativo.
* **RN-06 (Plazo Máximo de Cambio):** Solo se admiten cambios de prendas si la venta original tiene una antigüedad menor o igual a 30 días.

---

## 6. Casos de Uso (CU)

### PAQ-01: Gestión SaaS y Multitenant
* **CU-01:** Registrar empresa contratante (Tenant) — *Actor: Superadministrador SaaS*
* **CU-02:** Administrar planes de suscripción — *Actor: Superadministrador SaaS*
* **CU-03:** Asignar y cambiar plan a una empresa — *Actor: Superadministrador SaaS*
* **CU-04:** Consultar estado y vigencia de la suscripción — *Actor: Administrador de Empresa*

### PAQ-02: Organización y Usuarios
* **CU-05:** Administrar sucursales (con validación de límite de plan) — *Actor: Administrador de Empresa*
* **CU-06:** Administrar usuarios y roles por empresa — *Actor: Administrador de Empresa*

### PAQ-03: Catálogo e Inventario
* **CU-07:** Administrar productos, variantes y categorías — *Actor: Administrador de Empresa*
* **CU-08:** Consultar y ajustar existencias de inventario por sucursal — *Actor: Administrador / Cajero*

### PAQ-04: Operaciones Offline y Sincronización
* **CU-09:** Descargar catálogo e inventario local (Cache PWA / SQLite) — *Actor: Cajero / Cliente*
* **CU-10:** Registrar venta de contado offline — *Actor: Cajero*
* **CU-11:** Registrar reserva de prendas offline — *Actor: Cajero / Cliente*
* **CU-12:** Consultar lista de operaciones locales pendientes — *Actor: Cajero*
* **CU-13:** Sincronizar cola de operaciones locales con backend — *Actor: Cajero / Sistema*
* **CU-14:** Resolver conflictos de stock post-sincronización — *Actor: Administrador de Empresa / Sistema*

### PAQ-05: Políticas Postventa
* **CU-15:** Registrar cambio de prendas de vestir — *Actor: Cajero*

### PAQ-06: Analítica con Machine Learning
* **CU-16:** Generar dataset sintético para entrenamiento — *Actor: Sistema*
* **CU-17:** Entrenar y consultar modelo supervisado (predicción de demanda) — *Actor: Administrador / Sistema*
* **CU-18:** Entrenar y consultar modelo no supervisado (segmentación / anomalías) — *Actor: Administrador / Sistema*
* **CU-19:** Visualizar dashboard analítico de negocio — *Actor: Administrador de Empresa*

### PAQ-07: Reportes Generativos con IA
* **CU-20:** Consultar reporte por lenguaje natural (texto o voz) — *Actor: Administrador de Empresa*
* **CU-21:** Visualizar reporte dinámico en tabla o gráfico — *Actor: Administrador de Empresa*
* **CU-22:** Exportar reporte generado a PDF o Excel — *Actor: Administrador de Empresa*

---

## 7. Arquitectura del Sistema

### 7.1 Esquema General en Capas

```text
┌────────────────────────────────────────────────────────────────────────┐
│                          CLIENTES FRONTEND                             │
│                                                                        │
│   [ Angular 20 PWA ]                         [ Flutter 3 Mobile App ]  │
│   ├── Service Worker (Caché Assets)          ├── UI Mobile Responsiva  │
│   ├── IndexedDB (Persistencia Local)         ├── SQLite (Persistencia) │
│   ├── Voice Input (Web Speech API)           ├── Cola de Sync Local    │
│   └── Offline Sync Manager                   └── Connectivity Handler  │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   │ HTTPS / JSON REST API           │
                   ▼                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI + Python)                       │
│                                                                        │
│   ├── Middleware Multitenant (Extracción y validación de tenant_id)    │
│   ├── Control de Acceso por Roles (RBAC: Superadmin, Admin, Cashier)   │
│   ├── API REST Routers:                                                │
│   │   ├── /tenants & /subscriptions (Gestión SaaS)                     │
│   │   ├── /branches, /users, /products, /inventory                     │
│   │   ├── /sync (Batch Idempotente con resolución de stock)            │
│   │   ├── /exchanges (Cambios de prendas en < 30 días)                 │
│   │   ├── /ml (Predicción de demanda y segmentación)                   │
│   │   └── /ai/reports (Reportes generativos con NL2SQL seguro)         │
│   │                                                                    │
│   ├── Servicios de Dominio:                                            │
│   │   ├── SyncService (Transacciones atómicas, validación UUID)        │
│   │   ├── SubscriptionValidator (Límites de sucursales y permisos)     │
│   │   ├── MLService (Scikit-Learn: Random Forest / K-Means)            │
│   │   └── GenerativeAIService (LLM prompt seguro + exportadores)       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  BASE DE DATOS CENTRAL (PostgreSQL)                    │
│                                                                        │
│   Esquema Multitenant Compartido con Discriminador Lógico:             │
│   ├── tenants, plans, subscriptions                                    │
│   ├── branches, users (filtrados por tenant_id)                        │
│   ├── products, categories, inventories (filtrados por tenant_id)      │
│   ├── sales, sale_details, reservations (filtrados por tenant_id)      │
│   └── sync_audit_logs, exchanges (filtrados por tenant_id)             │
└────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Estrategia Multitenant
* **Modelo:** Base de datos compartida con aislamiento lógico por columna discriminadora `tenant_id`.
* **Seguridad y Filtrado:** Cada token JWT contiene `tenant_id` y `role`. Una dependencia en FastAPI (`get_current_tenant`) inyecta el `tenant_id` en cada operación de base de datos. Ningún usuario de la Empresa A puede consultar o modificar datos de la Empresa B.

---

## 8. Modelo de Dominio y Base de Datos

### 8.1 Entidades Clave y Relaciones

1. **`tenants`:** Entidad raíz de empresa contratante (`id`, `name`, `tax_id`, `domain_slug`, `status`, `created_at`).
2. **`plans`:** Planes de suscripción (`id`, `name`, `max_branches`, `has_ai_reports`, `price_monthly`, `is_active`).
3. **`subscriptions`:** Suscripción activa (`id`, `tenant_id`, `plan_id`, `start_date`, `end_date`, `status`).
4. **`branches`:** Sucursales pertenecientes a un tenant (`id`, `tenant_id`, `name`, `address`, `phone`, `is_active`).
5. **`users`:** Usuarios asociados a tenant y sucursal (`id`, `tenant_id`, `branch_id`, `email`, `hashed_password`, `role`).
6. **`products` & `product_variants`:** Prendas y variantes (`id`, `tenant_id`, `name`, `sku`, `category_id`, `size`, `color`, `price`).
7. **`inventories`:** Existencias por sucursal (`id`, `tenant_id`, `branch_id`, `variant_id`, `stock_quantity`, `reserved_quantity`).
8. **`sales` & `sale_details`:** Ventas de contado (`id`, `uuid`, `tenant_id`, `branch_id`, `user_id`, `total_amount`, `payment_method`, `sync_status`, `created_at`).
9. **`reservations`:** Reservas de prendas (`id`, `uuid`, `tenant_id`, `branch_id`, `customer_name`, `status`, `created_at`).
10. **`exchanges`:** Registro de cambio de prendas (`id`, `tenant_id`, `branch_id`, `original_sale_id`, `returned_variant_id`, `new_variant_id`, `price_difference`, `created_at`).

---

## 9. Arquitectura de Operaciones Offline y Sincronización

### 9.1 Almacenamiento Local
* **Web (Angular PWA):** Persistencia en **IndexedDB** para almacenar:
  * Catálogo descargado (productos, variantes y precios).
  * Inventario local conocido.
  * Cola de transacciones locales pendientes (`sync_queue`).
* **Móvil (Flutter):** Persistencia en **SQLite** (`sqflite`) con esquema réplica para catálogo y cola de transacciones locales.

### 9.2 Protocolo de Sincronización e Idempotencia
1. Cada transacción offline genera en el cliente un identificador universal único (**UUID v4**).
2. Estados de la transacción local:
   * `LOCAL`: Registrada sin conexión, pendiente de envío.
   * `ENVIADO`: En tránsito hacia el backend.
   * `CONFIRMADO`: Aceptada por el servidor y descontada del inventario central.
   * `CONFLICTO`: Discrepancia detectada (ej. stock central insuficiente).
3. **Idempotencia (RNF05):** Si el servidor recibe una transacción con un UUID ya registrado previamente, no vuelve a decrementar el inventario ni a duplicar la venta; simplemente responde con la confirmación de la venta existente.
4. **Resolución de Conflictos de Stock (RN-05):** Si el inventario central es insuficiente para cubrir la venta registrada offline, la transacción se almacena en estado `CONFLICTO`, generando una alerta de inventario y notificación al administrador para compensación administrativa.

---

## 10. Módulo de Analítica y Machine Learning

### 10.1 Componentes del Módulo
1. **Generador de Datos Sintéticos:** Script para generar datos históricos de ventas multitenant con distribución realista (temporadas, picos semanales, sucursales y categorías).
2. **Modelo Supervisado (Predicción de Demanda / Ventas):**
   * Algoritmo: Regresión con *Random Forest* o *Gradient Boosting* de `scikit-learn`.
   * Entrada: Sucursal, categoría de prenda, mes, día de semana y tendencia histórica.
   * Salida: Demanda estimada en unidades para optimización de inventario.
3. **Modelo No Supervisado (Segmentación de Clientes):**
   * Algoritmo: Clustering *K-Means* basado en métricas RFM (Recencia, Frecuencia, Monto monetario).
   * Salida: Segmentos de clientes (Frecuentes, Ocasionales, Alto Valor).
4. **Dashboard Analítico:** Componente visual interactivo en Angular con gráficos (barras, líneas, donas) para visualización de predicciones y KPIs.

---

## 11. Módulo de Reportes Generativos con IA

### 11.1 Especificaciones de Operación
1. **Entrada:** Lenguaje natural escrito en campo de búsqueda o dictado por voz utilizando **Web Speech API** en el navegador.
2. **Procesamiento en Backend:**
   * Recepción del texto de consulta.
   * Validación de plan: si el tenant posee Plan Básico, se retorna HTTP 403.
   * El servicio de IA analiza la intención y genera los filtros de la consulta inyectando de forma estricta e inmutable el `tenant_id` actual.
3. **Mínimo 4 Reportes Demostrables:**
   * Ventas agrupadas por sucursal en un período determinado.
   * Top 10 productos más vendidos por categoría.
   * Comparativa de ventas entre sucursales de los últimos 3 meses.
   * Productos con menor existencia y riesgo de agotamiento.
4. **Visualización y Exportación:**
   * Presentación dinámica en tabla o gráfico según el tipo de datos.
   * Botones de descarga directa a formato **PDF** y hoja de cálculo **Excel**.

---

## 12. Estructura de Repositorios y Ejecución Local

### 12.1 Distribución del Proyecto
```text
/home/ovando/Projects/SI2/FashionStore-SaaS/
│
├── backend/            # Python 3.12 + FastAPI + PostgreSQL (Repo Git independiente)
├── frontend/           # Angular 20 + PWA + Three.js (Repo Git independiente)
├── mobile/             # Flutter 3 + Dart + SQLite (Repo Git independiente)
├── docs/               # DOCUMENTACION_PARCIAL2.md
└── design/             # Modelos 3D y diagramas
```

### 12.2 Ejecución Local
* **Backend:**
  ```bash
  cd /home/ovando/Projects/SI2/FashionStore-SaaS/backend
  source .venv/bin/activate
  uvicorn main:app --reload --port 8000
  ```
* **Frontend:**
  ```bash
  cd /home/ovando/Projects/SI2/FashionStore-SaaS/frontend
  npm run start
  ```
* **Mobile:**
  ```bash
  cd /home/ovando/Projects/SI2/FashionStore-SaaS/mobile
  flutter run
  ```
