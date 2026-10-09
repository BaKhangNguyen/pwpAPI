import tkinter as tk

from api_client import RoverAPIClient
from config import WINDOW_SIZE, WINDOW_TITLE
from control_screen import ControlScreen
from login_screen import LoginScreen


class RoverApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)

        self.client = RoverAPIClient()
        self.current_screen = None

        self.show_login()

    def clear_screen(self):
        if self.current_screen is not None:
            self.current_screen.destroy()

    def show_login(self):
        self.clear_screen()
        self.current_screen = LoginScreen(
            self.root,
            self.client,
            self.show_controls
        )

    def show_controls(self, username):
        self.clear_screen()
        self.current_screen = ControlScreen(
            self.root,
            self.client,
            username
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RoverApp().run()
