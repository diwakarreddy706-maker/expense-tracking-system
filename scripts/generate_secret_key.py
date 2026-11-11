#!/usr/bin/env python
"""
Generates a cryptographically strong 64-character secret key for production Django deployments.
Usage:
    python scripts/generate_secret_key.py
    python scripts/generate_secret_key.py --write-env
"""

import sys
import secrets
from pathlib import Path


def generate_key():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(chars) for _ in range(64))


def main():
    new_key = generate_key()
    print("=" * 70)
    print("AgriBOS ERP - Production Django Secret Key Generator")
    print("=" * 70)
    print(f"Generated Key (64 characters):\n{new_key}\n")
    print("Add this to your production environment or .env file as:")
    print(f"SECRET_KEY={new_key}")
    print("=" * 70)

    if '--write-env' in sys.argv:
        env_path = Path(__file__).resolve().parent.parent / '.env'
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('SECRET_KEY='):
                    lines[i] = f"SECRET_KEY={new_key}"
                    updated = True
                    break
            if not updated:
                lines.append(f"SECRET_KEY={new_key}")
            env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            print(f"[SUCCESS] Updated SECRET_KEY in {env_path}")
        else:
            print(f"[WARNING] {env_path} not found.")


if __name__ == '__main__':
    main()
