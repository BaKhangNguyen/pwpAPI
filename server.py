import atexit
import secrets

from flask import Flask, jsonify, request

from database import DatabaseManager
from robot import RobotClass


DATABASE = "users.db"

database = DatabaseManager(DATABASE)
rover = RobotClass()
app = Flask(__name__)
tokens = {}


def is_authenticated():
    authorization = request.headers.get(
        "Authorization",
        ""
    )

    return (
        authorization.startswith("Bearer ")
        and authorization[7:] in tokens
    )


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


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        success=True,
        message="Rover API online."
    )


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

    if not username or not password:
        return jsonify(
            success=False,
            message="Username and password are required."
        ), 400

    success, message = database.create_user(
        username,
        password
    )

    return jsonify(
        success=success,
        message=message
    ), 201 if success else 409


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

    if not username or not password:
        return jsonify(
            success=False,
            message="Username and password are required."
        ), 400

    if not database.authenticate_user(
        username,
        password
    ):
        return jsonify(
            success=False,
            message="Invalid username or password."
        ), 401

    token = secrets.token_hex(32)
    tokens[token] = username

    return jsonify(
        success=True,
        message="Login successful.",
        token=token
    )


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


atexit.register(rover.STOP)


if __name__ == "__main__":
    try:
        app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    finally:
        rover.STOP()
