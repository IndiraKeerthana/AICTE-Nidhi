def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "capabilities" in data
    assert data["capabilities"]["pymupdf_available"] is True

def test_benchmark_endpoint(client):
    response = client.get("/api/evaluation/benchmark")
    assert response.status_code == 200
    data = response.json()
    assert "defect_detection_metrics" in data or data.get("status") == "NOT_EVALUATED"
