import requests

from config import API_URL, REQUEST_TIMEOUT


# Handles all communication between the laptop GUI and the Raspberry Pi Flask API.
class RoverAPIClient:
    def __init__(self):
        # Store the Raspberry Pi API address without a trailing slash.
        self.api_url = API_URL.rstrip("/")

        # Set the maximum amount of time each HTTP request can wait.
        self.timeout = REQUEST_TIMEOUT

        # The authentication token is empty until the user logs in successfully.
        self.token = None

        # Stores the username of the currently authenticated user.
        self.username = None

    # Safely converts a Flask HTTP response into JSON data.
    def _json(self, response):
        try:
            return response.json()

        # If the server returns data that is not valid JSON,
        # return a controlled error instead of crashing the program.
        except ValueError:
            return {
                "success": False,
                "message": "Invalid response from Raspberry Pi."
            }

    # Checks whether the Raspberry Pi Flask API is online and reachable.
    def health(self):
        try:
            # Send a GET request to the /health endpoint.
            response = requests.get(
                f"{self.api_url}/health",
                timeout=self.timeout
            )

            # Convert the returned Flask response into JSON.
            data = self._json(response)

            # Return whether the request succeeded and the server message.
            return (
                response.ok,
                data.get("message", "Rover API online.")
            )

        # Catch network errors such as timeout, connection failure,
        # or loss of communication with the Raspberry Pi.
        except requests.RequestException as error:
            return False, str(error)

    # Sends a username and password to the Raspberry Pi to create a new account.
    def create_account(self, username, password):
        try:
            # Send account information as JSON to the /create-account endpoint.
            response = requests.post(
                f"{self.api_url}/create-account",
                json={
                    "username": username,
                    "password": password
                },
                timeout=self.timeout
            )

            # Convert the returned response into JSON.
            data = self._json(response)

            # HTTP 201 means the account was created successfully.
            return (
                response.status_code == 201,
                data.get("message", "Request failed.")
            )

        # Return a controlled error if the laptop cannot reach the Raspberry Pi.
        except requests.RequestException:
            return False, "Unable to connect to the Raspberry Pi."

    # Authenticates a user through the Flask API.
    def login(self, username, password):
        try:
            # Send the entered username and password to the /login endpoint.
            response = requests.post(
                f"{self.api_url}/login",
                json={
                    "username": username,
                    "password": password
                },
                timeout=self.timeout
            )

            # Convert the returned response into JSON.
            data = self._json(response)

            # Any status other than 200 means authentication failed.
            if response.status_code != 200:
                return False, data.get(
                    "message",
                    "Login failed."
                )

            # Store the authentication token returned by Flask.
            self.token = data["token"]

            # Store the username for the current logged-in session.
            self.username = username

            # Return login success to the GUI.
            return True, data.get(
                "message",
                "Login successful."
            )

        # Prevent the GUI from crashing if the Raspberry Pi cannot be reached.
        except requests.RequestException:
            return False, "Unable to connect to the Raspberry Pi."

    # Creates the Authorization header used for protected API requests.
    def _headers(self):
        # If the user has not logged in, there is no token to send.
        if not self.token:
            return {}

        # Send the token using the Bearer authentication format.
        return {
            "Authorization": f"Bearer {self.token}"
        }

    # Sends one of the five rover movement commands to the Flask API.
    def send_command(self, command):
        # Map each rover command to its matching Flask endpoint.
        endpoints = {
            "FWD": "/fwd",
            "BACKWD": "/backwd",
            "LEFT": "/left",
            "RIGHT": "/right",
            "STOP": "/stop"
        }

        # Reject any command that is not one of the five accepted commands.
        if command not in endpoints:
            return False, "Invalid rover command."

        try:
            # Send the selected command to the Raspberry Pi.
            # The authentication token is included in the request header.
            response = requests.post(
                f"{self.api_url}{endpoints[command]}",
                headers=self._headers(),
                timeout=self.timeout
            )

            # Convert the response into JSON.
            data = self._json(response)

            # HTTP 200 means the Raspberry Pi successfully processed the command.
            return (
                response.status_code == 200,
                data.get("message", "Request failed.")
            )

        # Return a communication error instead of crashing the GUI.
        except requests.RequestException:
            return (
                False,
                "Unable to communicate with the Raspberry Pi."
            )

    # Requests the rover's current command and physical status.
    def get_status(self):
        try:
            # Send an authenticated GET request to the /status endpoint.
            response = requests.get(
                f"{self.api_url}/status",
                headers=self._headers(),
                timeout=self.timeout
            )

            # Convert the returned response into JSON.
            data = self._json(response)

            # If the server rejects the request, return the error message.
            if response.status_code != 200:
                return False, data.get(
                    "message",
                    "Status request failed."
                )

            # Return the rover status dictionary to the GUI.
            return True, data["status"]

        # Handle network failures without closing the program.
        except requests.RequestException:
            return (
                False,
                "Unable to communicate with the Raspberry Pi."
            )
