from PCA9685 import PCA9685


FORWARD = "forward"
BACKWARD = "backward"


class MotorDriver:
    def __init__(self):
        self.pwm = PCA9685(0x40, debug=False)
        self.pwm.setPWMFreq(50)

        self.PWMA = 0
        self.AIN1 = 1
        self.AIN2 = 2
        self.PWMB = 5
        self.BIN1 = 3
        self.BIN2 = 4

    def run(self, motor, direction, speed):
        speed = max(0, min(100, speed))

        if motor == 0:
            self.pwm.setDutycycle(
                self.PWMA,
                speed
            )

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

        else:
            self.pwm.setDutycycle(
                self.PWMB,
                speed
            )

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
