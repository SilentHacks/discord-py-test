from importlib.metadata import version

import simcord


def test_version_matches_package_metadata():
    """`simcord.__version__` is sourced from package metadata, so it can never
    drift from the version declared in pyproject.toml."""
    assert simcord.__version__ == version("simcord")
