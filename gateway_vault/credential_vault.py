"""AES-256-GCM credential store, with master key supplied outside the database.

This is a local credential vault, not a threshold signer or a trading executor.
"""
import os
from pathlib import Path
import sqlite3

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialVault:
    def __init__(self, db_path, master_key):
        if not isinstance(master_key, bytes) or len(master_key) != 32:
            raise ValueError("A 32-byte external master key is required")
        self.cipher = AESGCM(master_key)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS credentials (name TEXT PRIMARY KEY, nonce BLOB, ciphertext BLOB)")
        self.conn.commit()
        try:
            Path(db_path).chmod(0o600)
        except OSError:
            pass

    def put(self, name, value):
        if not isinstance(name, str) or not name or not isinstance(value, str) or not value:
            raise ValueError("Name and secret must be nonempty strings")
        nonce = os.urandom(12)
        encrypted = self.cipher.encrypt(nonce, value.encode(), name.encode())
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO credentials VALUES (?,?,?)", (name, nonce, encrypted))

    def get(self, name):
        row = self.conn.execute("SELECT nonce,ciphertext FROM credentials WHERE name=?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return self.cipher.decrypt(row[0], row[1], name.encode()).decode()

    def names(self):
        return [row[0] for row in self.conn.execute("SELECT name FROM credentials ORDER BY name")]

    def delete(self, name):
        with self.conn:
            self.conn.execute("DELETE FROM credentials WHERE name=?", (name,))
