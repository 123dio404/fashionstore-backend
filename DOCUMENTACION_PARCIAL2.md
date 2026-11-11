# FashionStore SaaS — Documentación del Segundo Parcial
**Materia:** Sistemas de Información II (INF412)  
**Docente:** MSc. Ing. Angélica Garzón Cuéllar  
**Plataforma:** FashionStore SaaS (E-Commerce Multitenant con Persistencia Offline e Inteligencia Artificial)

---

## 1. Aspectos Generales y Descripción del Sistema
* **Nombre del Producto:** **FashionStore SaaS**
* **Definición:** Plataforma de comercio electrónico multitenant para empresas de indumentaria textil bajo el modelo Software as a Service (SaaS). Incorpora gestión de suscripciones (Planes Básico, Profesional y Empresarial), clientes con soporte offline (PWA con IndexedDB y Móvil Flutter con SQLite), motor de sincronización e idempotencia para ventas de contado y reservas, políticas postventa para cambio de prendas, analítica inteligente con Machine Learning (datos sintéticos, modelos supervisados y no supervisados) y reportes generativos mediante IA en lenguaje natural (texto y voz).
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
* **RF02:** Administrar catálogo de planes de suscripción (Básico, Profesional y Empresarial).
* **RF03:** Asignar y cambiar planes de suscripción con fechas de inicio y vencimiento.
* **RF04:** Restringir operaciones y recursos automáticamente según los límites del plan contratado.

#### PAQ-02: Organización y Usuarios
* **RF05:** Registrar y administrar sucursales por empresa (máximo 2 en Básico, 5 en Profesional y 15 en Empresarial).
* **RF06:** Gestionar usuarios con roles (`Superadmin`, `Tenant Admin`, `Cajero`, `Cliente`).
* **RF07:** Aislar la información impidiendo accesos cruzados entre empresas en todo el backend.

#### PAQ-03: Catálogo e Inventario
* **RF08:** Administrar prendas con categorías, temporadas, variantes de talla y color, material textil (alergias/estación) y soporte multicolor.
* **RF08-A (Precios Menudeo y Mayorista):** Configurar precio por menor y precio por mayor activado automáticamente según umbrales de cantidad en carrito (ej. >= 3 unidades o docena).
* **RF08-B (Liquidación de Fin de Temporada):** Aplicación masiva de descuentos por lote (40% a 60%) en prendas de temporada saliente para recuperación de capital sin afectar novedades.
* **RF09:** Controlar existencias de inventario independientes por cada sucursal física.
* **RF09-B (Compras y Abastecimiento):** Registrar notas de compra e ingreso formal de mercadería a proveedores con actualización automática de stock y costos.

#### PAQ-04: Operaciones Offline y Sincronización
* **RF10:** Descargar y almacenar localmente el catálogo y stock conocido (IndexedDB en PWA, SQLite en Móvil).
* **RF11:** Registrar ventas de contado sin conexión a Internet generando un UUID único en cliente.
* **RF12:** Registrar reservas de prendas sin conexión a Internet.
* **RF13:** Consultar lista de ventas y reservas locales pendientes de sincronización.
* **RF14:** Sincronizar cola de operaciones pendientes al recuperar conectividad a Internet.
* **RF15:** Validar idempotencia en backend para no duplicar ventas ante reintentos de envío o clics compulsivos.
* **RF16:** Detectar y gestionar conflictos de inventario cuando el stock central sea insuficiente.
* **RF16-B (Máquina de Estados de Despacho):** Trazabilidad del pedido (`PAGADO` -> `POR_DESPACHAR` -> `ENVIADO` -> `ENTREGADO_CONFORME`) con confirmación de conformidad del cliente en app o web.

#### PAQ-05: Políticas Postventa
* **RF17:** Registrar cambios de prendas de vestir adquiridas dentro de un tiempo determinado (30 días).
* **RF17-B (Notificación Push de Diferencia):** Notificar al móvil del cliente si la nueva prenda tiene mayor costo para cobro inmediato en pasarela.
* **RF17-C (Políticas de Reembolso Financiero):** Si la prenda nueva cuesta menos o se desiste, liquidar el reembolso en el arqueo mensual de caja con 10% de retención administrativa.
* **RF18:** Actualizar inventario atómicamente por reingreso (+1) de la prenda devuelta y egreso (-1) de la nueva prenda.

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
* **RF28:** Restringir el acceso a reportes con IA a tenants con Plan Profesional o Empresarial; el Plan Básico recibe HTTP 403.

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
  * **Plan Básico:** Bs. 29.99/mes · hasta 2 sucursales activas · sin reportes generativos de IA.
  * **Plan Profesional:** Bs. 69.99/mes · hasta 5 sucursales activas · con reportes generativos de IA.
  * **Plan Empresarial:** Bs. 129.99/mes · hasta 15 sucursales activas · con reportes generativos de IA.
