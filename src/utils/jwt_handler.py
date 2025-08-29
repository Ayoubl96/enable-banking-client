import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from config import settings

class JWTHandler:
    def __init__(self, algorithm: str = 'RS256'):
        private_key_path = settings.enable_banking_private_key_path
        with open(private_key_path, 'r') as f:
            self.private_key = f.read()
        self.algorithm = algorithm
    def generate_enable_baking_token(self):

        now = datetime.now(timezone.utc)

        jwt_body = {
            "iss": settings.enable_banking_iss,
            "aud": settings.enable_banking_aud,
            "iat": now,
            "exp": now + timedelta(minutes=settings.enable_banking_token_expiry_minutes),
        }

        jwt = pyjwt.encode(
            jwt_body,
            self.private_key,
            algorithm = self.algorithm,
            headers = {
                'kid': settings.enable_banking_application_id
            }
        )
        print(jwt)
        return jwt
