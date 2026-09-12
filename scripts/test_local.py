"""Run isolated tests with non-production settings, without a developer .env."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key, value in {
    "POSTGRES_DB": "test", "POSTGRES_USER": "test", "POSTGRES_PASSWORD": "test",
    "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "1", "DEBUG": "false",
    "LOG_LEVEL": "WARNING", "SECRET_KEY": "local-test-key-012345678901234567890",
    "R2_ENDPOINT_URL": "http://127.0.0.1:1", "R2_ACCESS_KEY_ID": "test",
    "R2_SECRET_ACCESS_KEY": "test", "R2_BUCKET_NAME": "test",
}.items():
    os.environ[key] = value

import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