* **RN-03 (Ventas Offline):** Las ventas registradas sin conexión son obligatoriamente de contado (efectivo).
* **RN-04 (Idempotencia Transaccional):** Toda operación offline lleva un UUID v4 generado en cliente. Transacciones repetidas se confirman sin reprocesar inventario.
* **RN-05 (Gestión de Conflictos):** El stock se descuenta con una operación atómica y condicional (`stock_actual - stock_reservado >= cantidad`). La primera venta que completa el descuento conserva la unidad; la segunda se registra como `CONFLICTO` sin sobreventa, con pago pendiente y sin reintento automático. El administrador resuelve el conflicto con `compensar` (reembolso y notificación al cliente) o `reasignar` (si reapareció stock, confirma la venta).
* **RN-06 (Plazo Máximo de Cambio):** Solo se admiten cambios de prendas si la venta original tiene una antigüedad menor o igual a 30 días.
* **RN-07 (Doble Esquema de Precios):** Las prendas cuentan con precio minorista y mayorista. El precio mayorista se activa de forma automática cuando el cliente alcanza la cantidad mínima umbral en su carrito.
* **RN-08 (Descuento de Stock Condicional):** En pedidos en línea, el stock físico permanece en reserva/intacto y se descuenta únicamente tras la confirmación exitosa de la pasarela de pagos.
* **RN-09 (Políticas Financieras de Reembolso):** En devoluciones donde aplique reembolso de dinero, se retiene un 10% por costos administrativos y el saldo se programa para liquidación en el cierre mensual de caja.

---

## 6. Casos de Uso (CU)

### PAQ-01: Gestión SaaS y Multitenant
* **CU-01:** Registrar empresa contratante (Tenant) — *Actor: Superadministrador SaaS* [WEB]
* **CU-02:** Administrar planes de suscripción — *Actor: Superadministrador SaaS* [WEB]
* **CU-03:** Asignar y cambiar plan de suscripción — *Actor: Superadministrador SaaS* [WEB]
* **CU-04:** Monitorear estado y vigencia de suscripción — *Actor: Administrador de Empresa* [WEB]

### PAQ-02: Organización y Usuarios
* **CU-05:** Administrar sucursales físicas — *Actor: Administrador de Empresa* [WEB]
* **CU-06:** Administrar usuarios y roles por empresa — *Actor: Administrador de Empresa* [WEB]

### PAQ-03: Catálogo e Inventario
* **CU-07:** Administrar prendas y variantes del catálogo — *Actor: Administrador de Empresa* [WEB]
* **CU-08:** Controlar existencias de inventario por sucursal — *Actor: Administrador / Cajero* [WEB / MOVIL]

### PAQ-04: Operaciones Offline y Sincronización
* **CU-09:** Habilitar catálogo y existencias fuera de línea — *Actor: Cajero / Cliente* [WEB / MOVIL]
* **CU-10:** Registrar venta de contado fuera de línea — *Actor: Cajero / Encargado (WEB) · Cliente (MOVIL)* [WEB / MOVIL]
* **CU-11:** Registrar reserva de prendas fuera de línea — *Actor: Cajero / Cliente* [WEB / MOVIL]
* **CU-12:** Monitorear operaciones pendientes de sincronización — *Actor: Cajero* [WEB / MOVIL]
* **CU-13:** Sincronizar transacciones locales con la nube — *Actor: Cajero / Sistema* [WEB / MOVIL]
* **CU-14:** Conciliar discrepancias de inventario post-sincronización — *Actor: Administrador de Empresa / Sistema* [WEB]

### PAQ-05: Políticas Postventa
* **CU-15:** Tramitar cambio de prendas de vestir — *Actor: Cajero / Cliente* [WEB / MOVIL]

### PAQ-06: Analítica con Machine Learning
* **CU-16:** Simular histórico de ventas para calibración de modelos — *Actor: Administrador / Sistema* [WEB]
* **CU-17:** Pronosticar demanda futura de prendas por sucursal — *Actor: Administrador / Sistema* [WEB]
* **CU-18:** Segmentar clientes por comportamiento de compra (RFM) — *Actor: Administrador / Sistema* [WEB]
* **CU-19:** Visualizar tablero analítico de rendimiento comercial — *Actor: Administrador de Empresa* [WEB]

### PAQ-07: Reportes Generativos con IA
* **CU-20:** Generar reporte analítico asistido por IA (Texto / Voz) — *Actor: Administrador de Empresa* [WEB / MOVIL]
* **CU-21:** Explorar resultados analíticos en tablas y gráficos dinámicos — *Actor: Administrador de Empresa* [WEB]
* **CU-22:** Exportar informes gerenciales a PDF y Excel — *Actor: Administrador de Empresa* [WEB]

