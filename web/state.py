
_booking_context = {
    "selected_customer": None,
    "selected_flight": None,
    "passengers": [],
    "filters": {},
}

def get_booking_context():
    return _booking_context

def update_booking_context(data: dict):
    """Update booking context with a dict."""
    _booking_context.update(data)
    return _booking_context
