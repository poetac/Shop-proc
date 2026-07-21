#!/usr/bin/env python3
"""Generate a bcrypt hash for APP_PASSWORD_HASH.

Usage:
    python scripts/hash_password.py            # prompts for the password
    python scripts/hash_password.py 'secret'   # hash given argument
"""

import getpass
import sys

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
    print(pwd_context.hash(password))


if __name__ == "__main__":
    main()
