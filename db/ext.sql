-- Extensiones de la aplicación sobre el esquema del examen (37 tablas originales intactas)
ALTER TABLE producto_variante ADD COLUMN IF NOT EXISTS id_talla BIGINT REFERENCES tallas(id) ON DELETE RESTRICT;
ALTER TABLE producto_variante ADD COLUMN IF NOT EXISTS id_color BIGINT REFERENCES color(id) ON DELETE RESTRICT;
ALTER TABLE inventario ADD COLUMN IF NOT EXISTS stock_reservado INTEGER NOT NULL DEFAULT 0;
ALTER TABLE inventario ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE movimiento_inventario ADD COLUMN IF NOT EXISTS tipo VARCHAR(30) NOT NULL DEFAULT 'ajuste';
ALTER TABLE movimiento_inventario ALTER COLUMN motivo SET DEFAULT '';

DO $$ BEGIN
  ALTER TABLE categoria ADD CONSTRAINT uq_categoria_nombre UNIQUE (nombre);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE tallas ADD CONSTRAINT uq_tallas_nombre UNIQUE (nombre);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE color ADD CONSTRAINT uq_color_nombre UNIQUE (nombre);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE sucursal ADD CONSTRAINT uq_sucursal_nombre UNIQUE (nombre);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE inventario ADD CONSTRAINT uq_inventario_sucursal_variante UNIQUE (id_sucursal, id_variante);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS ix_inventario_id_variante ON inventario (id_variante);
CREATE INDEX IF NOT EXISTS ix_inventario_id_sucursal ON inventario (id_sucursal);
CREATE INDEX IF NOT EXISTS ix_movimiento_inventario_id_inventario ON movimiento_inventario (id_inventario);
CREATE INDEX IF NOT EXISTS ix_producto_variante_id_producto ON producto_variante (id_producto);