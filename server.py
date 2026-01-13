import asyncio
import asyncpg
import socket
from utils import *
from typing import Optional, Any, Callable


class Server:
    def __init__(self, host: str, port: int,
                 psql_host: str ="localhost", psql_port: int = 5432,
                 psql_user: str = "postgres", psql_password: str ="admin",
                 psql_db: str = "userdata") -> None:
        self.addr: tuple[str, int] = host, port
        self.server: socket.socket = socket.socket()
        self.server.bind(self.addr)
        self.server.setblocking(False)

        self.connections: dict[socket.socket, str] = {}
        self.connection_by_username: dict[str, socket.socket] = {}


        self.psql_params: dict[str, Any] = {
            "host": psql_host,
            "port": psql_port,
            "user": psql_user,
            "password": psql_password,
            "database": psql_db,
            "min_size": 8,
            "max_size": 16
        }
        self.psql_pool: Optional[asyncpg.Pool] = None

        self.commands: dict[str, Callable] = {}
        for obj in dir(self):
            if callable(getattr(self, obj)) and hasattr(getattr(self, obj), "command_name"):
                self.commands[getattr(self, obj).command_name] = getattr(self, obj)


    @command("/help")
    async def help(self, connection: socket.socket) -> None:
        await self.send_message(("Список доступных команд:\n" +
                                 ("\n".join(i for i in self.commands.keys()))).encode("utf-8"), connection, connection)


    @command("/users_online")
    async def users_online(self, connection: socket.socket) -> None:
        await self.send_message((f"Пользователи онлайн:\n" +
                                 ("\n".join(i for i in sorted(self.connections.values())))).encode("utf-8"), connection, connection)


    @command("/whisper")
    async def whisper(self, connection_sender: socket.socket, receiver_username: str, message: bytes) -> None:
        connection_receiver = self.connection_by_username[receiver_username]
        await self.send_message(f"{self.connections[connection_sender]} шепчет вам: ".encode("utf-8") + message, connection_sender, connection_receiver)


    async def send_message(self, message: bytes, connection_sender: socket.socket, connection_receiver: Optional[socket.socket]=None) -> None:
        loop = asyncio.get_event_loop()
        receivers = self.connections.items() if connection_receiver is None else {connection_receiver: self.connections[connection_receiver]}.items()
        for con, username in receivers:
            if con != connection_sender or connection_receiver is not None:
                try:
                    asyncio.create_task(loop.sock_sendall(con, message))
                except Exception as e:
                    print(f"Произошла ошибка {e} с пользователем {self.connections[con]}")
                    await self.disconnect(con)


    async def receive(self, connection: socket.socket) -> None:
        username = self.connections[connection]
        loop = asyncio.get_event_loop()

        try:
            while True:
                message = await loop.sock_recv(connection, 1024)
                if not message:
                    await self.disconnect(connection)
                    break
                message = message.decode("utf-8")
                if (com := message.split()[0]) in self.commands:
                    if len(message.split(" ")) > 1:
                        receiver = message.split(" ")[1]
                        msg = " ".join(message.split()[2:])
                        await self.commands[com](connection, receiver, msg.encode("utf-8"))
                    else:
                        await self.commands[com](connection)
                else:
                    asyncio.create_task(self.send_message(f"{username}: ".encode("utf-8") + message.encode("utf-8"), connection))

        except Exception as e:
            print(f"Произошла ошибка {e} с пользователем {username}")
            await self.disconnect(connection)


    async def disconnect(self, connection: socket.socket) -> None:
        username = self.connections[connection]
        print(f"Разрыв соединения с пользователем {username}...")
        del self.connections[connection]
        del self.connection_by_username[username]
        print(f"Соединение с пользователем {username} разорвано")
        asyncio.create_task(self.send_message(f"Пользователь {username} отключился".encode("utf-8"), connection))


    async def register(self, connection: socket.socket, username: str) -> None:
        loop = asyncio.get_event_loop()

        await loop.sock_sendall(connection, "Вы новенький,\nпридумайте пароль: ".encode("utf-8"))
        received_user_password = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        while not check_password_validity(received_user_password):
            await loop.sock_sendall(connection, "Пароль слишком слабый либо содержит запрещенные символы,\n"
                                                "попробуйте еще раз: ".encode("utf-8"))
            received_user_password = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        async with self.psql_pool.acquire() as psql_connection:
            await psql_connection.execute(add_user_to_table(username, received_user_password))


    async def authenticate(self, connection: socket.socket) -> bool:
        loop = asyncio.get_event_loop()

        await loop.sock_sendall(connection, "Введите имя пользователя: ".encode("utf-8"))
        username = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        while not check_username_validity(username):
            await loop.sock_sendall(connection, "Имя пользователя некорректно,"
                                                "\nпопробуйте другое имя пользователя: ".encode("utf-8"))
            username = (await loop.sock_recv(connection, 1024)).decode("utf-8")
        async with self.psql_pool.acquire() as psql_connection:
            database_user_password = (await psql_connection.fetchrow(get_password_by_username(username)))
            if database_user_password is not None:
                database_user_password = database_user_password["password"]
        received_user_password = None

        try:
            if database_user_password is None:
                await self.register(connection, username)
            else:
                await loop.sock_sendall(connection, "Введите пароль: ".encode("utf-8"))
                received_user_password = (await loop.sock_recv(connection, 1024)).decode("utf-8")
                while received_user_password != database_user_password and received_user_password != "":
                    await loop.sock_sendall(connection, "Вы ввели неправильный пароль,\nпопробуйте еще раз: ".encode("utf-8"))
                    received_user_password = (await loop.sock_recv(connection, 1024)).decode("utf-8")

            if received_user_password == database_user_password:
                self.connections[connection] = username
                self.connection_by_username[username] = connection
                return True
        except Exception as e:
            print(f"С соединением {connection} произошла ошибка {e}")
        return False


    async def connect_user(self, connection: socket.socket) -> None:
        loop = asyncio.get_event_loop()
        connection.setblocking(False)

        status = await self.authenticate(connection)
        if not status:
            print(f"Соединение с {connection} не установлено")
            connection.close()
            return

        username = self.connections[connection]
        print(f"Новое подключение: {username}")
        asyncio.create_task(loop.sock_sendall(connection, f"Вы подключились к серверу {self.addr}"
                                                          f"\nПолучить список доступных команд: /help".encode("utf-8")))
        asyncio.create_task(self.send_message(f"Подключился пользователь: {username}".encode("utf-8"), connection))
        asyncio.create_task(self.receive(connection))


    async def create_pool(self) -> None:
        self.psql_pool = await asyncpg.create_pool(**self.psql_params)


    async def listen(self) -> None:
        self.server.listen()
        await self.create_pool()

        while True:
            loop = asyncio.get_event_loop()
            connection, client_address = await loop.sock_accept(self.server)
            asyncio.create_task(self.connect_user(connection))



if __name__ == "__main__":
    server = Server("127.0.0.1", 8000)
    asyncio.run(server.listen())
