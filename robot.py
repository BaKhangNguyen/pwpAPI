import threading
import time

from motor_driver import BACKWARD, FORWARD, MotorDriver


class RobotClass:
    def __init__(self):
        self.motor = MotorDriver()

        self.LEFT_MOTOR = 1
        self.RIGHT_MOTOR = 0

        self.LEFT_FORWARD = FORWARD
        self.RIGHT_FORWARD = FORWARD

        self.DRIVE_SPEED = 70
        self.TURN_SPEED = 65

        self.current_command = "STOP"
        self.lock = threading.Lock()

        self.STOP()

    def opposite(self, direction):
        if direction == FORWARD:
            return BACKWARD
        return FORWARD

    def run_motors(
        self,
        left_direction,
        right_direction,
        left_speed,
        right_speed
    ):
        self.motor.stop(self.LEFT_MOTOR)
        self.motor.stop(self.RIGHT_MOTOR)

        time.sleep(0.03)

        self.motor.run(
            self.LEFT_MOTOR,
            left_direction,
            left_speed
        )

        self.motor.run(
            self.RIGHT_MOTOR,
            right_direction,
            right_speed
        )

    def MOVEFWD(self):
        with self.lock:
            self.run_motors(
                self.LEFT_FORWARD,
                self.RIGHT_FORWARD,
                self.DRIVE_SPEED,
                self.DRIVE_SPEED
            )
            self.current_command = "FWD"

        return "Rover moving forward."

    def MOVEBACKWARD(self):
        with self.lock:
            self.run_motors(
                self.opposite(self.LEFT_FORWARD),
                self.opposite(self.RIGHT_FORWARD),
                self.DRIVE_SPEED,
                self.DRIVE_SPEED
            )
            self.current_command = "BACKWD"

        return "Rover moving backward."

    def TURNLEFT(self):
        with self.lock:
            self.run_motors(
                self.opposite(self.LEFT_FORWARD),
                self.RIGHT_FORWARD,
                self.TURN_SPEED,
                self.TURN_SPEED
            )
            self.current_command = "LEFT"

        return "Rover turning left."

    def TURNRIGHT(self):
        with self.lock:
            self.run_motors(
                self.LEFT_FORWARD,
                self.opposite(self.RIGHT_FORWARD),
                self.TURN_SPEED,
                self.TURN_SPEED
            )
            self.current_command = "RIGHT"

        return "Rover turning right."

    def STOP(self):
        with self.lock:
            self.motor.stop(self.LEFT_MOTOR)
            self.motor.stop(self.RIGHT_MOTOR)
            self.current_command = "STOP"

        return "Rover stopped."

    def execute_command(self, command):
        commands = {
            "FWD": self.MOVEFWD,
            "BACKWD": self.MOVEBACKWARD,
            "LEFT": self.TURNLEFT,
            "RIGHT": self.TURNRIGHT,
            "STOP": self.STOP
        }

        if command not in commands:
            return False, "Invalid rover command."

        message = commands[command]()
        print(command, message)

        return True, message

    def get_status(self):
        return {
            "command": self.current_command,
            "simulation": False
        }
