import threading
import time

from motor_driver import BACKWARD, FORWARD, MotorDriver


# Controls the rover's movement using the two physical motors.
class RobotClass:
    def __init__(self):
        # Create the motor driver used to communicate with the motor HAT.
        self.motor = MotorDriver()

        # Motor 1 is connected to the left side and Motor 0 to the right side.
        self.LEFT_MOTOR = 1
        self.RIGHT_MOTOR = 0

        # Both motors use FORWARD as their normal forward direction.
        self.LEFT_FORWARD = FORWARD
        self.RIGHT_FORWARD = FORWARD

        # Use different drive speeds to help the rover move straight.
        self.LEFT_DRIVE_SPEED = 90
        self.RIGHT_DRIVE_SPEED = 62
        self.TURN_SPEED = 65

        # Track the current movement command.
        self.current_command = "STOP"

        # Lock prevents multiple movement commands from changing the motors at once.
        self.lock = threading.Lock()

        # Make sure the rover starts in a stopped state.
        self.STOP()

    # Return the opposite motor direction.
    def opposite(self, direction):
        if direction == FORWARD:
            return BACKWARD

        return FORWARD

    # Stop both motors briefly, then run them with the requested
    # directions and individual speeds.
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

    # Move the rover forward using separate left and right drive speeds.
    def MOVEFWD(self):
        with self.lock:
            self.run_motors(
                self.LEFT_FORWARD,
                self.RIGHT_FORWARD,
                self.LEFT_DRIVE_SPEED,
                self.RIGHT_DRIVE_SPEED
            )

            self.current_command = "FWD"

        return "Rover moving forward."

    # Move both motors in reverse.
    def MOVEBACKWARD(self):
        with self.lock:
            self.run_motors(
                self.opposite(self.LEFT_FORWARD),
                self.opposite(self.RIGHT_FORWARD),
                self.LEFT_DRIVE_SPEED,
                self.RIGHT_DRIVE_SPEED
            )

            self.current_command = "BACKWD"

        return "Rover moving backward."

    # Turn left by reversing the left motor while the right motor moves forward.
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

    # Turn right by moving the left motor forward while reversing the right motor.
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

    # Stop both motors and update the current rover state.
    def STOP(self):
        with self.lock:
            self.motor.stop(self.LEFT_MOTOR)
            self.motor.stop(self.RIGHT_MOTOR)

            self.current_command = "STOP"

        return "Rover stopped."

    # Match an incoming API command to the correct RobotClass method.
    def execute_command(self, command):
        commands = {
            "FWD": self.MOVEFWD,
            "BACKWD": self.MOVEBACKWARD,
            "LEFT": self.TURNLEFT,
            "RIGHT": self.TURNRIGHT,
            "STOP": self.STOP
        }

        # Reject commands that are not supported by the rover.
        if command not in commands:
            return False, "Invalid rover command."

        # Run the selected rover method.
        message = commands[command]()

        # Print the command and result in the Raspberry Pi terminal.
        print(command, message)

        return True, message

    # Return the rover's current command for the /status API endpoint.
    def get_status(self):
        return {
            "command": self.current_command,
            "simulation": False
        }
