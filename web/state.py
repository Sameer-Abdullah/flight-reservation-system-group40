from flask import session

BOOKING_SESSION_KEY = "booking_context"


def get_booking_context() -> dict:

    return session.get(BOOKING_SESSION_KEY) or {}


def update_booking_context(data: dict) -> dict:
    """
    This keeps all pages (search → seats → booking → payment) in sync.
    """
    ctx = get_booking_context()
    ctx.update(data or {})
    session[BOOKING_SESSION_KEY] = ctx
    session.modified = True
    return ctx


def clear_booking_context():
    session.pop(BOOKING_SESSION_KEY, None)
