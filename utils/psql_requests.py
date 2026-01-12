def get_password_by_username(username: str) -> str:
    return \
        f"""
        SELECT password
        FROM users_list
        WHERE username = '{username}'
        """


def add_user_to_table(username: str, password: str) -> str:
    return \
        f"""
        INSERT INTO users_list(username, password)
        VALUES('{username}', '{password}');
        """
