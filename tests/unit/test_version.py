from importlib.metadata import PackageNotFoundError, version

import simcord


def test_version_matches_package_metadata():
    """`simcord.__version__` is sourced from package metadata, so it can never
    drift from the version declared in pyproject.toml. Without dist metadata
    (a bare source checkout) it falls back to a sentinel instead of raising."""
    try:
        assert simcord.__version__ == version("simcord")
    except PackageNotFoundError:
        assert simcord.__version__ == "0.0.0+unknown"
