import requests

from config import API_URL, REQUEST_TIMEOUT


class RoverAPIClient:
    def __init__(self):
        self.api_url = API_URL.rstrip("/")
        self.timeout = REQUEST_TIMEOUT
        self.token = None
        self.username = None

    def _json(self, response):
        try:
            return response.json()
        except ValueError:
            return {"success": False, "message": "Invalid response from Raspberry Pi."}

    def health(self):
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=self.timeout
            )
            data = self._json(response)
            return response.ok, data.get("message", "Rover API online.")
        except requests.RequestException as error:
            return False, str(error)

    def create_account(self, username, password):
        try:
            response = requests.post(
                f"{self.api_url}/create-account",
                json={
                    "username": username,
                    "password": password
                },
                timeout=self.timeout
            )
            data = self._json(response)
            return response.status_code == 201, data.get("message", "Request failed.")
        except requests.RequestException:
            return False, "Unable to connect to the Raspberry Pi."

    def login(self, username, password):
        try:
            response = requests.post(
                f"{self.api_url}/login",
                json={
                    "username": username,
                    "password": password
                },
                timeout=self.timeout
            )
            data = self._json(response)

            if response.status_code != 200:
                return False, data.get("message", "Login failed.")

            self.token = data["token"]
            self.username = username
            return True, data.get("message", "Login successful.")
        except requests.RequestException:
            return False, "Unable to connect to the Raspberry Pi."

    def _headers(self):
        if not self.token:
            return {}
        return {
            "Authorization": f"Bearer {self.token}"
        }

    def send_command(self, command):
        endpoints = {
            "FWD": "/fwd",
            "BACKWD": "/backwd",
            "LEFT": "/left",
            "RIGHT": "/right",
            "STOP": "/stop"
        }

        if command not in endpoints:
            return False, "Invalid rover command."

        try:
            response = requests.post(
                f"{self.api_url}{endpoints[command]}",
                headers=self._headers(),
                timeout=self.timeout
            )
            data = self._json(response)
            return response.status_code == 200, data.get("message", "Request failed.")
        except requests.RequestException:
            return False, "Unable to communicate with the Raspberry Pi."

    def get_status(self):
        try:
            response = requests.get(
                f"{self.api_url}/status",
                headers=self._headers(),
                timeout=self.timeout
            )
            data = self._json(response)

            if response.status_code != 200:
                return False, data.get("message", "Status request failed.")

            return True, data["status"]
        except requests.RequestException:
            return False, "Unable to communicate with the Raspberry Pi."
