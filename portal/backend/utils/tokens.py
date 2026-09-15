import secrets


def generate_bearer_token() -> str:
    return "tk_" + secrets.token_urlsafe(32)


def generate_claim_token() -> str:
    return "ct_" + secrets.token_urlsafe(24)
