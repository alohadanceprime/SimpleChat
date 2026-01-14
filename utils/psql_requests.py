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


def get_server_list() -> str:
    return \
        f"""
        SELECT servername
        FROM servers_list
        """


def get_host_port(servername: str) -> str:
    return \
        f"""
        SELECT host, port
        FROM servers_list
        WHERE servername = '{servername}'
        """


def check_if_server_exists(servername: str) -> str:
    return \
        f"""
        SELECT servername
        FROM servers_list
        WHERE servername = '{servername}'
        """


def add_server_to_table(servername: str, host: str, port: int)-> str:
    return \
        f"""
        INSERT INTO servers_list(servername, host, port)
        VALUES('{servername}', '{host}', {port});
        """
