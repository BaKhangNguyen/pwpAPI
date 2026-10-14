import tkinter as tk

from api_client import RoverAPIClient
from config import WINDOW_SIZE, WINDOW_TITLE
from control_screen import ControlScreen
from login_screen import LoginScreen


# Main application class that manages the Tkinter window
# and switches between the login and rover control screens.
class RoverApp:
    def __init__(self):
        # Create the main Tkinter window.
        self.root = tk.Tk()

        # Apply the window title and size from config.py.
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)

        # Create one RoverAPIClient object that is shared
        # by both the login screen and control screen.
        self.client = RoverAPIClient()

        # Track which GUI screen is currently being displayed.
        self.current_screen = None

        # Start the application on the login screen.
        self.show_login()

    # Remove the current screen before displaying a new one.
    def clear_screen(self):
        if self.current_screen is not None:
            self.current_screen.destroy()

    # Display the login screen.
    # Pass show_controls as the callback to run after a successful login.
    def show_login(self):
        self.clear_screen()

        self.current_screen = LoginScreen(
            self.root,
            self.client,
            self.show_controls
        )

    # Replace the login screen with the rover control screen.
    # The authenticated username is passed to ControlScreen.
    def show_controls(self, username):
        self.clear_screen()

        self.current_screen = ControlScreen(
            self.root,
            self.client,
            username
        )

    # Start the Tkinter event loop so the GUI remains active
    # and continues responding to user actions.
    def run(self):
        self.root.mainloop()


# Only start the application when this file is run directly.
# If main.py is imported by another file, the GUI will not launch automatically.
if __name__ == "__main__":
    RoverApp().run()
