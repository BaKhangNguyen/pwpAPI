import queue
import threading
import time
import tkinter as tk
from io import BytesIO

import requests
from PIL import Image, ImageTk
from config import API_URL


# Main GUI screen for controlling the rover.
class ControlScreen(tk.Frame):
    def __init__(self, parent, client, username):
        super().__init__(parent)

        # Store user and API information.
        self.client = client
        self.username = username

        # Set default rover control state.
        self.control_mode = "HOLD"
        self.active_command = "STOP"
        self.closing = False

        # Locks prevent multiple threads from changing commands
        # or sending API requests at the same time.
        self.command_lock = threading.Lock()
        self.network_lock = threading.Lock()

        # Queues store rover commands and GUI log messages.
        self.command_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.release_job = None
        self.video_running = True
        self.video_queues = {1: queue.Queue(maxsize=2), 2: queue.Queue(maxsize=2)}
        self.video_labels = {}
        self.video_status = {1: "CONNECTING...", 2: "CONNECTING..."}

        # Build and start the control interface.
        self.pack(fill="both", expand=True)
        self.create_layout()
        self.bind_controls()

        # Start the background command worker and log processor.
        threading.Thread(target=self.command_worker, daemon=True).start()
        for stream_number in (1, 2):
            threading.Thread(
                target=self.video_worker, args=(stream_number,), daemon=True
            ).start()
            self.after(60, lambda number=stream_number: self.update_video(number))
        self.after(50, self.process_log_queue)

        self.add_log("SYSTEM: Rover control system initialized.")
        self.add_log(f"SYSTEM: Logged in as {self.username}.")
        self.add_log("SYSTEM: Control mode = HOLD.")
        self.focus_set()

    # Create one of the four equal GUI panels.
    def create_panel(self, relx, rely, title):
        panel = tk.Frame(self, bd=2, relief="solid")
        panel.place(relx=relx, rely=rely, relwidth=0.5, relheight=0.5)
        tk.Label(panel, text=title, font=("Arial", 20)).pack(pady=10)
        return panel

    # Create a black placeholder area for a future video stream.
    def create_video_panel(self, relx, rely, title):
        panel = self.create_panel(relx, rely, title)
        screen = tk.Frame(panel, bg="black")
        screen.place(relx=0.05, rely=0.15, relwidth=0.90, relheight=0.75)
        label = tk.Label(
            screen,
            text=title,
            fg="white",
            bg="black",
            font=("Arial", 20),
        )
        label.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        stream_number = 1 if title == "VIDEO STREAMING 1" else 2
        self.video_labels[stream_number] = label
        return panel

    # Build the four-quadrant GUI layout and rover controls.
    def create_layout(self):
        self.create_video_panel(0.0, 0.0, "VIDEO STREAMING 1")
        controls = self.create_panel(0.5, 0.0, "ROVER CONTROL")
        self.create_video_panel(0.0, 0.5, "VIDEO STREAMING 2")
        log_panel = self.create_panel(0.5, 0.5, "USER LOG")

        # Button for switching between HOLD and CONTINUOUS modes.
        self.mode_button = tk.Button(
            controls,
            text="MODE: HOLD",
            width=18,
            command=self.toggle_control_mode,
        )
        self.mode_button.place(relx=0.5, rely=0.15, anchor="center")

        control_area = tk.Frame(controls)
        control_area.place(relx=0.5, rely=0.56, anchor="center")

        # Directional movement controls.
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

        # Status button requests the current command from the Raspberry Pi.
        self.status_button = tk.Button(
            control_area,
            text="STATUS",
            width=10,
            command=self.get_status,
        )
        self.status_button.grid(row=3, column=1, padx=8, pady=8)

        # Explain how the current control mode works.
        self.mode_help_label = tk.Label(
            controls,
            text="Hold mode: release = STOP",
            font=("Arial", 11),
        )
        self.mode_help_label.place(relx=0.5, rely=0.93, anchor="center")

        # User Log displays commands, errors, and rover status.
        self.log_screen = tk.Text(
            log_panel,
            bg="black",
            fg="white",
            font=("Consolas", 12),
        )
        self.log_screen.place(relx=0.05, rely=0.15, relwidth=0.90, relheight=0.75)

    # Create a movement button with mouse press and release controls.
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

    # Switch between HOLD and CONTINUOUS movement modes.
    def toggle_control_mode(self):
        if self.closing:
            return

        # Stop the rover before changing control modes.
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

    # Mouse input starts movement and stops on release in HOLD mode.
    def mouse_press(self, command):
        if not self.closing:
            self.start_command(command)

    def mouse_release(self):
        if not self.closing and self.control_mode == "HOLD":
            self.force_stop()

    # Bind arrow keys and WASD to rover movement.
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

        # Space is an emergency STOP and closing the window uses safe shutdown.
        self.winfo_toplevel().bind("<space>", lambda event: self.force_stop())
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.close_window)

    # Handle keyboard movement commands.
    def key_press(self, command):
        if self.closing:
            return

        if self.control_mode == "HOLD":
            self.cancel_release_job()

        self.start_command(command)

    # In HOLD mode, delay STOP slightly to handle keyboard auto-repeat.
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

    # Add a new rover command to the command queue.
    def start_command(self, command):
        if self.closing:
            return

        with self.command_lock:
            if self.active_command == command:
                return
            self.active_command = command

        self.command_queue.put(command)

    # Remove commands that are still waiting to be processed.
    def clear_pending_commands(self):
        while True:
            try:
                self.command_queue.get_nowait()
                self.command_queue.task_done()
            except queue.Empty:
                break

    # Stop the rover and give STOP priority over waiting commands.
    def force_stop(self):
        if self.closing:
            return

        self.cancel_release_job()

        with self.command_lock:
            self.active_command = "STOP"

        self.clear_pending_commands()
        self.command_queue.put("STOP")

    # Background worker sends queued commands to the Raspberry Pi API.
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

    # If a movement command fails, attempt to stop the rover for safety.
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

    # Retry STOP if the first safety request does not succeed.
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

    # Each video panel receives frames in its own background thread.
    def video_worker(self, stream_number):
        url = f"{API_URL.rstrip('/')}/video_feed/{stream_number}"
        frames = self.video_queues[stream_number]
        previous_error = None

        while self.video_running and not self.closing:
            token = getattr(self.client, "token", None) or getattr(self.client, "_token", None)
            if not token:
                self.video_status[stream_number] = "LOGIN REQUIRED"
                time.sleep(1)
                continue

            try:
                with requests.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    stream=True,
                    timeout=(5, 10),
                ) as response:
                    if response.status_code != 200:
                        status = f"HTTP {response.status_code}"
                        self.video_status[stream_number] = status
                        if status != previous_error:
                            self.add_log(f"VIDEO {stream_number}: {status} from {url}")
                            previous_error = status
                        time.sleep(2)
                        continue

                    self.video_status[stream_number] = None
                    self.add_log(f"VIDEO {stream_number}: Connected.")
                    previous_error = None
                    buffer = b""

                    for chunk in response.iter_content(chunk_size=8192):
                        if self.closing or not self.video_running:
                            break
                        if not chunk:
                            continue
                        buffer += chunk

                        while True:
                            start = buffer.find(b"\xff\xd8")
                            if start < 0:
                                buffer = buffer[-2:]
                                break
                            end = buffer.find(b"\xff\xd9", start + 2)
                            if end < 0:
                                buffer = buffer[start:]
                                break

                            jpeg = buffer[start:end + 2]
                            buffer = buffer[end + 2:]
                            if frames.full():
                                try:
                                    frames.get_nowait()
                                except queue.Empty:
                                    pass
                            try:
                                frames.put_nowait(jpeg)
                            except queue.Full:
                                pass

                        if len(buffer) > 2_000_000:
                            buffer = buffer[-2:]

                if self.video_running and not self.closing:
                    self.video_status[stream_number] = "RECONNECTING..."
            except requests.RequestException as error:
                if self.closing or not self.video_running:
                    break
                message = str(error)
                self.video_status[stream_number] = "CAMERA OFFLINE"
                if message != previous_error:
                    self.add_log(f"VIDEO {stream_number}: {message}")
                    previous_error = message

            if self.video_running and not self.closing:
                time.sleep(2)

    # Update each video panel on the Tkinter main thread.
    def update_video(self, stream_number):
        if self.closing:
            return

        label = self.video_labels[stream_number]
        frames = self.video_queues[stream_number]
        newest = None
        try:
            while True:
                newest = frames.get_nowait()
        except queue.Empty:
            pass

        if newest is not None:
            try:
                with Image.open(BytesIO(newest)) as image:
                    frame = image.convert("RGB")
                width = max(1, label.winfo_width())
                height = max(1, label.winfo_height())
                resampling = getattr(Image, "Resampling", Image).LANCZOS
                frame.thumbnail((width, height), resampling)
                photo = ImageTk.PhotoImage(frame)
                label.config(image=photo, text="")
                label.image = photo
            except (OSError, ValueError) as error:
                self.add_log(f"VIDEO {stream_number}: Frame error: {error}")
        elif self.video_status[stream_number]:
            label.config(image="", text=self.video_status[stream_number])
            label.image = None

        self.after(60, lambda: self.update_video(stream_number))

    # Request rover status in a separate thread so the GUI stays responsive.
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

    # Place messages into the log queue for safe Tkinter processing.
    def add_log(self, message):
        self.log_queue.put(message)

    # Display queued log messages in the User Log.
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

    # Safely stop the rover before closing the application.
    def close_window(self):
        if self.closing:
            return

        self.closing = True
        self.video_running = False
        self.cancel_release_job()
        self.clear_pending_commands()

        try:
            with self.network_lock:
                self.client.send_command("STOP")
        except Exception:
            pass

        self.winfo_toplevel().destroy()
