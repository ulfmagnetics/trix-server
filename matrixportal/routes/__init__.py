# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""HTTP route handlers for MatrixPortal server."""

from . import display
from . import fetch
from . import clear
from . import crash


def register_all(server, context):
    """Register all HTTP route handlers with the server.

    Args:
        server: adafruit_httpserver.Server instance
        context: AppContext with shared resources
    """
    display.register(server, context)
    fetch.register(server, context)
    clear.register(server, context)
    crash.register(server, context)
