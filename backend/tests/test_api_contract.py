from app.main import app


def test_openapi_exposes_versioned_core_contract() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/sources/upload" in paths
    assert "/api/v1/reports/{report_id}/versions/{version_id}/diff" in paths
    assert "/api/v1/executions/{execution_id}" in paths
