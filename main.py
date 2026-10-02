import tkinter as tk
import sqlite3
import threading
import requests
import secrets

from tkinter import messagebox
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash


DATABASE = "users.db"
API_URL = "http://192.168.240.23:5000"


# Manages the SQLite database used for account creation and authentication.
class DatabaseManager:
    def __init__(self, database):
        self.database = database
        self.initialize_database()

    def connect(self):
        return sqlite3.connect(self.database)

    def initialize_database(self):
        # Create the Users table if it does not already exist.
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Username TEXT UNIQUE NOT NULL,
                    Password TEXT NOT NULL
                )
            """)

    def create_user(self, username, password):
        # Hash the password before storing it in the database.
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO Users (Username, Password) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )

            return True, "Account created successfully."

        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def authenticate_user(self, username, password):
        # Retrieve the stored password hash and compare it to the entered password.
        with self.connect() as connection:
            result = connection.execute(
                "SELECT Password FROM Users WHERE Username = ?",
                (username,)
            ).fetchone()

        return bool(result and check_password_hash(result[0], password))


# Controls the rover.
# The physical rover is simulated until the Raspberry Pi and motors are available.
class RoverController:
    def __init__(self):
        self.current_command = "STOP"

    def execute_command(self, command):
        # Each required API command is connected to a rover action.
        messages = {
            "FWD": "Rover moving forward.",
            "BACKWD": "Rover moving backward.",
            "LEFT": "Rover turning left.",
            "RIGHT": "Rover turning right.",
            "STOP": "Rover stopped."
        }

        if command not in messages:
            return False, "Invalid rover command."

        self.current_command = command
        message = messages[command]

        # This represents the future physical rover action.
        print("[SIMULATION]", message)

        return True, message

    def get_status(self):
        # Returns the current simulated rover state.
        return {
            "command": self.current_command,
            "simulation": True
        }


# Flask API that connects the GUI to the rover controller.
class RoverAPI:
    def __init__(self, database, rover):
        self.database = database
        self.rover = rover
        self.app = Flask(__name__)

        # Tokens are used to make sure only logged-in users can control the rover.
        self.tokens = {}

        self.setup_routes()

    def setup_routes(self):
        # API route for creating an account.
        @self.app.post("/create-account")
        def create_account():
            data = request.get_json(silent=True) or {}

            username = data.get("username", "").strip()
            password = data.get("password", "")

            if not username or not password:
                return jsonify(
                    success=False,
                    message="Username and password are required."
                ), 400

            success, message = self.database.create_user(
                username, password
            )

            return jsonify(
                success=success,
                message=message
            ), 201 if success else 409

        # API route for logging in.
        @self.app.post("/login")
        def login():
            data = request.get_json(silent=True) or {}

            username = data.get("username", "").strip()
            password = data.get("password", "")

            if not username or not password:
                return jsonify(
                    success=False,
                    message="Username and password are required."
                ), 400

            if not self.database.authenticate_user(username, password):
                return jsonify(
                    success=False,
                    message="Invalid username or password."
                ), 401

            # Create an authentication token for the logged-in user.
            token = secrets.token_hex(32)
            self.tokens[token] = username

            return jsonify(
                success=True,
                message="Login successful.",
                token=token
            )

        # Create one API endpoint for each required rover command.
        for command in ("fwd", "backwd", "left", "right", "stop"):
            self.app.add_url_rule(
                f"/{command}",
                command,
                self.command_route(command.upper()),
                methods=["POST"]
            )

        # API route used to check the rover's current state.
        @self.app.get("/status")
        def status():
            if not self.is_authenticated():
                return jsonify(
                    success=False,
                    message="Authentication required."
                ), 401

            return jsonify(
                success=True,
                status=self.rover.get_status()
            )

    def command_route(self, command):
        # Processes one of the five rover commands.
        def route():
            if not self.is_authenticated():
                return jsonify(
                    success=False,
                    message="Authentication required."
                ), 401

            success, message = self.rover.execute_command(command)

            return jsonify(
                success=success,
                command=command,
                message=message
            )

        return route

    def is_authenticated(self):
        # Check whether the request contains a valid login token.
        authorization = request.headers.get("Authorization", "")

        return (
            authorization.startswith("Bearer ")
            and authorization[7:] in self.tokens
        )

    def run(self):
        # Run the API locally so the GUI can communicate with it.
        self.app.run(
            host="192.168.240.23",
            port=5000,
            debug=False,
            use_reloader=False
        )


# Tkinter GUI that communicates with the Flask API.
class RoverGUI:
    def __init__(self, api_url):
        self.api_url = api_url
        self.token = None
        self.username = None

        self.window = tk.Tk()
        self.window.title("DSE Mars Rover Control System")
        self.window.geometry("1200x800")

        self.create_login_screen()

    def create_login_screen(self):
        # Create the login and account creation screen.
        frame = tk.Frame(self.window)
        frame.pack(expand=True)

        tk.Label(
            frame,
            text="DSE MARS ROVER",
            font=("Arial", 30)
        ).pack(pady=20)

        tk.Label(
            frame,
            text="Username",
            font=("Arial", 14)
        ).pack()

        self.username_box = tk.Entry(
            frame,
            width=25,
            font=("Arial", 14)
        )
        self.username_box.pack(pady=5)

        tk.Label(
            frame,
            text="Password",
            font=("Arial", 14)
        ).pack()

        self.password_box = tk.Entry(
            frame,
            width=25,
            show="*",
            font=("Arial", 14)
        )
        self.password_box.pack(pady=5)

        tk.Button(
            frame,
            text="Login",
            width=15,
            command=self.login
        ).pack(pady=10)

        tk.Button(
            frame,
            text="Create Account",
            width=15,
            command=self.create_account
        ).pack()

    def account_request(self, endpoint):
        # Send account information to the Flask API.
        username = self.username_box.get().strip()
        password = self.password_box.get()

        if not username or not password:
            messagebox.showerror(
                "Error",
                "Enter a username and password."
            )
            return

        try:
            response = requests.post(
                f"{self.api_url}/{endpoint}",
                json={
                    "username": username,
                    "password": password
                },
                timeout=5
            )

            data = response.json()

            if response.status_code == 201:
                messagebox.showinfo(
                    "Success",
                    data["message"]
                )
            else:
                messagebox.showerror(
                    "Error",
                    data.get("message", "Request failed.")
                )

        except requests.RequestException:
            messagebox.showerror(
                "Connection Error",
                "The Flask API is not running."
            )

    def create_account(self):
        self.account_request("create-account")

    def login(self):
        # Send login information to the Flask API.
        username = self.username_box.get().strip()
        password = self.password_box.get()

        if not username or not password:
            messagebox.showerror(
                "Error",
                "Enter a username and password."
            )
            return

        try:
            response = requests.post(
                f"{self.api_url}/login",
                json={
                    "username": username,
                    "password": password
                },
                timeout=5
            )

            data = response.json()

            if response.status_code != 200:
                messagebox.showerror(
                    "Error",
                    data.get("message", "Login failed.")
                )
                return

            # Save the token returned by the API.
            self.token = data["token"]
            self.username = username

            self.open_control_system()

        except requests.RequestException:
            messagebox.showerror(
                "Connection Error",
                "The Flask API is not running."
            )

    def open_control_system(self):
        # Remove the login screen and display the four-quadrant control system.
        for widget in self.window.winfo_children():
            widget.destroy()

        self.create_control_system()

    def create_panel(self, x, y, title, background=None):
        # Creates one quadrant of the GUI.
        panel = tk.Frame(
            self.window,
            bd=2,
            relief="solid"
        )

        panel.place(
            relx=x,
            rely=y,
            relwidth=0.5,
            relheight=0.5
        )

        if background:
            screen = tk.Frame(
                panel,
                bg=background
            )

            screen.place(
                relx=0.05,
                rely=0.1,
                relwidth=0.9,
                relheight=0.8
            )

            tk.Label(
                screen,
                text=title,
                fg="white",
                bg=background,
                font=("Arial", 22)
            ).place(
                relx=0.5,
                rely=0.5,
                anchor="center"
            )

        else:
            tk.Label(
                panel,
                text=title,
                font=("Arial", 20)
            ).pack(pady=10)

        return panel

    def create_control_system(self):
        # Four quadrants:
        # 1. Video Stream 1
        # 2. Rover Control
        # 3. Video Stream 2
        # 4. User Log
        self.create_panel(0, 0, "VIDEO STREAM 1", "black")

        controls = self.create_panel(
            0.5,
            0,
            "ROVER CONTROL"
        )

        self.create_panel(0, 0.5, "VIDEO STREAM 2", "black")

        log_panel = self.create_panel(
            0.5,
            0.5,
            "USER LOG"
        )

        # Map GUI buttons to the five required API commands.
        buttons = [
            ("↑", "FWD", 0.50, 0.30),
            ("←", "LEFT", 0.25, 0.55),
            ("→", "RIGHT", 0.75, 0.55),
            ("↓", "BACKWD", 0.50, 0.80)
        ]

        for text, command, x, y in buttons:
            tk.Button(
                controls,
                text=text,
                font=("Arial", 20),
                width=6,
                height=2,
                command=lambda c=command: self.send_command(c)
            ).place(
                relx=x,
                rely=y,
                anchor="center"
            )

        tk.Button(
            controls,
            text="STOP",
            width=8,
            height=2,
            command=lambda: self.send_command("STOP")
        ).place(
            relx=0.60,
            rely=0.55,
            anchor="center"
        )

        tk.Button(
            controls,
            text="STATUS",
            width=8,
            height=2,
            command=self.get_status
        ).place(
            relx=0.40,
            rely=0.55,
            anchor="center"
        )

        # Text box used to display API results and system events.
        self.log_screen = tk.Text(
            log_panel,
            bg="black",
            fg="white",
            font=("Consolas", 12)
        )

        self.log_screen.place(
            relx=0.05,
            rely=0.12,
            relwidth=0.9,
            relheight=0.78
        )

        self.add_log("SYSTEM: Rover control system initialized.")
        self.add_log("SYSTEM: Simulation mode active.")
        self.add_log(f"SYSTEM: Logged in as {self.username}.")

    def send_command(self, command):
        # Run API requests in a separate thread so the GUI stays responsive.
        threading.Thread(
            target=self.send_command_request,
            args=(command,),
            daemon=True
        ).start()

    def send_command_request(self, command):
        # Match each rover command to its Flask API endpoint.
        endpoints = {
            "FWD": "/fwd",
            "BACKWD": "/backwd",
            "LEFT": "/left",
            "RIGHT": "/right",
            "STOP": "/stop"
        }

        try:
            response = requests.post(
                f"{self.api_url}{endpoints[command]}",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                timeout=5
            )

            data = response.json()

            if response.status_code == 200:
                self.add_log(
                    f"COMMAND: {command} | {data['message']}"
                )
            else:
                self.add_log(
                    f"ERROR: {data.get('message', 'Request failed.')}"
                )

        except requests.RequestException:
            self.add_log(
                "ERROR: Unable to communicate with Flask API."
            )

    def get_status(self):
        # Check the rover's current state through the API.
        threading.Thread(
            target=self.get_status_request,
            daemon=True
        ).start()

    def get_status_request(self):
        try:
            response = requests.get(
                f"{self.api_url}/status",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                timeout=5
            )

            data = response.json()

            if response.status_code == 200:
                status = data["status"]

                self.add_log(
                    f"STATUS: Command={status['command']} | "
                    f"Simulation={status['simulation']}"
                )
            else:
                self.add_log(
                    f"ERROR: {data.get('message', 'Request failed.')}"
                )

        except requests.RequestException:
            self.add_log(
                "ERROR: Unable to communicate with Flask API."
            )

    def add_log(self, message):
        # Schedule the log update on Tkinter's main thread.
        self.window.after(
            0,
            lambda: self.write_log(message)
        )

    def write_log(self, message):
        # Safely write a message to the User Log.
        if hasattr(self, "log_screen") and self.log_screen.winfo_exists():
            self.log_screen.insert(
                tk.END,
                message + "\n"
            )
            self.log_screen.see(tk.END)

    def run(self):
        # Start the Tkinter event loop.
        self.window.mainloop()


# Main program execution:
# 1. Create the database.
# 2. Create the rover controller.
# 3. Create and start the Flask API.
# 4. Start the connected Tkinter GUI.
if __name__ == "__main__":
    database_manager = DatabaseManager(DATABASE)
    rover_controller = RoverController()

    rover_api = RoverAPI(
        database_manager,
        rover_controller
    )

    api_thread = threading.Thread(
        target=rover_api.run,
        daemon=True
    )
    api_thread.start()

    gui = RoverGUI(API_URL)
    gui.run()
