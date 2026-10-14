import threading
import tkinter as tk
from tkinter import messagebox


# Login and account-creation screen for the rover application.
class LoginScreen(tk.Frame):
    def __init__(self, parent, client, on_login):
        super().__init__(parent)

        # Store the API client and the function used after a successful login.
        self.client = client
        self.on_login = on_login

        # Expand the login screen to fill the main window.
        self.pack(fill="both", expand=True)

        # Main container for all login controls.
        container = tk.Frame(self)
        container.pack(expand=True)

        tk.Label(
            container,
            text="DSE MARS ROVER",
            font=("Arial", 30)
        ).pack(pady=20)

        # Username input.
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

        # Password input. show="*" hides the typed password.
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

        # Login and account-creation buttons.
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

        # Display the current Raspberry Pi connection status.
        self.connection_label = tk.Label(
            container,
            text="Checking Raspberry Pi connection..."
        )
        self.connection_label.pack(pady=20)

        # Place the cursor in the username field when the screen opens.
        self.username_box.focus_set()

        # Pressing Enter in the password field attempts login.
        self.password_box.bind("<Return>", lambda event: self.login())

        # Check the Raspberry Pi connection in the background
        # so the GUI does not freeze.
        threading.Thread(
            target=self.check_connection,
            daemon=True
        ).start()

    # Get the current username and password from the input boxes.
    def credentials(self):
        return (
            self.username_box.get().strip(),
            self.password_box.get()
        )

    # Make sure both username and password were entered.
    def valid_credentials(self):
        username, password = self.credentials()

        if not username or not password:
            messagebox.showerror(
                "Error",
                "Enter a username and password."
            )
            return None

        return username, password

    # Enable or disable the login and create-account buttons.
    def set_buttons(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.login_button.config(state=state)
        self.create_button.config(state=state)

    # Check whether the Raspberry Pi Flask API is reachable.
    def check_connection(self):
        success, message = self.client.health()

        # Update Tkinter from the main GUI thread.
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

    # Send a request to create a new user account.
    def create_account(self):
        credentials = self.valid_credentials()

        if not credentials:
            return

        username, password = credentials

        # Disable buttons while the network request is running.
        self.set_buttons(False)

        def request():
            success, message = self.client.create_account(
                username,
                password
            )

            # Re-enable the GUI and display the result.
            def finish():
                self.set_buttons(True)

                if success:
                    messagebox.showinfo("Success", message)
                else:
                    messagebox.showerror("Error", message)

            self.after(0, finish)

        # Run the request in a background thread.
        threading.Thread(
            target=request,
            daemon=True
        ).start()

    # Send the entered credentials to the Raspberry Pi for authentication.
    def login(self):
        credentials = self.valid_credentials()

        if not credentials:
            return

        username, password = credentials

        # Disable buttons while the login request is running.
        self.set_buttons(False)

        def request():
            success, message = self.client.login(
                username,
                password
            )

            # Process the login result on the main Tkinter thread.
            def finish():
                self.set_buttons(True)

                if success:
                    self.on_login(username)
                else:
                    messagebox.showerror("Error", message)

            self.after(0, finish)

        # Run the login request in a background thread.
        threading.Thread(
            target=request,
            daemon=True
        ).start()
