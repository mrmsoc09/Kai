import os

os.environ.setdefault("K1_TEST_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("K1_DEV_TOKEN", "devtoken")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
