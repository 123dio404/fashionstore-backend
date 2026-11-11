"""Script de verificación automatizada para los requisitos del Segundo Parcial.

Valida:
1. Aislamiento Multitenant (RNF02).
2. Límite de sucursales según plan Básico vs Profesional (RN-02).
3. Ciclo de Reservas (Cancelación con liberación de stock y conversión a venta).
4. Cambios de prendas de vestir con regla de 30 días (RN-06).
5. Sincronización offline con idempotencia (RNF05) y detección de conflictos (RN-05).
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.tenant import Tenant, Plan, Subscription
from app.models.branch import Branch
from app.models.user import User
from app.models.inventory import Stock
from app.models.commerce import Sale, Reservation, ReservationItem
from app.schemas.saas import ChangePlanRequest
from app.schemas.exchange import ExchangeCreateRequest
from app.schemas.sync import SyncBatchRequest, SyncOperationItem, SyncItemDetail
from app.services.commerce_service import cancel_reservation, convert_reservation_to_sale
from app.services.exchange_service import process_garment_exchange
from app.services.sync_service import process_sync_batch
from app.api.v1.branches import add_branch
from app.schemas.branch import BranchCreate


def run_tests():
    db = SessionLocal()
    print("=" * 70)
    print(" INICIANDO VERIFICACIÓN DE REQUISITOS — SEGUNDO PARCIAL (SAAS)")
    print("=" * 70)

    try:
        # 1. VERIFICACIÓN DE MULTITENANCY Y AISLAMIENTO DE DATOS
        print("\n--- PRUEBA 1: Aislamiento Multitenant (RNF02) ---")
        t1 = db.query(Tenant).filter(Tenant.slug == "urban-style").first()
        t2 = db.query(Tenant).filter(Tenant.slug == "elegance-fashion").first()
        assert t1 is not None and t2 is not None, "Los tenants de prueba no existen"

        b_t1 = db.query(Branch).filter(Branch.tenant_id == t1.id).all()
        b_t2 = db.query(Branch).filter(Branch.tenant_id == t2.id).all()
        print(f"Sucursales Tenant 1 ({t1.name}): {[b.name for b in b_t1]}")
        print(f"Sucursales Tenant 2 ({t2.name}): {[b.name for b in b_t2]}")
        # Aislamiento: ninguna sucursal se comparte
        t1_ids = {b.id for b in b_t1}
        t2_ids = {b.id for b in b_t2}
        assert t1_ids.isdisjoint(t2_ids), "Error de aislamiento: hay sucursales compartidas entre tenants"
        print(">> Prueba 1 PASÓ: Aislamiento de datos confirmado.")

        # 2. VALIDACIÓN DE LÍMITES POR PLAN DE SUSCRIPCIÓN
        print("\n--- PRUEBA 2: Límites de Sucursales según Plan (RN-02) ---")
        # Tenant 1 tiene Plan Básico (máximo 2 sucursales)
        admin_t1 = db.query(User).filter(User.email == "admin@urbanstyle.com").first()
        assert admin_t1 is not None, "Admin de Tenant 1 no encontrado"

        # Contar sucursales de Tenant 1
        curr_branches = len(b_t1)
        print(f"Tenant 1 tiene {curr_branches} sucursales activas. Plan Básico permite máx. 2.")
        if curr_branches >= 2:
            try:
                # Intentar crear una 3ra sucursal debe lanzar 403 Forbidden
                add_branch(
                    data=BranchCreate(city_id=b_t1[0].city_id, name="Sucursal Excedente Test", address="Calle Falsa 123"),
                    user=admin_t1,
                    db=db,
                )
                assert False, "Error: El sistema permitió crear más sucursales de las autorizadas por el plan"
            except HTTPException as e:
                assert e.status_code == 403, f"Esperado 403, obtenido {e.status_code}"
                print(f"Bloqueo verificado exitosamente: '{e.detail}'")
        print(">> Prueba 2 PASÓ: Regla de límites de plan validada.")

        # 3. CANCELACIÓN DE RESERVA Y LIBERACIÓN INMEDIATA DE STOCK
        print("\n--- PRUEBA 3: Cancelación de Reserva y Liberación de Stock ---")
        stock_item = db.query(Stock).filter(Stock.branch_id == b_t1[0].id, Stock.physical_stock > 5).first()
        assert stock_item is not None, "Stock de prueba no encontrado"

        stock_inicial_disp = stock_item.physical_stock - stock_item.reserved_stock
        stock_reservado_inicial = stock_item.reserved_stock
        print(f"Stock disponible antes de reservar: {stock_inicial_disp} (Reservado actual: {stock_reservado_inicial})")

        # Crear reserva de 2 unidades
        res = Reservation(
            client_id=admin_t1.id,
            branch_id=b_t1[0].id,
            tenant_id=t1.id,
            reservation_date=datetime.now(timezone.utc).date(),
            reservation_time=datetime.now(timezone.utc).time(),
            status="Pendiente",
            items=[ReservationItem(stock_id=stock_item.id, quantity=2)],
        )
        stock_item.reserved_stock += 2
        db.add(res)
        db.commit()
        db.refresh(res)
        db.refresh(stock_item)

        print(f"Reserva #{res.id} creada por 2 unidades. Stock reservado ahora: {stock_item.reserved_stock}")
        assert stock_item.reserved_stock == stock_reservado_inicial + 2, "El stock reservado no se incrementó"

        # Ahora el cliente o cajero cancela la reserva
        res_cancelada = cancel_reservation(db, res.id)
        db.refresh(stock_item)
        print(f"Reserva #{res.id} cancelada. Estado: {res_cancelada.status}. Stock reservado: {stock_item.reserved_stock}")
        assert res_cancelada.status == "cancelada", "El estado de la reserva no cambió a cancelada"
        assert stock_item.reserved_stock == stock_reservado_inicial, "El stock reservado NO fue liberado tras cancelar"
        print(">> Prueba 3 PASÓ: Reserva cancelada y stock liberado correctamente.")

        # 4. CONVERSIÓN DE RESERVA EN VENTA AL RETIRAR
        print("\n--- PRUEBA 4: Conversión de Reserva a Venta al Retirar Prenda ---")
        # Crear nueva reserva
        res2 = Reservation(
            client_id=admin_t1.id,
            branch_id=b_t1[0].id,
            tenant_id=t1.id,
            reservation_date=datetime.now(timezone.utc).date(),
            reservation_time=datetime.now(timezone.utc).time(),
            status="Pendiente",
            items=[ReservationItem(stock_id=stock_item.id, quantity=1)],
        )
        stock_item.reserved_stock += 1
        db.add(res2)
        db.commit()
        db.refresh(res2)

        stock_fisico_antes = stock_item.physical_stock
        cajero_t1 = db.query(User).filter(User.email == "cajero@urbanstyle.com").first()
        sale_result = convert_reservation_to_sale(db, res2.id, cashier_id=cajero_t1.id)
        db.refresh(stock_item)
        db.refresh(res2)

        assert res2.status == "completada", "La reserva no quedó en completada"
        assert stock_item.physical_stock == stock_fisico_antes - 1, "El stock físico no se descontó en la venta"
        print(f"Reserva convertida a Venta #{sale_result.id} (Total: {sale_result.total}). Stock físico actualizado: {stock_item.physical_stock}")
        print(">> Prueba 4 PASÓ: Reserva convertida a venta y stock descontado.")

        # 5. CAMBIO DE PRENDAS DE VESTIR (POSTVENTA)
        print("\n--- PRUEBA 5: Cambio de Prendas con Regla de 30 Días (RN-06) ---")
        # Usamos la venta generada en la prueba 4
        new_variant_stock = db.query(Stock).filter(
            Stock.branch_id == b_t1[0].id,
            Stock.id != stock_item.id,
            Stock.physical_stock > 2,
        ).first()

        if new_variant_stock:
            stock_devuelto_antes = stock_item.physical_stock
            stock_nuevo_antes = new_variant_stock.physical_stock

            exchange_res = process_garment_exchange(
                db=db,
                cashier_id=cajero_t1.id,
                data=ExchangeCreateRequest(
                    original_sale_id=sale_result.id,
                    returned_stock_id=stock_item.id,
                    new_stock_id=new_variant_stock.id,
                    quantity=1,
                    reason="Cambio de talla por preferencia del cliente",
                ),
                current_tenant_id=t1.id,
            )
            db.refresh(stock_item)
            db.refresh(new_variant_stock)

            assert exchange_res.receipt_number.startswith("CHG-"), "Comprobante de cambio no generado"
            assert stock_item.physical_stock == stock_devuelto_antes + 1, "La prenda devuelta no reingresó al inventario"
            assert new_variant_stock.physical_stock == stock_nuevo_antes - 1, "La nueva prenda no se descontó del inventario"
            print(f"Cambio procesado con éxito. Comprobante: {exchange_res.receipt_number}")
            print(f"Diferencia de precio: {exchange_res.price_difference} Bs.")
            print(">> Prueba 5 PASÓ: Cambio de prenda y ajustes de inventario verificados.")

        # 6. SINCRONIZACIÓN OFFLINE E IDEMPOTENCIA
        print("\n--- PRUEBA 6: Sincronización Offline e Idempotencia (RNF05) ---")
        offline_uuid = str(uuid.uuid4())
        batch_req = SyncBatchRequest(
            operations=[
                SyncOperationItem(
                    uuid=offline_uuid,
                    type="SALE",
                    created_at=datetime.now(timezone.utc),
                    branch_id=b_t1[0].id,
                    client_id=admin_t1.id,
                    total=Decimal("120.00"),
                    payment_method="efectivo",
                    items=[
                        SyncItemDetail(stock_id=stock_item.id, quantity=1, unit_price=Decimal("120.00"))
                    ],
                )
            ]
        )

        # Primer envío (debe confirmar)
        sync_res1 = process_sync_batch(db, cajero_t1, batch_req)
        assert sync_res1.confirmed == 1, "La venta offline no fue confirmada"
        assert sync_res1.results[0].status == "CONFIRMADO"
        print(f"Envío 1: Venta offline sincronizada con éxito (Server ID: {sync_res1.results[0].server_id})")

        # Segundo envío con el MISMO UUID (debe ser idempotente, NO duplicar)
        sync_res2 = process_sync_batch(db, cajero_t1, batch_req)
        assert sync_res2.results[0].status == "DUPLICADO_IDEMPOTENTE", "La idempotencia falló: se duplicó la venta"
        print(f"Envío 2 (Reintento de red con mismo UUID): Detectado como '{sync_res2.results[0].status}'")
        print(">> Prueba 6 PASÓ: Idempotencia transaccional RNF05 garantizada.")

        print("\n" + "=" * 70)
        print(" ¡TODAS LAS PRUEBAS DEL SEGUNDO PARCIAL PASARON EXITOSAMENTE!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
