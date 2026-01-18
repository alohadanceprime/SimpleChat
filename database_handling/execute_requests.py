from asyncpg import Pool
from typing import Optional
from database_handling.psql_requests import *



async def add_user(pool: Pool, username: str, password:str) -> None:
    async with pool.acquire() as psql_connection:
        await psql_connection.execute(add_user_to_table_req(username, password))


async def get_password_by_username(pool: Pool, username: str) -> Optional[str]:
    async with pool.acquire() as psql_connection:
        return await psql_connection.fetchval(get_password_by_username_req(username))


async def get_server_list(pool: Pool) -> list[str]:
    async with pool.acquire() as psql_connection:
        server_list = (await psql_connection.fetch(get_server_list_req))
    if server_list:
        server_list = [i["servername"] for i in server_list]
    else:
        server_list = ["Нет доступных серверов"]
    return server_list


async def get_host_port(pool: Pool, servername: str) -> Optional[tuple[str, int]]:
    async with pool.acquire() as psql_connection:
        resp = await psql_connection.fetchrow(get_host_port_req(servername))
    if resp:
        host, port = resp["host"], resp["port"]
        if host == "localhost":
            host = "127.0.0.1"
        return host, port
    return None


async def check_if_server_exists(pool: Pool, servername: str) -> bool:
    async with pool.acquire() as psql_connection:
        return (await psql_connection.fetchrow(check_if_server_exists_req(servername))) is not None


async def add_server_to_table(pool: Pool, servername: str, host: str, port: int) -> None:
    async with pool.acquire() as psql_connection:
        await psql_connection.execute(add_server_to_table_req(servername, host, port))
