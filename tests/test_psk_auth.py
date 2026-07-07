#!/usr/bin/env python3
"""
Test script for PSK authentication handshake
"""

import sys
sys.path.insert(0, '/home/maxi/codigo/sistema-monitoreo-remoto-servidores-simulados')

from server.auth_handler import (
    encrypt_message,
    decrypt_message,
    encode_encrypted_message,
    decode_encrypted_message,
    load_psk_config,
    get_node_psk,
)


def test_psk_encryption_decryption():
    """Test basic PSK encryption and decryption"""
    print("[test] Testing PSK encryption/decryption...")
    
    # Load PSK for node-01
    psk_config = load_psk_config()
    psk = get_node_psk("node-01", psk_config)
    
    assert psk is not None, "Failed to load PSK for node-01"
    assert len(psk) == 32, f"PSK should be 32 bytes, got {len(psk)}"
    
    # Test encryption/decryption
    original_message = {"type": "auth_challenge_response", "message": "Please authenticate"}
    ciphertext, nonce, salt = encrypt_message(original_message, psk)
    
    decrypted_message = decrypt_message(ciphertext, nonce, salt, psk)
    
    assert decrypted_message == original_message, "Decrypted message doesn't match original"
    print("[test] ✓ Encryption/decryption works correctly")


def test_encoded_message_format():
    """Test encoded message format"""
    print("[test] Testing encoded message format...")
    
    psk_config = load_psk_config()
    psk = get_node_psk("node-01", psk_config)
    
    message = {"type": "auth_response", "acknowledged": True}
    ciphertext, nonce, salt = encrypt_message(message, psk)
    
    # Encode
    encoded_line = encode_encrypted_message(ciphertext, nonce, salt)
    print(f"[test] Encoded message length: {len(encoded_line)} chars")
    
    # Decode
    decoded_ciphertext, decoded_nonce, decoded_salt = decode_encrypted_message(encoded_line)
    
    assert decoded_ciphertext == ciphertext, "Ciphertext mismatch"
    assert decoded_nonce == nonce, "Nonce mismatch"
    assert decoded_salt == salt, "Salt mismatch"
    
    # Verify we can decrypt
    decrypted_message = decrypt_message(decoded_ciphertext, decoded_nonce, decoded_salt, psk)
    assert decrypted_message == message, "Decrypted message doesn't match"
    
    print("[test] ✓ Encoded message format works correctly")


def test_multiple_psk_nodes():
    """Test PSK loading for multiple nodes"""
    print("[test] Testing multiple node PSKs...")
    
    psk_config = load_psk_config()
    
    for node_id in ["node-01", "node-02", "node-03"]:
        psk = get_node_psk(node_id, psk_config)
        assert psk is not None, f"Failed to load PSK for {node_id}"
        assert len(psk) == 32, f"PSK for {node_id} should be 32 bytes"
        print(f"[test] ✓ PSK loaded for {node_id}")


def main():
    print("=" * 50)
    print("PSK Authentication Tests")
    print("=" * 50)
    
    try:
        test_psk_encryption_decryption()
        test_encoded_message_format()
        test_multiple_psk_nodes()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
