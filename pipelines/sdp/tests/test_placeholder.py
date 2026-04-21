"""Placeholder test to verify pytest runs."""


def test_package_imports():
    """Verify the agl_analytics package can be imported."""
    import agl_analytics

    assert agl_analytics.__version__ == "0.1.1"
