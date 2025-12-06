# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Authentication helper for API key validation."""

from adafruit_httpserver import Request, Response


def require_api_key(request: Request, api_key: str) -> Response | None:
    """Validate API key from request headers.

    Args:
        request: HTTP request object
        api_key: Expected API key from settings

    Returns:
        None if authentication succeeds
        Response object with 401 status if authentication fails
    """
    # Get API key from X-Trix-API-Key header
    provided_key = None
    if hasattr(request, 'headers') and request.headers:
        provided_key = request.headers.get('X-Trix-API-Key')

    # Check if header is missing
    if provided_key is None:
        print("Authentication failed: X-Trix-API-Key header missing")
        return Response(request, "Unauthorized", status=(401, "Unauthorized"))

    # Compare keys
    if provided_key != api_key:
        print("Authentication failed: Invalid API key")
        return Response(request, "Unauthorized", status=(401, "Unauthorized"))

    # Authentication successful
    return None
