from app.ratelimit import reset


def pytest_runtest_setup() -> None:
    reset()
