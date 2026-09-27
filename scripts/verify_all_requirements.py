import os
import sys
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.services.customer_experience_service import generate_recommendations
from app.services.commerce_service import checkout, add_to_cart, get_or_create_cart
from app.schemas.commerce import CheckoutRequest, CartItemRequest
from app.providers.payments import get_payment_provider, generate_qr_base64
from app.providers.business import get_notification_provider
from app.models.inventory import Stock

def run_tests():
    db = SessionLocal()
    print("=" * 60)
    print("INICIANDO PRUEBAS DE REQUISITOS Y CASOS DE USO")
    print("=" * 60)

    try:
        # 1. AI RECOMMENDATIONS WITH SIZE, SEASON, AND CUSTOMER PROFILE
        print("\n--- PRUEBA 1: Recomendaciones IA con Talla, Temporada y Perfil ---")
        rec_obj = generate_recommendations(db, user_id=1, limit=3)
        recs = rec_obj.items
        print(f"Total recomendaciones obtenidas: {len(recs)}")
        assert len(recs) > 0, "No se generaron recomendaciones"
        for r in recs:
            print(f" - Producto ID {r.product_id}: Score={r.score} | Razón: {r.reason}")
        print(">> Prueba 1 PASÓ exitosamente.")

        # 2. STRIPE QR CODE GENERATION
        print("\n--- PRUEBA 2: Generación de Código QR Stripe para pagos ---")
        qr_provider = get_payment_provider("stripe_qr")
        qr_res = qr_provider.create_intent(
            amount=Decimal("89.99"),
            currency="usd",
            idempotency_key="TEST-QR-1",
            metadata={"product": "Chaqueta"}
        )
        assert qr_res["status"] == "succeeded"
        assert "QR-STRIPE-" in qr_res["id"] or "SIM-QR-" in qr_res["id"]
        assert qr_res["qr_code_base64"].startswith("data:image/png;base64,")
        print(f"QR generado correctamente. Ref: {qr_res['id']}")
        print(f"Data URI (primeros 50 caracteres): {qr_res['qr_code_base64'][:50]}...")
        print(">> Prueba 2 PASÓ exitosamente.")

        # 3. NOTIFICATION PROVIDER DISPATCH
        print("\n--- PRUEBA 3: Despacho de Notificaciones de Compra/Transacción ---")
        notif_provider = get_notification_provider()
        notif_res = notif_provider.send(
            event="purchase.completed",
            sale_id=123,
            total="89.99",
            payment_method="stripe_qr",
            reference="STRIPE-QR-12345"
        )
        assert "NOTIF-123-" in notif_res["id"]
        assert "Compra confirmada" in notif_res["title"]
        print(f"Notificación despachada: {notif_res['title']}")
        print(f"Mensaje: {notif_res['message']}")
        print(">> Prueba 3 PASÓ exitosamente.")

        # 4. STRIPE PAYMENT REJECTION (402) - NO INVENTORY DEBITED
        print("\n--- PRUEBA 4: Rechazo de Pago por Pasarela Stripe (Simulate Rejection) ---")
        # Ensure item in cart for user 1
        cart = get_or_create_cart(db, user_id=1)
        # Clear items in cart first using ORM
        cart.items.clear()
        db.commit()

        # Add 1 unit of stock_id 1
        add_to_cart(db, user_id=1, data=CartItemRequest(stock_id=1, quantity=1))

        stock_before = db.query(Stock).filter(Stock.id == 1).first().physical_stock

        req_rejected = CheckoutRequest(
            branch_id=1,
            payment_provider="stripe",
            card_token="pm_card_declined",
            simulate_rejection=True,
            idempotency_key="test-rej-001"
        )

        rejected_threw = False
        try:
            checkout(db, user_id=1, data=req_rejected)
        except HTTPException as e:
            rejected_threw = True
            print(f"HTTPException esperada recibida: {e.status_code} - {e.detail}")
            assert e.status_code == 402, f"Código inesperado: {e.status_code}"

        assert rejected_threw, "El checkout debió lanzar HTTPException 402 en rechazo"

        # Check stock was NOT decremented
        db.expire_all()
        stock_after = db.query(Stock).filter(Stock.id == 1).first().physical_stock
        assert stock_after == stock_before, f"El stock cambió de {stock_before} a {stock_after} a pesar del rechazo!"
        print(f"Integridad de stock verificada: {stock_after} unidades (sin cambios tras rechazo).")

        # Check cart still has items
        active_cart = get_or_create_cart(db, user_id=1)
        assert len(active_cart.items) == 1, "El carrito no debió vaciarse tras un rechazo!"
        print(f"Integridad del carrito verificada: {len(active_cart.items)} artículo(s) retenido(s).")
        print(">> Prueba 4 PASÓ exitosamente.")

        # 5. STRIPE PAYMENT APPROVAL - INVENTORY DEBITED & SIMULATED INVOICE ISSUED
        print("\n--- PRUEBA 5: Aprobación de Pago Stripe y Factura Fiscal Simulada ---")
        req_approved = CheckoutRequest(
            branch_id=1,
            payment_provider="stripe",
            card_token="pm_card_visa",
            simulate_rejection=False,
            idempotency_key="test-appr-001"
        )
        sale_approved = checkout(db, user_id=1, data=req_approved)
        print(f"Venta aprobada ID: {sale_approved.id} | Ref: {sale_approved.payments[0].reference}")
        payment_status = sale_approved.payments[0].status
        print(f"Estado de pago: {payment_status}")
        assert payment_status == "completado"

        # Check stock was decremented by 1
        db.expire_all()
        stock_final = db.query(Stock).filter(Stock.id == 1).first().physical_stock
        assert stock_final == stock_before - 1, f"El stock debió bajar de {stock_before} a {stock_before - 1}, pero es {stock_final}"
        print(f"Stock debitado correctamente: {stock_before} -> {stock_final}.")

        # Check cart is completed/empty
        new_cart = get_or_create_cart(db, user_id=1)
        assert len(new_cart.items) == 0
        print("Carrito activo limpiado correctamente para nueva compra.")

        # Emit simulated fiscal invoice (FAC-...)
        from app.providers.business import get_fiscal_provider
        fiscal_prov = get_fiscal_provider()
        invoice_doc = fiscal_prov.issue_invoice(sale=sale_approved)
        assert invoice_doc["provider"] == "simulated"
        assert invoice_doc["invoice_number"].startswith("FAC-")
        print(f"Factura fiscal simulada emitida: {invoice_doc['invoice_number']} | IVA: ${invoice_doc['tax']} | Total: ${invoice_doc['total']}")
        print(f"Descargo fiscal: {invoice_doc['disclaimer']}")
        print(">> Prueba 5 PASÓ exitosamente.")

        print("\n" + "=" * 60)
        print("TODAS LAS PRUEBAS (1 AL 5) PASARON EXITOSAMENTE AL 100%")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
