"""112233.es API."""

from .core.public_http import install_public_http_guard

install_public_http_guard()

# Habitaclia is currently a production canary source.  Installing it here keeps
# the existing configured-source health contract unchanged while letting the
# external-listings worker collect real production evidence for the adapter.
from .habitaclia_source import install_habitaclia_source

install_habitaclia_source()
