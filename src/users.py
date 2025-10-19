import bcrypt


def hash_password(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


USERS = {
    "alice": {"password": hash_password("password123"), "role": "admin"},
    "bob":   {"password": hash_password("securepass"), "role": "user"},
    "carol": {"password": hash_password("qwerty"), "role": "user"}
}
