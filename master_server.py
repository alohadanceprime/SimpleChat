from server import *
from utils import *
from multiprocessing import Process
from typing import Any, Optional



class MasterServer:
    def __init__(self, host: str, port: int,
                 psql_host: str ="localhost", psql_port: int = 5432,
                 psql_user: str = "postgres", psql_password: str ="admin",
                 psql_db: str = "userdata"):
        self._addr: tuple[str, int] = host, port
        self.__server: socket.socket = socket.socket()
        self.__server.bind(self._addr)
        self.__server.setblocking(False)

        self.__psql_params: dict[str, Any] = {
            "host": psql_host,
            "port": psql_port,
            "user": psql_user,
            "password": psql_password,
            "database": psql_db,
            "min_size": 8,
            "max_size": 16
        }
        self.__psql_pool: Optional[asyncpg.Pool] = None

        self.__commands: dict[str, Callable] = {}
        for obj in dir(self):
            if callable(getattr(self, obj)) and hasattr(getattr(self, obj), "command_name"):
                self.__commands[getattr(self, obj).command_name] = getattr(self, obj)

        self.__running_servers: dict[str, tuple[tuple[str, int], Process]] = {}

        self.__tasks: Optional[asyncio.Task]  = None


    @command("/help")
    async def __help(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(connection, ("Список доступных команд:\n" +
                                             ("\n".join(i for i in self.__commands.keys()))).encode("utf-8"))


    @command("/server_list")
    async def __get_server_list(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        async with self.__psql_pool.acquire() as psql_connection:
            server_list = (await psql_connection.fetch(get_server_list()))
        if server_list:
            server_list = [i["servername"] for i in server_list]
        await loop.sock_sendall(connection, ("Список серверов:\n" + "\n".join(server_list)).encode("utf-8"))


    @command("/connect")
    async def __connect(self, connection: socket.socket, servername: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(connection, "connection_approved".encode("utf-8"))
        response = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        if response != "ready_for_connection":
            return
        async with self.__psql_pool.acquire() as psql_connection:
            sql_resp = await psql_connection.fetchrow(get_host_port(servername))
        if sql_resp is None:
            await loop.sock_sendall(connection, "server_is_not_exist".encode("utf-8"))
            return
        host, port = sql_resp["host"], sql_resp["port"]
        if host == "localhost":
            host = "127.0.0.1"

        if servername not in self.__running_servers:
            self.__run_server(servername, host, port)
        await loop.sock_sendall(connection, (host + " " + str(port)).encode("utf-8"))
        connection.close()
        if self.__tasks:
            self.__tasks.cancel()


    @command("/start_server")
    async def __start_server(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(connection, "Придумайте имя сервера".encode("utf-8"))
        servername = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        async with self.__psql_pool.acquire()  as psql_connection:
            is_exists = (await psql_connection.fetchrow(check_if_server_exists(servername))) is not None
        while is_exists:
            await loop.sock_sendall(connection, "Сервер с заданным именем уже существует,\n"
                                                "попробуйте ввести другое имя:".encode("utf-8"))
            servername = (await loop.sock_recv(connection, 1024)).decode("utf-8")
            async with self.__psql_pool.acquire() as psql_connection:
                is_exists = (await psql_connection.fetchrow(check_if_server_exists(servername))) is not None

        while True:
            try:
                await loop.sock_sendall(connection, "Придумайте хост сервера".encode("utf-8"))
                host = (await loop.sock_recv(connection, 1024)).decode("utf-8")
                await loop.sock_sendall(connection, "Придумайте порт сервера".encode("utf-8"))
                port = int((await loop.sock_recv(connection, 1024)).decode("utf-8"))
                if not check_host_port_validity(host, port):
                    raise "Invalid host/port"
                async with self.__psql_pool.acquire()  as psql_connection:
                    await psql_connection.execute(add_server_to_table(servername, host, port))
                break
            except Exception:
                await loop.sock_sendall(connection, "Данные хост + порт уже заняты/ они не корректны".encode("utf-8"))

        await loop.sock_sendall(connection, "Сервер успешно создан".encode("utf-8"))
        self.__run_server(servername, host, port)


    def __run_server(self, servername: str, host: str, port: int) -> None:
        p = Process(target=create_server, args=(host, port), daemon=True)
        p.start()
        self.__running_servers[servername] = ((host, port), p)
        print(f"Сервер {servername} запущен на {host}:{port}, PID={p.pid}")


    async def __create_pool(self) -> None:
        self.__psql_pool = await asyncpg.create_pool(**self.__psql_params)


    async def __receive(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        try:
            while True:
                if connection.fileno() < 0:
                    break
                await loop.sock_sendall(connection, "Для получения списка команд напишите /help".encode("utf-8"))
                message = await loop.sock_recv(connection, 1024)
                if not message:
                    connection.close()
                    break
                message = message.decode("utf-8")
                cmd = message.split(" ")[0]
                args = message.split(" ")[1:]
                if cmd not in self.__commands:
                    await loop.sock_sendall(connection, "Данная команда не существует".encode("utf-8"))
                    continue
                if args:
                    await self.__commands[cmd](connection, *args)
                else:
                    await self.__commands[cmd](connection)
                if connection.fileno() < 0:
                    break
        except Exception as e:
            print(f"Произошла ошибка {e} с пользователем {connection}")
            connection.close()


    async def __connect_user(self, connection: socket.socket) -> None:
        connection.setblocking(False)
        await self.__receive(connection)


    async def run_master_server(self) -> None:
        self.__server.listen()
        await self.__create_pool()

        while True:
            loop = asyncio.get_event_loop()
            connection, client_address = await loop.sock_accept(self.__server)
            self.__tasks = asyncio.create_task(self.__connect_user(connection))



if __name__ == "__main__":
    master = MasterServer("127.0.0.1", 8000, psql_host="localhost", psql_port=5432,
                          psql_user="postgres", psql_password="admin", psql_db="userdata")
    asyncio.run(master.run_master_server())
