"""Immutable offline completion vocabulary, independent of LIVE approval/files."""
FIXTURES = {
    "Обязательно с балконом.": {"balcony": {"strength": "hard", "value": True}},
    "Como máximo 600 euros al mes.": {"budget": {"strength": "hard", "value": {
        "amount": "600", "currency": "EUR", "period": "monthly"}}},
    "The apartment must be unfurnished.": {"furnished": {"strength": "hard", "value": False}},
}
