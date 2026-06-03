import pytest
from unittest.mock import MagicMock

# make_tiny was removed from main.py when the sequential loop was deleted
# (Plan 04-05: main.py delegates to core.orchestrator.async_main). The
# orchestrator logs the full URL directly; no URL-shortening is performed.
# This file is retained as a placeholder for future utils tests.
