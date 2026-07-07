"""Minimal token validation for Phase 0."""

# Static demo tokens; use a proper secret store for production auth.
_VALID_TOKENS: dict[str, str] = {
    "node-01": "node-01-secret",
    "node-02": "node-02-secret",
    "node-03": "node-03-secret",
}


def get_token(node_id: str) -> str | None:
    """Return the valid token for *node_id*, or None if unknown."""
    return _VALID_TOKENS.get(node_id)


def validate_token(node_id: str, token: str) -> bool:
    """Return True iff *node_id* has *token* as its valid secret."""
    return get_token(node_id) == token
