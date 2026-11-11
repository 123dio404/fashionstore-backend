"""Punto 7 · RNF11 / RF25: gating del plan SaaS para reportes con IA.

Demuestra que el backend aplica el límite comercial del plan:
  * Básico (Bs. 29.99, sin IA) -> 403.
  * Empresarial (Bs. 129.99, con IA) -> 200.
"""

from __future__ import annotations


def test_basic_plan_cannot_access_ai_reports(client, seed):
    response = client.get(
        "/api/v1/ai-reports/top-products",
        headers=seed.token(seed.admin_a),
    )

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert "Plan Básico" in detail
    assert "no incluye" in detail
    assert "Empresarial" in detail


def test_enterprise_plan_can_access_ai_reports(client, seed):
    response = client.get(
        "/api/v1/ai-reports/top-products",
        headers=seed.token(seed.admin_b),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tipo_reporte"] == "top_productos"
    assert isinstance(body["filas"], list)


def test_ai_reports_require_authentication(client):
    response = client.get("/api/v1/ai-reports/top-products")
    assert response.status_code == 401
