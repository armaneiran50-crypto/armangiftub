import anthropic

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Shared Anthropic client (reads ANTHROPIC_API_KEY from the environment)."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client
