import atexit
import secrets

from flask import Flask, jsonify, request

from database import DatabaseManager
from robot import RobotClass


# Name of the SQLite database used for user accounts.
DATABASE = "users.db"

# Create the database manager, physical rover controller, and Flask app.
database = DatabaseManager(DATABASE)
rover = RobotClass()
app = Flask(__name__)

# Store active login tokens and the usernames connected to them.
tokens = {}


# Check whether an incoming request contains a valid Bearer token.
def is_authenticated():
    authorization = request.headers.get(
        "Authorization",
        ""
    )

    return (
        authorization.startswith("Bearer ")
        and authorization[7:] in tokens
    )


# Run one rover command after verifying authentication.
def run_command(command):
    if not is_authenticated():
        return jsonify(
            success=False,
            message="Authentication required."
        ), 401

    success, message = rover.execute_command(
        command
    )

    return jsonify(
        success=success,
        command=command,
        message=message
    )


# Health endpoint used by the laptop to check whether the API is online.
@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        success=True,
        message="Rover API online."
    )


# Create a new user account and store the hashed password in SQLite.
@app.route("/create-account", methods=["POST"])
def create_account():
    data = request.get_json(silent=True) or {}

    username = data.get(
        "username",
        ""
    ).strip()

    password = data.get(
        "password",
        ""
    )

    # Reject requests with missing login information.
    if not username or not password:
        return jsonify(
            success=False,
            message="Username and password are required."
        ), 400

    success, message = database.create_user(
        username,
        password
    )

    # Return 201 for successful creation or 409 if the username already exists.
    return jsonify(
        success=success,
        message=message
    ), 201 if success else 409


# Authenticate an existing user and create a session token.
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get(
        "username",
        ""
    ).strip()

    password = data.get(
        "password",
        ""
    )

    # Reject empty username or password fields.
    if not username or not password:
        return jsonify(
            success=False,
            message="Username and password are required."
        ), 400

    # Verify the entered password using DatabaseManager.
    if not database.authenticate_user(
        username,
        password
    ):
        return jsonify(
            success=False,
            message="Invalid username or password."
        ), 401

    # Generate a random authentication token for the successful login.
    token = secrets.token_hex(32)
    tokens[token] = username

    return jsonify(
        success=True,
        message="Login successful.",
        token=token
    )


# Movement endpoints send the matching command to RobotClass.
@app.route("/fwd", methods=["POST"])
def fwd():
    return run_command("FWD")


@app.route("/backwd", methods=["POST"])
def backwd():
    return run_command("BACKWD")


@app.route("/left", methods=["POST"])
def left():
    return run_command("LEFT")


@app.route("/right", methods=["POST"])
def right():
    return run_command("RIGHT")


@app.route("/stop", methods=["POST"])
def stop():
    return run_command("STOP")


# Return the current rover movement status to an authenticated user.
@app.route("/status", methods=["GET"])
def status():
    if not is_authenticated():
        return jsonify(
            success=False,
            message="Authentication required."
        ), 401

    return jsonify(
        success=True,
        status=rover.get_status()
    )


# Stop the rover if the Python program exits normally.
atexit.register(rover.STOP)


# Start the Flask server when server.py is run directly.
if __name__ == "__main__":
    try:
        # Listen on all local network interfaces using TCP port 5000.
        # Threaded mode allows multiple API requests to be handled.
        app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    # Make sure the motors are stopped when the server shuts down.
    finally:
        rover.STOP()
