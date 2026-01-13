import json


banned_symbols: set[str] = {' ', '\t', '\n', '\r', '"', "'", '`', '<',
                     '>', '|', '\\', '/', ':', ';', '*', '?',
                     '[', ']', '{','}', '(', ')', '&', '%', '$',
                     '#', '@', '!', '~', '=', '+', ',', '.'}


with open("dictionaries/banned_words.json", "r") as file:
    data = json.load(file)
    banned_words: tuple[str] = tuple(data["banned_words"])


def check_password_validity(password: str) -> bool:
    if len(password) < 6 or len(password) > 64:
        return False

    for char in password:
        if char in banned_symbols:
            return False

    return True


def check_username_validity(username: str) -> bool:
    if len(username) < 6 or len(username) > 64:
        return False

    for char in username:
        if char in banned_symbols:
            return False

    for word in banned_words:
        if word in username.lower():
            return False

    return True


