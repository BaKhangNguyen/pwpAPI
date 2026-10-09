import queue
import threading
import tkinter as tk


class ControlScreen(tk.Frame):
    def __init__(self, parent, client, username):
        super().__init__(parent)
        self.client = client
        self.username = username
        self.active_command = "STOP"
        self.command_lock = threading.Lock()
        self.command_queue = queue.Queue()
        self.release_job = None
        self.pack(fill="both", expand=True)

        self.create_layout()
        self.bind_controls()

        threading.Thread(
            target=self.command_worker,
            daemon=True
        ).start()

        self.add_log("SYSTEM: Rover control system initialized.")
        self.add_log("SYSTEM: Video streaming disabled.")
        self.add_log(f"SYSTEM: Logged in as {self.username}.")
        self.add_log("SYSTEM: Hold an arrow key or WASD to drive. Release to stop.")

        self.focus_set()

    def create_panel(self, row, column, title):
        panel = tk.Frame(
            self,
            bd=2,
            relief="solid"
        )
        panel.grid(
            row=row,
            column=column,
            sticky="nsew"
        )

        tk.Label(
            panel,
            text=title,
            font=("Arial", 20)
        ).pack(pady=10)

        return panel

    def create_video_panel(self, row, column, title):
        panel = self.create_panel(row, column, title)

        screen = tk.Frame(
            panel,
            bg="black"
        )
        screen.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )

        tk.Label(
            screen,
            text="VIDEO STREAM DISABLED",
            fg="white",
            bg="black",
            font=("Arial", 20)
        ).place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        return panel

    def create_layout(self):
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self.create_video_panel(
            0,
            0,
            "VIDEO STREAM 1"
        )

        controls = self.create_panel(
            0,
            1,
            "ROVER CONTROL"
        )

        self.create_video_panel(
            1,
            0,
            "VIDEO STREAM 2"
        )

        log_panel = self.create_panel(
            1,
            1,
            "USER LOG"
        )

        control_area = tk.Frame(controls)
        control_area.pack(expand=True)

        self.forward_button = self.make_drive_button(
            control_area,
            "↑",
            "FWD"
        )
        self.forward_button.grid(
            row=0,
            column=1,
            padx=8,
            pady=8
        )

        self.left_button = self.make_drive_button(
            control_area,
            "←",
            "LEFT"
        )
        self.left_button.grid(
            row=1,
            column=0,
            padx=8,
            pady=8
        )

        self.stop_button = tk.Button(
            control_area,
            text="STOP",
            width=8,
            height=3,
            command=self.force_stop
        )
        self.stop_button.grid(
            row=1,
            column=1,
            padx=8,
            pady=8
        )

        self.right_button = self.make_drive_button(
            control_area,
            "→",
            "RIGHT"
        )
        self.right_button.grid(
            row=1,
            column=2,
            padx=8,
            pady=8
        )

        self.backward_button = self.make_drive_button(
            control_area,
            "↓",
            "BACKWD"
        )
        self.backward_button.grid(
            row=2,
            column=1,
            padx=8,
            pady=8
        )

        tk.Button(
            control_area,
            text="STATUS",
            width=10,
            command=self.get_status
        ).grid(
            row=3,
            column=1,
            padx=8,
            pady=8
        )

        tk.Label(
            controls,
            text="Arrow keys / WASD = drive     Space = STOP",
            font=("Arial", 11)
        ).pack(pady=10)

        self.log_screen = tk.Text(
            log_panel,
            bg="black",
            fg="white",
            font=("Consolas", 12)
        )
        self.log_screen.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )

    def make_drive_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            font=("Arial", 20),
            width=6,
            height=2
        )

        button.bind(
            "<ButtonPress-1>",
            lambda event, value=command: self.start_command(value)
        )

        button.bind(
            "<ButtonRelease-1>",
            lambda event: self.force_stop()
        )

        return button

    def bind_controls(self):
        key_commands = {
            "Up": "FWD",
            "w": "FWD",
            "W": "FWD",
            "Down": "BACKWD",
            "s": "BACKWD",
            "S": "BACKWD",
            "Left": "LEFT",
            "a": "LEFT",
            "A": "LEFT",
            "Right": "RIGHT",
            "d": "RIGHT",
            "D": "RIGHT"
        }

        for key, command in key_commands.items():
            self.winfo_toplevel().bind(
                f"<KeyPress-{key}>",
                lambda event, value=command: self.key_press(value)
            )
            self.winfo_toplevel().bind(
                f"<KeyRelease-{key}>",
                lambda event: self.key_release()
            )

        self.winfo_toplevel().bind(
            "<space>",
            lambda event: self.force_stop()
        )

        self.winfo_toplevel().protocol(
            "WM_DELETE_WINDOW",
            self.close_window
        )

    def key_press(self, command):
        if self.release_job is not None:
            self.after_cancel(self.release_job)
            self.release_job = None

        self.start_command(command)

    def key_release(self):
        if self.release_job is not None:
            self.after_cancel(self.release_job)

        self.release_job = self.after(
            80,
            self.finish_key_release
        )

    def finish_key_release(self):
        self.release_job = None
        self.force_stop()

    def start_command(self, command):
        with self.command_lock:
            if self.active_command == command:
                return

            self.active_command = command

        self.command_queue.put(command)

    def force_stop(self):
        with self.command_lock:
            self.active_command = "STOP"

        self.command_queue.put("STOP")

    def command_worker(self):
        while True:
            command = self.command_queue.get()

            success, message = self.client.send_command(command)

            if success:
                self.add_log(
                    f"COMMAND: {command} | {message}"
                )
            else:
                self.add_log(
                    f"ERROR: {message}"
                )

            self.command_queue.task_done()

    def get_status(self):
        def request():
            success, result = self.client.get_status()

            if success:
                self.add_log(
                    f"STATUS: Command={result['command']} | "
                    f"Simulation={result['simulation']}"
                )
            else:
                self.add_log(
                    f"ERROR: {result}"
                )

        threading.Thread(
            target=request,
            daemon=True
        ).start()

    def add_log(self, message):
        self.after(
            0,
            lambda: self.write_log(message)
        )

    def write_log(self, message):
        if self.log_screen.winfo_exists():
            self.log_screen.insert(
                tk.END,
                message + "\n"
            )
            self.log_screen.see(tk.END)

    def close_window(self):
        self.client.send_command("STOP")
        self.winfo_toplevel().destroy()
