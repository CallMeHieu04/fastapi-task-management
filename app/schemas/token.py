from app.schemas.common import BaseAppModel


class Token(BaseAppModel):
    """Schema returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseAppModel):
    """Schema for requesting a refreshed token pair or revoking on logout."""

    refresh_token: str
