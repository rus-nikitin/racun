import contextvars

# Контекстная переменная для хранения UUID текущего запроса
request_id_var = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str:
    """
    Получить текущий UUID запроса из контекста.
    """
    return request_id_var.get()
