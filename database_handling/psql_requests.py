def get_password_by_username_req(username: str) -> str:
    return \
        f"""
        SELECT password
        FROM users_list
        WHERE username = '{username}'
        """


def add_user_to_table_req(username: str, password: str) -> str:
    return \
        f"""
        INSERT INTO users_list(username, password)
        VALUES('{username}', '{password}');
        """


def get_host_port_req(servername: str) -> str:
    return \
        f"""
        SELECT host, port
        FROM servers_list
        WHERE servername = '{servername}'
        """


def check_if_server_exists_req(servername: str) -> str:
    return \
        f"""
        SELECT servername
        FROM servers_list
        WHERE servername = '{servername}'
        """


def add_server_to_table_req(servername: str, host: str, port: int)-> str:
    return \
        f"""
        INSERT INTO servers_list(servername, host, port)
        VALUES('{servername}', '{host}', {port});
        """


get_server_list_req: str=\
    f"""
    SELECT servername
    FROM servers_list
    """

