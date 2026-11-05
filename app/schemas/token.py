from pydantic import BaseModel


class Token(BaseModel):
    """Schema for JWT tokens returned upon login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Payload decoded from JWT token."""

    sub: str
    type: str
    exp: int


class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing an access token."""

    refresh_token: str
