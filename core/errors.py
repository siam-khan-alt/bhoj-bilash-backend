"""Every error looks like `{ "message": "..." }` — frontend reads only this shape."""

from rest_framework.views import exception_handler


def _first_message(data, default: str) -> str:
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail
        for value in data.values():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
    elif isinstance(data, list) and data:
        return str(data[0])
    elif isinstance(data, str):
        return data
    return default


def bhojbilash_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        default = getattr(exc, "default_detail", "Request failed.")
        response.data = {"message": _first_message(response.data, str(default))}
    return response
