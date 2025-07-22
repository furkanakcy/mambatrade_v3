from cryptography.fernet import Fernet
import os

# Define the path for the secret key file
KEY_PATH = "secret.key"

def generate_key():
    """Generates a key and saves it into a file."""
    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as key_file:
        key_file.write(key)

def load_key():
    """Loads the key from the current directory."""
    if not os.path.exists(KEY_PATH):
        generate_key()
    return open(KEY_PATH, "rb").read()

# Load the key and create a Fernet instance
key = load_key()
cipher_suite = Fernet(key)

def encrypt_message(message: str) -> bytes:
    """Encrypts a message."""
    return cipher_suite.encrypt(message.encode())

def decrypt_message(encrypted_message: bytes) -> str:
    """Decrypts a message."""
    return cipher_suite.decrypt(encrypted_message).decode()

if __name__ == '__main__':
    # Generate the key if the script is run directly
    print("Generating a new secret key...")
    generate_key()
    print(f"Secret key saved to {KEY_PATH}. Make sure to add this file to your .gitignore!")

    # Example usage
    original_message = "This is a super secret API key"
    encrypted = encrypt_message(original_message)
    decrypted = decrypt_message(encrypted)

    print(f"\nOriginal: {original_message}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    assert original_message == decrypted