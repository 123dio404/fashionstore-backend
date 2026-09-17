-- 1. USUARIOS Y ROLES
CREATE TABLE usuario (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    telefono VARCHAR(20),
    password VARCHAR(255) NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE rol (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE usuario_rol (
    id_usuario BIGINT NOT NULL,
    id_rol BIGINT NOT NULL,
    PRIMARY KEY (id_usuario, id_rol),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE,
    FOREIGN KEY (id_rol) REFERENCES rol(id) ON DELETE CASCADE
);

-- 2. RED GEOGRÁFICA Y SUCURSALES
CREATE TABLE ciudad (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE sucursal (
    id BIGSERIAL PRIMARY KEY,
    id_ciudad BIGINT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    direccion VARCHAR(255) NOT NULL,
    telefono VARCHAR(20),
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (id_ciudad) REFERENCES ciudad(id) ON DELETE RESTRICT
);

CREATE TABLE horario_sucursal (
    id BIGSERIAL PRIMARY KEY,
    id_sucursal BIGINT NOT NULL,
    dia_semana VARCHAR(20) NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    FOREIGN KEY (id_sucursal) REFERENCES sucursal(id) ON DELETE CASCADE
);

-- 3. CATÁLOGO DE PRODUCTOS Y PARÁMETROS
CREATE TABLE categoria (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE producto (
    id BIGSERIAL PRIMARY KEY,
    id_categoria BIGINT NOT NULL,
    precio NUMERIC(12, 2) NOT NULL,
    marca VARCHAR(100),
    nombre VARCHAR(150) NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (id_categoria) REFERENCES categoria(id) ON DELETE RESTRICT
);

CREATE TABLE producto_variante (
    id BIGSERIAL PRIMARY KEY,
    id_producto BIGINT NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    precio NUMERIC(12, 2) NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE
);

CREATE TABLE imagen_producto (
    id BIGSERIAL PRIMARY KEY,
    id_producto BIGINT NOT NULL,
    url_imagen VARCHAR(255) NOT NULL,
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE
);

CREATE TABLE tallas (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(20) NOT NULL
);

CREATE TABLE color (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL
);

CREATE TABLE temporada (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL
);

-- 4. INVENTARIO Y MOVIMIENTOS
CREATE TABLE inventario (
    id BIGSERIAL PRIMARY KEY,
    id_variante BIGINT NOT NULL,
    id_talla BIGINT NOT NULL,
    id_sucursal BIGINT NOT NULL,
    stock_actual INT NOT NULL DEFAULT 0,
    stock_minimo INT NOT NULL DEFAULT 0,
    FOREIGN KEY (id_variante) REFERENCES producto_variante(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_talla) REFERENCES tallas(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_sucursal) REFERENCES sucursal(id) ON DELETE RESTRICT
);

CREATE TABLE medida_prenda (
    id BIGSERIAL PRIMARY KEY,
    id_inventario BIGINT NOT NULL,
    pecho NUMERIC(6, 2),
    cintura NUMERIC(6, 2),
    cadera NUMERIC(6, 2),
    largo NUMERIC(6, 2),
    ancho_hombros NUMERIC(6, 2),
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (id_inventario) REFERENCES inventario(id) ON DELETE CASCADE
);

CREATE TABLE movimiento_inventario (
    id BIGSERIAL PRIMARY KEY,
    id_inventario BIGINT NOT NULL,
    cantidad INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR(255) NOT NULL,
    FOREIGN KEY (id_inventario) REFERENCES inventario(id) ON DELETE RESTRICT
);

-- 5. PROVEEDORES
CREATE TABLE proveedor (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ci VARCHAR(30) NOT NULL UNIQUE,
    telefono VARCHAR(20),
    email VARCHAR(150),
    direccion VARCHAR(255),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE producto_proveedor (
    id_producto BIGINT NOT NULL,
    id_proveedor BIGINT NOT NULL,
    precio_compra NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (id_producto, id_proveedor),
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE,
    FOREIGN KEY (id_proveedor) REFERENCES proveedor(id) ON DELETE RESTRICT
);

-- 6. CARRITO Y COMPRAS DIGITALES / PRESENCIALES
CREATE TABLE carrito (
    id BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'Activo',
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE carrito_detalle (
    id BIGSERIAL PRIMARY KEY,
    id_carrito BIGINT NOT NULL,
    id_inventario BIGINT NOT NULL,
    cantidad INT NOT NULL,
    precio NUMERIC(12, 2) NOT NULL,
    FOREIGN KEY (id_carrito) REFERENCES carrito(id) ON DELETE CASCADE,
    FOREIGN KEY (id_inventario) REFERENCES inventario(id) ON DELETE RESTRICT
);

CREATE TABLE venta (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    id_usuario BIGINT, -- Nulo si la compra es digital sin intervención de vendedor/cajero
    id_sucursal BIGINT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total NUMERIC(12, 2) NOT NULL,
    tipo_venta VARCHAR(30) NOT NULL,
    FOREIGN KEY (id_cliente) REFERENCES usuario(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE SET NULL,
    FOREIGN KEY (id_sucursal) REFERENCES sucursal(id) ON DELETE RESTRICT
);

CREATE TABLE detalle_venta (
    id BIGSERIAL PRIMARY KEY,
    id_venta BIGINT NOT NULL,
    id_inventario BIGINT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario NUMERIC(12, 2) NOT NULL,
    FOREIGN KEY (id_venta) REFERENCES venta(id) ON DELETE CASCADE,
    FOREIGN KEY (id_inventario) REFERENCES inventario(id) ON DELETE RESTRICT
);

CREATE TABLE pago (
    id BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL,
    monto NUMERIC(12, 2) NOT NULL,
    estado VARCHAR(30) NOT NULL,
    fecha_pago TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    referencia VARCHAR(100),
    FOREIGN KEY (id_pedido) REFERENCES venta(id) ON DELETE CASCADE
);

-- 7. RESERVAS Y PROBADORES FÍSICOS
CREATE TABLE reserva (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    id_sucursal BIGINT NOT NULL,
    fecha_reserva DATE NOT NULL,
    hora_reserva TIME NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'Pendiente',
    FOREIGN KEY (id_cliente) REFERENCES usuario(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_sucursal) REFERENCES sucursal(id) ON DELETE RESTRICT
);

CREATE TABLE detalle_reserva (
    id BIGSERIAL PRIMARY KEY,
    id_reserva BIGINT NOT NULL,
    id_inventario BIGINT NOT NULL,
    cantidad INT NOT NULL,
    FOREIGN KEY (id_reserva) REFERENCES reserva(id) ON DELETE CASCADE,
    FOREIGN KEY (id_inventario) REFERENCES inventario(id) ON DELETE RESTRICT
);

-- 8. VESTIDOR VIRTUAL (AR) Y RECOMENDADOR CON IA
CREATE TABLE perfil_corporal (
    id BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL UNIQUE,
    altura NUMERIC(5, 2),
    peso NUMERIC(5, 2),
    pecho NUMERIC(5, 2),
    cintura NUMERIC(5, 2),
    cadera NUMERIC(5, 2),
    largo_pierna NUMERIC(5, 2),
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE recomendacion_talla (
    id BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    id_producto BIGINT NOT NULL,
    nivel_confianza NUMERIC(5, 2) NOT NULL,
    resultado VARCHAR(20) NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE
);

CREATE TABLE sesion_probador_virtual (
    id BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE resultado_probador (
    id BIGSERIAL PRIMARY KEY,
    id_sesion BIGINT NOT NULL,
    id_variante BIGINT NOT NULL,
    id_talla BIGINT NOT NULL,
    resultado_url VARCHAR(255) NOT NULL,
    nivel_confianza NUMERIC(5, 2) NOT NULL,
    FOREIGN KEY (id_sesion) REFERENCES sesion_probador_virtual(id) ON DELETE CASCADE,
    FOREIGN KEY (id_variante) REFERENCES producto_variante(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_talla) REFERENCES tallas(id) ON DELETE RESTRICT
);

CREATE TABLE recomendacion (
    id BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE detalle_recomendacion (
    id_recomendacion BIGINT NOT NULL,
    id_producto BIGINT NOT NULL,
    puntuacion NUMERIC(5, 2) NOT NULL,
    motivo VARCHAR(255),
    PRIMARY KEY (id_recomendacion, id_producto),
    FOREIGN KEY (id_recomendacion) REFERENCES recomendacion(id) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE
);

-- 9. PROMOCIONES, COLECCIONES Y CHATBOT
CREATE TABLE promocion (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    tipo_descuento VARCHAR(30) NOT NULL,
    valor_descuento NUMERIC(12, 2) NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE producto_promocion (
    id_producto BIGINT NOT NULL,
    id_promocion BIGINT NOT NULL,
    PRIMARY KEY (id_producto, id_promocion),
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE,
    FOREIGN KEY (id_promocion) REFERENCES promocion(id) ON DELETE CASCADE
);

CREATE TABLE coleccion (
    id_coleccion BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE
);

CREATE TABLE coleccion_producto (
    id_coleccion BIGINT NOT NULL,
    id_producto BIGINT NOT NULL,
    PRIMARY KEY (id_coleccion, id_producto),
    FOREIGN KEY (id_coleccion) REFERENCES coleccion(id_coleccion) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES producto(id) ON DELETE CASCADE
);

CREATE TABLE conversacion_chat (
    id_conversacion BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE mensaje_chat (
    id_mensaje BIGSERIAL PRIMARY KEY,
    id_conversacion BIGINT NOT NULL,
    emisor VARCHAR(30) NOT NULL,
    contenido TEXT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_conversacion) REFERENCES conversacion_chat(id_conversacion) ON DELETE CASCADE
);