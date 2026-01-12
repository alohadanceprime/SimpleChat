import asyncio
import socket



class Client:
    def __init__(self, host, port):
        self.sock: socket.socket = socket.socket()
        self.sock.setblocking(False)
        self.addr: tuple[str, int] = host, port
        self.is_connected: bool = False


    async def receive(self) -> None:
        loop = asyncio.get_event_loop()

        while self.is_connected:
            message = await loop.sock_recv(self.sock, 1024)
            print(message.decode("utf-8"))


    async def send(self) -> None:
        loop = asyncio.get_event_loop()

        while self.is_connected:
            data = await loop.run_in_executor(None, input)

            if not data:
                print("Вы отправили пустое сообщение, вы желаете отключиться от сервера?[YES/NO]")
                response = await loop.run_in_executor(None, input)
                if response == "YES":
                    self.is_connected = False
                    break
            await loop.sock_sendall(self.sock, data.encode("utf-8"))


    async def connect(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.sock_connect(self.sock, self.addr)
        self.is_connected = True

        recv_task = asyncio.create_task(self.receive())
        send_task = asyncio.create_task(self.send())
        try:
            await asyncio.wait((recv_task, send_task), return_when=asyncio.FIRST_COMPLETED)
        except Exception as exc:
            print(f"Произошла ошибка {exc}")
        finally:
            for task in (recv_task, send_task):
                task.cancel()
            self.sock.close()
            print("Соединение разорвано")



if __name__ == "__main__":
    client = Client("127.0.0.1", 8000)
    asyncio.run(client.connect())

