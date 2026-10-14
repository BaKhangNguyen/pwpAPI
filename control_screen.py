import queue
import threading
import time
import tkinter as tk


class ControlScreen(tk.Frame):
    def __init__(self, parent, client, username):
        super().__init__(parent)
        self.client = client
        self.username = username
        self.control_mode = "HOLD"
        self.active_command = "STOP"
        self.closing = False
        self.command_lock = threading.Lock()
        self.network_lock = threading.Lock()
        self.command_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.release_job = None

        self.pack(fill="both", expand=True)
        self.create_layout()
        self.bind_controls()

        threading.Thread(target=self.command_worker, daemon=True).start()
        self.after(50, self.process_log_queue)

        self.add_log("SYSTEM: Rover control system initialized.")
        self.add_log(f"SYSTEM: Logged in as {self.username}.")
        self.add_log("SYSTEM: Control mode = HOLD.")
        self.focus_set()

    def create_panel(self, relx, rely, title):
        panel = tk.Frame(self, bd=2, relief="solid")
        panel.place(relx=relx, rely=rely, relwidth=0.5, relheight=0.5)
        tk.Label(panel, text=title, font=("Arial", 20)).pack(pady=10)
        return panel

    def create_video_panel(self, relx, rely, title):
        panel = self.create_panel(relx, rely, title)
        screen = tk.Frame(panel, bg="black")
        screen.place(relx=0.05, rely=0.15, relwidth=0.90, relheight=0.75)
        tk.Label(
            screen,
            text=title,
            fg="white",
            bg="black",
            font=("Arial", 20),
        ).place(relx=0.5, rely=0.5, anchor="center")
        return panel

    def create_layout(self):
        self.create_video_panel(0.0, 0.0, "VIDEO STREAMING 1")
        controls = self.create_panel(0.5, 0.0, "ROVER CONTROL")
        self.create_video_panel(0.0, 0.5, "VIDEO STREAMING 2")
        log_panel = self.create_panel(0.5, 0.5, "USER LOG")

        self.mode_button = tk.Button(
            controls,
            text="MODE: HOLD",
            width=18,
            command=self.toggle_control_mode,
        )
        self.mode_button.place(relx=0.5, rely=0.15, anchor="center")

        control_area = tk.Frame(controls)
        control_area.place(relx=0.5, rely=0.56, anchor="center")

        self.forward_button = self.make_drive_button(control_area, "↑", "FWD")
        self.forward_button.grid(row=0, column=1, padx=8, pady=8)

        self.left_button = self.make_drive_button(control_area, "←", "LEFT")
        self.left_button.grid(row=1, column=0, padx=8, pady=8)

        self.stop_button = tk.Button(
            control_area,
            text="STOP",
            width=8,
            height=3,
            command=self.force_stop,
        )
        self.stop_button.grid(row=1, column=1, padx=8, pady=8)

        self.right_button = self.make_drive_button(control_area, "→", "RIGHT")
        self.right_button.grid(row=1, column=2, padx=8, pady=8)

        self.backward_button = self.make_drive_button(control_area, "↓", "BACKWD")
        self.backward_button.grid(row=2, column=1, padx=8, pady=8)

        self.status_button = tk.Button(
            control_area,
            text="STATUS",
            width=10,
            command=self.get_status,
        )
        self.status_button.grid(row=3, column=1, padx=8, pady=8)

        self.mode_help_label = tk.Label(
            controls,
            text="Hold mode: release = STOP",
            font=("Arial", 11),
        )
        self.mode_help_label.place(relx=0.5, rely=0.93, anchor="center")

        self.log_screen = tk.Text(
            log_panel,
            bg="black",
            fg="white",
            font=("Consolas", 12),
        )
        self.log_screen.place(relx=0.05, rely=0.15, relwidth=0.90, relheight=0.75)

    def make_drive_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            font=("Arial", 20),
            width=6,
            height=2,
        )
        button.bind(
            "<ButtonPress-1>",
            lambda event, value=command: self.mouse_press(value),
        )
        button.bind("<ButtonRelease-1>", lambda event: self.mouse_release())
        return button

    def toggle_control_mode(self):
        if self.closing:
            return

        self.force_stop()

        if self.control_mode == "HOLD":
            self.control_mode = "CONTINUOUS"
            self.mode_button.config(text="MODE: CONTINUOUS")
            self.mode_help_label.config(text="Continuous mode: press STOP to stop")
        else:
            self.control_mode = "HOLD"
            self.mode_button.config(text="MODE: HOLD")
            self.mode_help_label.config(text="Hold mode: release = STOP")

        self.add_log(f"SYSTEM: Control mode = {self.control_mode}.")
        self.focus_set()

    def mouse_press(self, command):
        if not self.closing:
            self.start_command(command)

    def mouse_release(self):
        if not self.closing and self.control_mode == "HOLD":
            self.force_stop()

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
            "D": "RIGHT",
        }

        for key, command in key_commands.items():
            self.winfo_toplevel().bind(
                f"<KeyPress-{key}>",
                lambda event, value=command: self.key_press(value),
            )
            self.winfo_toplevel().bind(
                f"<KeyRelease-{key}>",
                lambda event: self.key_release(),
            )

        self.winfo_toplevel().bind("<space>", lambda event: self.force_stop())
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.close_window)

    def key_press(self, command):
        if self.closing:
            return

        if self.control_mode == "HOLD":
            self.cancel_release_job()

        self.start_command(command)

    def key_release(self):
        if self.closing or self.control_mode != "HOLD":
            return

        self.cancel_release_job()
        self.release_job = self.after(80, self.finish_key_release)

    def finish_key_release(self):
        self.release_job = None
        if not self.closing and self.control_mode == "HOLD":
            self.force_stop()

    def cancel_release_job(self):
        if self.release_job is not None:
            try:
                self.after_cancel(self.release_job)
            except tk.TclError:
                pass
            self.release_job = None

    def start_command(self, command):
        if self.closing:
            return

        with self.command_lock:
            if self.active_command == command:
                return
            self.active_command = command

        self.command_queue.put(command)

    def clear_pending_commands(self):
        while True:
            try:
                self.command_queue.get_nowait()
                self.command_queue.task_done()
            except queue.Empty:
                break

    def force_stop(self):
        if self.closing:
            return

        self.cancel_release_job()

        with self.command_lock:
            self.active_command = "STOP"

        self.clear_pending_commands()
        self.command_queue.put("STOP")

    def command_worker(self):
        while True:
            command = self.command_queue.get()

            try:
                with self.network_lock:
                    success, message = self.client.send_command(command)

                if success:
                    self.add_log(f"COMMAND: {command} | {message}")
                else:
                    self.handle_command_failure(command, message)

            except Exception as error:
                self.handle_command_failure(command, str(error))

            finally:
                self.command_queue.task_done()

    def handle_command_failure(self, command, message):
        self.add_log(f"ERROR: {command} | {message}")

        if command != "STOP":
            with self.command_lock:
                if self.active_command == command:
                    self.active_command = "STOP"

            stop_success = self.send_stop_with_retry()

            if stop_success:
                self.add_log("SAFETY: STOP confirmed after command failure.")
            else:
                self.add_log("SAFETY ERROR: STOP could not be confirmed.")
        else:
            stop_success = self.send_stop_with_retry(attempts=1)

            if stop_success:
                self.add_log("SAFETY: STOP confirmed on retry.")
            else:
                self.add_log("SAFETY ERROR: STOP could not be confirmed.")

    def send_stop_with_retry(self, attempts=2):
        for attempt in range(attempts):
            try:
                with self.network_lock:
                    success, message = self.client.send_command("STOP")

                if success:
                    with self.command_lock:
                        self.active_command = "STOP"
                    return True

            except Exception:
                pass

            if attempt < attempts - 1:
                time.sleep(0.10)

        return False

    def get_status(self):
        if self.closing:
            return

        threading.Thread(target=self.get_status_request, daemon=True).start()

    def get_status_request(self):
        try:
            with self.network_lock:
                success, result = self.client.get_status()

            if success:
                self.add_log(
                    f"STATUS: Command={result['command']} | "
                    f"Simulation={result['simulation']}"
                )
            else:
                self.add_log(f"ERROR: STATUS | {result}")

        except Exception as error:
            self.add_log(f"ERROR: STATUS | {error}")

    def add_log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        if self.closing:
            return

        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if self.log_screen.winfo_exists():
                self.log_screen.insert(tk.END, message + "\n")
                self.log_screen.see(tk.END)

            self.log_queue.task_done()

        self.after(50, self.process_log_queue)

    def close_window(self):
        if self.closing:
            return

        self.closing = True
        self.cancel_release_job()
        self.clear_pending_commands()

        try:
            with self.network_lock:
                self.client.send_command("STOP")
        except Exception:
            pass

        self.winfo_toplevel().destroy()
