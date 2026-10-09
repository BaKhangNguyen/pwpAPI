import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash


class DatabaseManager:
    def __init__(self, database):
        self.database = database
        self.initialize_database()

    def connect(self):
        return sqlite3.connect(self.database)

    def initialize_database(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Username TEXT UNIQUE NOT NULL,
                    Password TEXT NOT NULL
                )
            """)

    def create_user(self, username, password):
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO Users (Username, Password) VALUES (?, ?)",
                    (
                        username,
                        generate_password_hash(password)
                    )
                )

            return True, "Account created successfully."

        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def authenticate_user(self, username, password):
        with self.connect() as connection:
            result = connection.execute(
                "SELECT Password FROM Users WHERE Username = ?",
                (username,)
            ).fetchone()

        return bool(
            result
            and check_password_hash(
                result[0],
                password
            )
        )
