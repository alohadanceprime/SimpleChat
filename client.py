import asyncio
import socket
from typing import Optional

class Client:
    def __init__(self, host, port):
        self.__sock: socket.socket = socket.socket()
        self.__sock.setblocking(False)
        self._addr: tuple[str, int] = host, port
        self._is_connected: bool = False
        self.__receive_task: Optional[asyncio.Task] = None
        self.__send_task: Optional[asyncio.Task]  = None


    async def __receive(self) -> None:
        loop = asyncio.get_event_loop()

        while self._is_connected:
            message = await loop.sock_recv(self.__sock, 1024)
            print(message.decode("utf-8"))


    async def __send(self) -> None:
        loop = asyncio.get_event_loop()

        while self._is_connected:
            response = await loop.run_in_executor(None, input)
            if not response:
                print("Вы отправили пустое сообщение, вы желаете отключиться от сервера?[YES/NO]")
                response = await loop.run_in_executor(None, input)
                if response == "YES":
                    self._is_connected = False
                    break

            elif (command := response.split(" ")[0]) == "/connect":
                if self.__receive_task:
                    self.__receive_task.cancel()
                servername = response.split(" ")[1]
                await loop.sock_sendall(self.__sock, (command + " " + servername).encode("utf-8"))
                server_response = (await loop.sock_recv(self.__sock, 1024)).decode("utf-8")

                if server_response == "connection_approved":
                    print("Выполняется подключение к серверу...")
                    await loop.sock_sendall(self.__sock, "ready_for_connection".encode("utf-8"))
                    server_response = (await loop.sock_recv(self.__sock, 1024)).decode("utf-8")
                    host, port = server_response.split(" ")
                    port = int(port)
                    self.__sock.close()
                    self.__sock = socket.socket()
                    self.__sock.setblocking(False)
                    self._addr = host, port
                    await self.connect()
                else:
                    asyncio.create_task(self.__receive())
                    print("Такой сервер не существует")

                    continue
            await loop.sock_sendall(self.__sock, response.encode("utf-8"))


    async def connect(self) -> None:
        current = asyncio.current_task()
        if self.__receive_task and self.__receive_task is not current:
            self.__receive_task.cancel()
        if self.__send_task and self.__send_task is not current:
            self.__send_task.cancel()

        loop = asyncio.get_event_loop()
        await loop.sock_connect(self.__sock, self._addr)
        self._is_connected = True
        self.__receive_task = asyncio.create_task(self.__receive())
        self.__send_task = asyncio.create_task(self.__send())

        try:
            await self.__send_task
        except Exception as e:
            print(f"Произошла ошибка {e}")
        finally:
            self._is_connected = False
            for task in (self.__receive_task, self.__send_task):
                task.cancel()
            self.__sock.close()
            print("Соединение разорвано")



if __name__ == "__main__":
    client = Client("127.0.0.1", 8000)
    asyncio.run(client.connect())
