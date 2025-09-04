from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    #JWT parameters
    enable_banking_private_key_path: str = "Insert path to private key"
    enable_banking_application_id: str = "Insert application id"
    enable_banking_iss: str = "enablebanking.com"
    enable_banking_aud: str = "api.enablebanking.com"
    enable_banking_token_expiry_minutes: int = 60

    # API base url
    enable_banking_base_api_url: str = "https://api.enablebanking.com"

    # Service Server configuration
    api_host: str = "localhost"
    api_port: int = 8001

    env: str = "dev"

    class Config:
        env_file = ".env"

settings = Settings()
