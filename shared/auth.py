"""Static node secrets used as PSKs for demo authentication."""

# Static demo PSKs for node-01..node-32; use a proper secret store for production.
_VALID_TOKENS: dict[str, str] = {
    f"node-{index:02d}": f"node-{index:02d}-secret"
    for index in range(1, 33)
}


def get_token(node_id: str) -> str | None:
    """Return the valid token for *node_id*, or None if unknown."""
    return _VALID_TOKENS.get(node_id)


def get_pre_shared_key(node_id: str) -> str | None:
    """Return the configured pre-shared key for *node_id*."""
    return get_token(node_id)


def validate_token(node_id: str, token: str) -> bool:
    """Return True iff *node_id* has *token* as its valid secret."""
    return get_token(node_id) == token
