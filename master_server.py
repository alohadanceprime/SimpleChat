from server import *
from utils import *
from multiprocessing import Process
from database_handling import *
from typing import Any, Optional



class MasterServer:
    def __init__(self, host: str, port: int,
                 psql_host: str ="localhost", psql_port: int = 5432,
                 psql_user: str = "postgres", psql_password: str ="admin",
                 psql_db: str = "userdata"):
        if not isinstance(host, str):
            raise TypeError("host is not a string")
        if not isinstance(port, int):
            raise TypeError("port is not an integer")
        if not 1 <= port <= 65535:
            raise ValueError("port is not in the range 1 to 65535")

        try:
            self._addr: tuple[str, int] = host, port
            self.__server: socket.socket = socket.socket()
            self.__server.bind(self._addr)
            self.__server.setblocking(False)
        except socket.error as e:
            raise RuntimeError(f"Failed to start server: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")



        self.__psql_params: dict[str, Any] = {
            "host": psql_host,
            "port": psql_port,
            "user": psql_user,
            "password": psql_password,
            "database": psql_db,
            "min_size": 8,
            "max_size": 16,
            "timeout": 30,
            "command_timeout": 30
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
        try:
            await loop.sock_sendall(connection, ("Список доступных команд:\n" +
                                             ("\n".join(i for i in self.__commands.keys()))).encode("utf-8"))
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке отослать список доступных команд пользователю {connection}")


    @command("/server_list")
    async def __get_server_list(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        try:
            server_list = await get_server_list(self.__psql_pool)
        except (asyncpg.PostgresError, ConnectionError) as e:
            print(f"Не получилось получить список серверов: {e}")
            return
        try:
            await loop.sock_sendall(connection, ("Список серверов:\n" + "\n".join(server_list)).encode("utf-8"))
        except Exception as e:
            print(f"Произошло неожиданное исключение при {e} "
                  f"при попытке отправить список серверов пользователю {connection}")



    @command("/connect")
    async def __connect(self, connection: socket.socket, servername: str) -> None:
        loop = asyncio.get_event_loop()
        if not isinstance(servername, str):
            print(f"Ожидалось что servername - строка, текущий тип: {type(servername)}")
            return
        try:
            sql_resp = await get_host_port(self.__psql_pool, servername)
        except (asyncpg.PostgresError, ConnectionError) as e:
            print(f"Произошла ошибка при поиске сервера в базе данных: {e}")
            await loop.sock_sendall(connection, "Внутренняя ошибка сервера, "
                                                "пожалуйста попробуйте позже".encode("utf-8"))
            return
        if sql_resp is None:
            await loop.sock_sendall(connection, "server_is_not_exist".encode("utf-8"))
            return
        try:
            await loop.sock_sendall(connection, "connection_approved".encode("utf-8"))
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке отослать подтверждение подключения пользователю {connection}")
            return
        response = (await loop.sock_recv(connection, 1024)).decode("utf-8").strip()
        if response != "ready_for_connection":
            print(f"Неожиданный ответ от клиента ({connection}): {response}, ожидалось: ready_for_connection")
            return
        host, port = sql_resp

        if servername not in self.__running_servers:
            try:
                self.__run_server(servername, host, port)
            except Exception as e:
                print(f"Произошла неожиданная ошибка {e} при попытке запустить сервер {servername}")
                await loop.sock_sendall(connection, "Внутренняя ошибка сервера, "
                                                    "пожалуйста попробуйте позже".encode("utf-8"))
                return
        try:
            await loop.sock_sendall(connection, (host + " " + str(port)).encode("utf-8"))
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке отослать данные для "
                  f"подключения к серверу пользователю {connection}")
            return
        connection.close()
        if self.__tasks:
            self.__tasks.cancel()


    @command("/start_server")
    async def __start_server(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        try:
            await loop.sock_sendall(connection, "Придумайте имя сервера".encode("utf-8"))
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке запустить сервер")
            return
        try:
            servername = (await loop.sock_recv(connection, 1024)).decode("utf-8").strip()
            while not check_servername_validity(servername):
                await loop.sock_sendall(connection, "Указанное имя сервера не доступно,\n"
                                                    "попробуйте указать другое имя".encode("utf-8"))
                servername = (await loop.sock_recv(connection, 1024)).decode("utf-8").strip()
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке получить имя сервера с пользователем {connection}")
            return
        try:
            is_exists = await check_if_server_exists(self.__psql_pool, servername)
        except (asyncpg.PostgresError, ConnectionError) as e:
            print(f"Произошла ошибка {e} при попытке проверить существует ли сервер с данным именем")
            return
        while is_exists:
            try:
                await loop.sock_sendall(connection, "Сервер с заданным именем уже существует,\n"
                                                    "попробуйте ввести другое имя:".encode("utf-8"))
                servername = (await loop.sock_recv(connection, 1024)).decode("utf-8").strip()
                is_exists = await check_if_server_exists(self.__psql_pool, servername)
            except Exception as e:
                print(f"Произошла ошибка {e} при попытке создать сервер с другим именем")
                return
        while True:
            try:
                await loop.sock_sendall(connection, "Придумайте хост сервера".encode("utf-8"))
                host = (await loop.sock_recv(connection, 1024)).decode("utf-8").strip()
                await loop.sock_sendall(connection, "Придумайте порт сервера".encode("utf-8"))
                port = int((await loop.sock_recv(connection, 1024)).decode("utf-8").strip())
                if not check_host_port_validity(host, port):
                    await loop.sock_sendall(connection,
                                            "Данные хост + порт уже заняты/ они не корректны".encode("utf-8"))
                    continue
                await add_server_to_table(self.__psql_pool, servername, host, port)
                break
            except Exception as e:
                print(f"Произошла ошибка {e} "
                      f"при попытке создать сервер с указанными хостом и портом с пользователем {connection}")
                return
        try:
            await loop.sock_sendall(connection, "Сервер успешно создан".encode("utf-8"))
        except Exception as e:
            print(f"Произошла ошибка {e} "
                  f"при попытке отослать сообщение об успешном создании сервера пользователю {connection}")
        try:
            self.__run_server(servername, host, port)
        except Exception as e:
            print(f"Произошла неожиданная ошибка {e} при попытке запустить сервер {servername}")



    def __run_server(self, servername: str, host: str, port: int) -> None:
        try:
            if servername in self.__running_servers:
                _, process = self.__running_servers[servername]
                if process.is_alive():
                    print(f"Сервер: {servername} уже запущен")
                    return
            p = Process(target=create_server, args=(host, port, servername), daemon=True)
            p.start()
            if not p.is_alive():
                raise RuntimeError("Процесс не запустился")
            self.__running_servers[servername] = ((host, port), p)
            print(f"Сервер {servername} запущен на {host}:{port}, PID={p.pid}")
        except Exception as e:
            print(f"Произошла ошибка {e} при попытке запустить сервер {servername}")


    async def __create_pool(self) -> None:
        try:
            self.__psql_pool = await asyncpg.create_pool(**self.__psql_params)
        except (asyncpg.exceptions.PostgresError, ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Failed to create pool: {e}")


    async def __receive(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        try:
            while True:
                if connection.fileno() < 0:
                    break
                try:
                    await loop.sock_sendall(connection, "Для получения списка команд напишите /help".encode("utf-8"))
                except Exception as e:
                    print(f"Произошла ошибка {e} "
                          f"при попытке отослать подсказку для получения команд пользователю {connection}")
                message = await loop.sock_recv(connection, 1024)
                if not message:
                    connection.close()
                    break
                message = message.decode("utf-8").strip()
                try:
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
                    print(f"Произошла ошибка {e} при попытке обработать команду пользователя {connection}")
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
