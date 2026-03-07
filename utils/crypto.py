from cryptography.fernet import Fernet
from typing import Optional
from config import Config

class CryptoManager:
    def __init__(self):
        if not Config.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY not set in .env")
        # Fernet expects the base64-encoded key directly (it decodes internally)
        self.cipher_suite = Fernet(Config.ENCRYPTION_KEY.encode())

    def encrypt(self, data: str) -> str:
        """Encrypt JSON string of tokens"""
        encrypted = self.cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt(self, encrypted_data: str) -> Optional[str]:
        """Decrypt to JSON string of tokens"""
        try:
            decrypted = self.cipher_suite.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception:
            return None