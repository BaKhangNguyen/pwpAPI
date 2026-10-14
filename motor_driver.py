from PCA9685 import PCA9685


# Direction values used by the motor-control methods.
FORWARD = "forward"
BACKWARD = "backward"


# Controls the two rover motors through the PCA9685 motor driver.
class MotorDriver:
    def __init__(self):
        # Connect to the PCA9685 at I2C address 0x40.
        self.pwm = PCA9685(0x40, debug=False)

        # Set the PWM frequency used by the motor driver.
        self.pwm.setPWMFreq(50)

        # Motor A pins.
        self.PWMA = 0
        self.AIN1 = 1
        self.AIN2 = 2

        # Motor B pins.
        self.PWMB = 5
        self.BIN1 = 3
        self.BIN2 = 4

    # Run one motor in the requested direction and speed.
    def run(self, motor, direction, speed):
        # Keep the speed value between 0 and 100.
        speed = max(0, min(100, speed))

        # Motor 0 uses the A-side motor channels.
        if motor == 0:
            self.pwm.setDutycycle(
                self.PWMA,
                speed
            )

            # Set the direction pins for Motor A.
            if direction == FORWARD:
                self.pwm.setLevel(
                    self.AIN1,
                    0
                )
                self.pwm.setLevel(
                    self.AIN2,
                    1
                )
            else:
                self.pwm.setLevel(
                    self.AIN1,
                    1
                )
                self.pwm.setLevel(
                    self.AIN2,
                    0
                )

        # Motor 1 uses the B-side motor channels.
        else:
            self.pwm.setDutycycle(
                self.PWMB,
                speed
            )

            # Set the direction pins for Motor B.
            if direction == FORWARD:
                self.pwm.setLevel(
                    self.BIN1,
                    0
                )
                self.pwm.setLevel(
                    self.BIN2,
                    1
                )
            else:
                self.pwm.setLevel(
                    self.BIN1,
                    1
                )
                self.pwm.setLevel(
                    self.BIN2,
                    0
                )

    # Stop one motor by setting its PWM duty cycle to zero.
    def stop(self, motor):
        if motor == 0:
            self.pwm.setDutycycle(
                self.PWMA,
                0
            )
        else:
            self.pwm.setDutycycle(
                self.PWMB,
                0
            )
