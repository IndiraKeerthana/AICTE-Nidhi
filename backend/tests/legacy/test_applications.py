def test_create_and_list_application(client):
    payload = {
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_programme": "ENGINEERING_AND_TECHNOLOGY",
        "declared_course": "Computer Science & Engineering",
        "declared_intake": 120,
        "declared_land_acres": 8.25
    }
    
    # 1. Create Application
    create_res = client.post("/api/applications", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["application_number"].startswith("APP-2026-")
    assert created_data["declared_intake"] == 120
    assert created_data["institution"]["aicte_permanent_id"] == "1-9988776655"
    app_id = created_data["id"]

    # 2. Get Application Details
    detail_res = client.get(f"/api/applications/{app_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == app_id
    assert detail_data["baseline_record"] is not None
    assert detail_data["baseline_record"]["approved_intake"] == 60
    assert detail_data["findings_count"] >= 1  # Should flag intake mismatch automatically!

    # 3. List Applications
    list_res = client.get("/api/applications")
    assert list_res.status_code == 200
    apps = list_res.json()
    assert any(a["id"] == app_id for a in apps)
