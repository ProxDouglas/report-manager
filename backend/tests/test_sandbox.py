import pytest

from app.core.errors import DomainError
from app.services.sandbox import PythonPolicyValidator


def test_restricted_python_policy_rejects_system_access() -> None:
    validator = PythonPolicyValidator()
    validator.validate("result = 1")
    with pytest.raises(DomainError):
        validator.validate("import os\nresult = os.listdir('/')")
