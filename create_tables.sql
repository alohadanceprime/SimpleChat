CREATE TABLE IF NOT EXISTS users_list(
    username VARCHAR(64) PRIMARY KEY,
    password VARCHAR(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS servers_list(
    servername VARCHAR(128) PRIMARY KEY,
    host VARCHAR(16)  NOT NULL,
    port INTEGER NOT NULL,
    UNIQUE (host, port)
);