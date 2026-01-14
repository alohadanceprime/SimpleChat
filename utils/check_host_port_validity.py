def check_host_port_validity(host: str, port: int) -> bool:
    if host != "localhost":
        threes = list(map(int, host.split(".")))
        if len(threes) != 4:
            return False
        for num in threes:
            if num < 0 or num > 255:
                return False

    if port < 0 or port > 65535:
        return False

    return True
