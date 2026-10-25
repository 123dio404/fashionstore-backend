import io
import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def login(username, password):
    resp = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {username}: {resp.status_code} - {resp.text}")
    return resp.json()["access_token"]


def run_tests():
    print("=" * 70)
    print(" INICIANDO VERIFICACIÓN DE MACHINE LEARNING Y REPORTES IA (PARCIAL 2)")
    print("=" * 70)

    # Tokens para Tenant 1 (Plan Básico) y Tenant 2 (Plan Profesional)
    token_t1 = login("admin@urbanstyle.com", "admin123")
    headers_t1 = {"Authorization": f"Bearer {token_t1}"}

    token_t2 = login("admin@elegance.com", "admin123")
    headers_t2 = {"Authorization": f"Bearer {token_t2}"}

    # ─────────────────────────────────────────────────────────────────
    # 1. VERIFICACIÓN DEL MÓDULO DE MACHINE LEARNING (PAQ-06)
    # ─────────────────────────────────────────────────────────────────
    print("\n--- PRUEBA 1: Estado y Métricas de Modelos ML (RF20, RF21) ---")
    resp = client.get("/api/v1/ml/status", headers=headers_t1)
    assert resp.status_code == 200, f"Error ML status: {resp.text}"
    status = resp.json()
    assert status["supervised_demand_model"]["trained"] is True
    assert status["unsupervised_clustering_model"]["trained"] is True
    r2 = status["supervised_demand_model"]["metrics"]["r2_score"]
    sil = status["unsupervised_clustering_model"]["metrics"]["silhouette_score"]
    print(f">> Modelo Supervisado: {status['supervised_demand_model']['algorithm']} | R2: {r2}")
    print(f">> Modelo No Supervisado: {status['unsupervised_clustering_model']['algorithm']} | Silhouette: {sil}")
    print(">> Prueba 1 PASÓ: Modelos ML cargados con métricas de desempeño válidas.")

    print("\n--- PRUEBA 2: Predicción de Demanda Textil y Riesgo de Stock (RF20) ---")
    resp = client.post(
        "/api/v1/ml/predict-demand",
        headers=headers_t2,
        json={"days": 7},
    )
    assert resp.status_code == 200, f"Error predict demand: {resp.text}"
    pred_data = resp.json()
    assert "proyecciones" in pred_data
    assert len(pred_data["proyecciones"]) > 0
    sample_proj = pred_data["proyecciones"][0]
    print(f">> Proyección para sucursal '{sample_proj['sucursal_nombre']}' en categoría '{sample_proj['categoria_nombre']}':")
    print(f"   Demanda total 7 días: {sample_proj['demanda_total_proyectada']} u. | Stock actual: {sample_proj['stock_disponible_actual']}")
    print(f"   Alerta desabastecimiento: {sample_proj['alerta_desabastecimiento']}")
    print(">> Prueba 2 PASÓ: Inferencia de demanda textil y alertas calculadas correctamente.")

    print("\n--- PRUEBA 3: Segmentación RFM con K-Means (RF21) ---")
    resp = client.get("/api/v1/ml/customer-segments", headers=headers_t2)
    assert resp.status_code == 200, f"Error customer segments: {resp.text}"
    seg_data = resp.json()
    assert "segment_distribution" in seg_data
    assert len(seg_data["segment_distribution"]) == 4
    for seg in seg_data["segment_distribution"]:
        print(f"   Segmento [{seg['nombre']}]: {seg['total_clientes']} clientes ({seg['porcentaje']}%) | Estrategia: {seg['estrategia_recomendada'][:50]}...")
    print(">> Prueba 3 PASÓ: Segmentación K-Means RFM en 4 clusters validada.")

    print("\n--- PRUEBA 4: Bundle para Dashboard Analítico (RF22) ---")
    resp = client.get("/api/v1/ml/dashboard", headers=headers_t2)
    assert resp.status_code == 200, f"Error ML dashboard: {resp.text}"
    dash_data = resp.json()
    assert "top_demand_categories" in dash_data
    assert "segmentacion_clientes" in dash_data
    print(f">> Top categorías con mayor demanda esperada: {[c['categoria'] for c in dash_data['top_demand_categories'][:3]]}")
    print(">> Prueba 4 PASÓ: Dashboard analítico alimentado con KPIs de ML.")

    # ─────────────────────────────────────────────────────────────────
    # 2. VERIFICACIÓN DE REPORTE CON IA Y LENGUAJE NATURAL (PAQ-07)
    # ─────────────────────────────────────────────────────────────────
    print("\n--- PRUEBA 5: Restricción de IA por Plan Básico vs Profesional (RF28 / RN-02) ---")
    # Tenant 1 (Plan Básico) debe recibir 403 Forbidden
    resp_t1 = client.post(
        "/api/v1/ai-reports/query",
        headers=headers_t1,
        json={"query": "Mostrar las prendas más vendidas del mes"},
    )
    assert resp_t1.status_code == 403, f"Esperaba 403 para Plan Básico pero obtuve {resp_t1.status_code}"
    print(f">> Bloqueo exitoso para Plan Básico: '{resp_t1.json()['detail']}'")

    # Tenant 2 (Plan Profesional) debe tener acceso habilitado
    resp_t2 = client.post(
        "/api/v1/ai-reports/query",
        headers=headers_t2,
        json={"query": "Cuáles son los productos más vendidos en nuestras tiendas?"},
    )
    assert resp_t2.status_code == 200, f"Error AI report para Plan Profesional: {resp_t2.text}"
    ai_result = resp_t2.json()
    print(f">> Acceso concedido para Plan Profesional:")
    print(f"   Título: {ai_result['titulo']}")
    print(f"   Tipo Gráfico: {ai_result['tipo_grafico']}")
    print(f"   Columnas: {ai_result['columnas']}")
    print(f"   Resumen IA: {ai_result['resumen_ejecutivo'][:120]}...")
    print(">> Prueba 5 PASÓ: Regla de restricción por plan y generación con IA comprobada.")

    print("\n--- PRUEBA 6: 4 Tipos de Reportes Reales Demostrables (RF25) ---")
    r1 = client.get("/api/v1/ai-reports/sales-by-branch", headers=headers_t2)
    assert r1.status_code == 200
    print(f">> Reporte 1 (Ventas por Sucursal): {r1.json()['titulo']} | Filas: {len(r1.json()['filas'])}")

    r2 = client.get("/api/v1/ai-reports/top-products", headers=headers_t2)
    assert r2.status_code == 200
    print(f">> Reporte 2 (Top Productos): {r2.json()['titulo']} | Filas: {len(r2.json()['filas'])}")

    r3 = client.get("/api/v1/ai-reports/quarterly-comparison", headers=headers_t2)
    assert r3.status_code == 200
    print(f">> Reporte 3 (Comparativa Trimestral): {r3.json()['titulo']} | Filas: {len(r3.json()['filas'])}")

    r4 = client.get("/api/v1/ai-reports/low-stock-risk", headers=headers_t2)
    assert r4.status_code == 200
    print(f">> Reporte 4 (Riesgo de Agotamiento): {r4.json()['titulo']} | Filas: {len(r4.json()['filas'])}")
    print(">> Prueba 6 PASÓ: Los 4 reportes reales de base de datos operativos.")

    print("\n--- PRUEBA 7: Exportación a Formatos PDF y Excel (RF27) ---")
    # Export PDF
    pdf_resp = client.post(
        "/api/v1/ai-reports/export/pdf",
        headers=headers_t2,
        json={"report_data": ai_result},
    )
    assert pdf_resp.status_code == 200, f"Error export PDF: {pdf_resp.text}"
    assert pdf_resp.content.startswith(b"%PDF"), "El archivo no inicia con cabecera %PDF"
    print(f">> Archivo PDF generado exitosamente: {len(pdf_resp.content)} bytes.")

    # Export Excel
    xlsx_resp = client.post(
        "/api/v1/ai-reports/export/excel",
        headers=headers_t2,
        json={"report_data": ai_result},
    )
    assert xlsx_resp.status_code == 200, f"Error export Excel: {xlsx_resp.text}"
    assert len(xlsx_resp.content) > 1000, "El archivo Excel generado está vacío o corrupto"
    print(f">> Archivo Excel generado exitosamente: {len(xlsx_resp.content)} bytes.")
    print(">> Prueba 7 PASÓ: Exportadores PDF y Excel funcionando.")

    print("\n" + "=" * 70)
    print(" ¡TODAS LAS PRUEBAS DE MACHINE LEARNING Y REPORTES IA PASARON AL 100%!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
