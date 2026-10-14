import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash


# Handles user account storage and authentication with SQLite.
class DatabaseManager:
    def __init__(self, database):
        # Store the database filename and create the Users table if needed.
        self.database = database
        self.initialize_database()

    # Open a connection to the SQLite database.
    def connect(self):
        return sqlite3.connect(self.database)

    # Create the Users table the first time the program runs.
    def initialize_database(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Username TEXT UNIQUE NOT NULL,
                    Password TEXT NOT NULL
                )
            """)

    # Create a new account and store a hashed version of the password.
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

        # A UNIQUE username prevents duplicate accounts.
        except sqlite3.IntegrityError:
            return False, "Username already exists."

    # Check whether the entered username and password are correct.
    def authenticate_user(self, username, password):
        with self.connect() as connection:
            result = connection.execute(
                "SELECT Password FROM Users WHERE Username = ?",
                (username,)
            ).fetchone()

        # Compare the entered password with the stored password hash.
        return bool(
            result
            and check_password_hash(
                result[0],
                password
            )
        )