### 6.1 Especificación detallada del CU-10 — Registrar venta de contado fuera de línea

**Actores**
* **Primario (WEB):** Cajero / Encargado con caja abierta en el POS.
* **Primario (MÓVIL):** Cliente autenticado que compra de contado; la app móvil es *purchase-only*, no abre caja ni ejecuta arqueo.
* **Sistema:** `SyncManagerService` (web, IndexedDB) / `SyncManager` (móvil, SQLite) y `POST /api/v1/sync/batch` (`process_sync_batch`).

**Precondiciones**
1. Usuario autenticado con rol `Cajero`, `Encargado`, `Administrador` o `Cliente` según el canal, y `tenant_id` activo.
2. Sucursal existente, activa y perteneciente al tenant de la sesión.
3. Copia local de catálogo y existencias descargada previamente (CU-09). En web, la caja debe haberse abierto al menos una vez con conexión.
4. Al menos una línea de venta con `stock_id` real y disponibilidad en la copia local.
5. Dispositivo sin conectividad, o checkout remoto fallido antes de confirmar la venta.

**Flujo principal**
1. El cajero selecciona la sucursal/caja y agrega prendas por variante, SKU o lector de barras.
2. El sistema valida que cada línea pertenezca a la sucursal y que `cantidad <= available_stock` local.
3. El cajero elige **Efectivo** (único método habilitado sin conexión, RN-03) y confirma el cobro.
4. El cliente móvil confirma la compra con método efectivo; la app fuerza este método si perdió la red.
5. El cliente de sincronización genera un **UUID v4** y guarda la operación como `LOCAL` en IndexedDB/SQLite.
6. El sistema descuenta el espejo local de existencias, actualiza el arqueo de caja (solo web) y emite un **comprobante provisional** con UUID, fecha, sucursal, cajero, ítems y total.
7. Al recuperar la conexión, el cliente envía el lote a `POST /api/v1/sync/batch`.
8. El backend valida tenant, sucursal activa, método de pago efectivo, idempotencia del UUID y disponibilidad central.
9. El backend descuenta el stock con `UPDATE ... WHERE stock_actual - stock_reservado >= cantidad`, crea `Sale`, `SaleItem`, `SalePayment` e `InventoryMovement`, y responde `CONFIRMADO`.
10. El cliente marca la operación como `CONFIRMADO` y el comprobante definitivo reemplaza al provisional.

**Flujos alternativos**
* **A1 — Stock local insuficiente:** el cobro se bloquea con el disponible real; se pide ajustar cantidad o reconectar.
* **A2 — Sucursal inactiva o sin copia local:** el cobro se bloquea; se solicita abrir caja con conexión al menos una vez.
* **A3 — Método distinto de efectivo sin conexión:** la UI deshabilita tarjeta, QR y datáfono; si llegara al backend, la operación se marca `CONFLICTO`, no se descuenta stock y el pago queda `pendiente`.
* **A4 — UUID ya procesado (reintento o doble clic):** el backend responde `DUPLICADO_IDEMPOTENTE`; no se crea otra venta ni se vuelve a descontar inventario (RNF05).
* **A5 — UUID usado por otra empresa:** se rechaza como `CONFLICTO`; el inventario de ambas empresas permanece intacto (RN-01).
* **A6 — Sin stock central al sincronizar (dos dispositivos, última unidad):** la primera operación que completa el descuento atómico gana; la segunda queda `CONFLICTO` sin sobreventa. El administrador resuelve con `compensar` (reembolso + notificación al cliente) o `reasignar` (si reapareció stock).
* **A7 — Falla de red durante la sincronización:** la operación permanece `LOCAL` y se reintenta; el UUID evita duplicados.

**Postcondiciones**
* **Éxito:** venta registrada una sola vez, stock local y central descontados atómicamente, movimiento de inventario `venta`, pago `completado`, arqueo actualizado (web) y comprobante provisional + definitivo emitidos.
* **Conflicto:** venta en estado `CONFLICTO` con pago `pendiente`; no hay sobreventa. Tras la resolución administrativa, la venta queda `RESUELTO_ADMIN` con pago `reembolsado` (compensación) o `completado` (reasignación), y el cliente afectado recibe notificación.
* **Idempotencia:** un reenvío del mismo UUID no altera stock, ventas ni movimientos.

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
   * Validación de plan: si el tenant posee Plan Básico (sin `has_ai_reports`), se retorna HTTP 403; los planes Profesional y Empresarial tienen acceso habilitado.
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
