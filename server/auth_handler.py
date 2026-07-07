import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def load_psk_config(config_path: str | None = None) -> dict[str, str]:
    """Load PSK configuration from JSON file"""
    if config_path is None:
        # Try relative path from current directory first
        if os.path.exists("configs/psk_config.json"):
            config_path = "configs/psk_config.json"
        # Try relative to this file's directory
        elif os.path.exists(os.path.join(os.path.dirname(__file__), "..", "configs", "psk_config.json")):
            config_path = os.path.join(os.path.dirname(__file__), "..", "configs", "psk_config.json")
        else:
            config_path = "configs/psk_config.json"
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("psk_config", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[warning] Could not load PSK config from {config_path}: {e}")
        return {}


def get_node_psk(node_id: str, psk_config: dict[str, str] | None = None) -> bytes | None:
    """Get PSK for a specific node from configuration"""
    if psk_config is None:
        psk_config = load_psk_config()
    
    psk_str = psk_config.get(node_id)
    if psk_str:
        # Convert hex string to bytes
        try:
            return bytes.fromhex(psk_str)
        except ValueError:
            return psk_str.encode("utf-8").ljust(32, b'\x00')[:32]
    return None


def derive_key(psk: bytes, salt: bytes) -> bytes:
    """Derive a key from PSK using PBKDF2"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(psk)


def encrypt_message(message: dict, psk: bytes) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt a message using AES-GCM with PSK
    Returns: (ciphertext, nonce, tag)
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = derive_key(psk, salt)
    cipher = AESGCM(key)
    
    plaintext = json.dumps(message, separators=(",", ":")).encode("utf-8")
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    
    return ciphertext, nonce, salt


def decrypt_message(ciphertext: bytes, nonce: bytes, salt: bytes, psk: bytes) -> dict:
    """
    Decrypt a message using AES-GCM with PSK
    Returns: decrypted message as dict
    """
    key = derive_key(psk, salt)
    cipher = AESGCM(key)
    
    plaintext = cipher.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))


def encode_encrypted_message(ciphertext: bytes, nonce: bytes, salt: bytes) -> str:
    """Encode encrypted data as a single line message"""
    import base64
    message = {
        "type": "auth_challenge",
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "salt": base64.b64encode(salt).decode("utf-8"),
    }
    return json.dumps(message, separators=(",", ":"))


def decode_encrypted_message(line: str) -> tuple[bytes, bytes, bytes]:
    """Decode encrypted data from a line message"""
    import base64
    message = json.loads(line)
    return (
        base64.b64decode(message["ciphertext"]),
        base64.b64decode(message["nonce"]),
        base64.b64decode(message["salt"]),
    )
