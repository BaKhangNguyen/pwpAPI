import threading
import tkinter as tk
from tkinter import messagebox


class LoginScreen(tk.Frame):
    def __init__(self, parent, client, on_login):
        super().__init__(parent)
        self.client = client
        self.on_login = on_login
        self.pack(fill="both", expand=True)

        container = tk.Frame(self)
        container.pack(expand=True)

        tk.Label(
            container,
            text="DSE MARS ROVER",
            font=("Arial", 30)
        ).pack(pady=20)

        tk.Label(
            container,
            text="Username",
            font=("Arial", 14)
        ).pack()

        self.username_box = tk.Entry(
            container,
            width=25,
            font=("Arial", 14)
        )
        self.username_box.pack(pady=5)

        tk.Label(
            container,
            text="Password",
            font=("Arial", 14)
        ).pack()

        self.password_box = tk.Entry(
            container,
            width=25,
            show="*",
            font=("Arial", 14)
        )
        self.password_box.pack(pady=5)

        self.login_button = tk.Button(
            container,
            text="Login",
            width=15,
            command=self.login
        )
        self.login_button.pack(pady=10)

        self.create_button = tk.Button(
            container,
            text="Create Account",
            width=15,
            command=self.create_account
        )
        self.create_button.pack()

        self.connection_label = tk.Label(
            container,
            text="Checking Raspberry Pi connection..."
        )
        self.connection_label.pack(pady=20)

        self.username_box.focus_set()
        self.password_box.bind("<Return>", lambda event: self.login())

        threading.Thread(
            target=self.check_connection,
            daemon=True
        ).start()

    def credentials(self):
        return (
            self.username_box.get().strip(),
            self.password_box.get()
        )

    def valid_credentials(self):
        username, password = self.credentials()

        if not username or not password:
            messagebox.showerror(
                "Error",
                "Enter a username and password."
            )
            return None

        return username, password

    def set_buttons(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.login_button.config(state=state)
        self.create_button.config(state=state)

    def check_connection(self):
        success, message = self.client.health()

        def update():
            if success:
                self.connection_label.config(
                    text=f"Raspberry Pi connected: {message}"
                )
            else:
                self.connection_label.config(
                    text="Raspberry Pi API not reachable."
                )

        self.after(0, update)

    def create_account(self):
        credentials = self.valid_credentials()
        if not credentials:
            return

        username, password = credentials
        self.set_buttons(False)

        def request():
            success, message = self.client.create_account(
                username,
                password
            )

            def finish():
                self.set_buttons(True)

                if success:
                    messagebox.showinfo("Success", message)
                else:
                    messagebox.showerror("Error", message)

            self.after(0, finish)

        threading.Thread(
            target=request,
            daemon=True
        ).start()

    def login(self):
        credentials = self.valid_credentials()
        if not credentials:
            return

        username, password = credentials
        self.set_buttons(False)

        def request():
            success, message = self.client.login(
                username,
                password
            )

            def finish():
                self.set_buttons(True)

                if success:
                    self.on_login(username)
                else:
                    messagebox.showerror("Error", message)

            self.after(0, finish)

        threading.Thread(
            target=request,
            daemon=True
        ).start()
