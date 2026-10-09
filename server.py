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


@app.get("/health")
def health():
    return jsonify(
        success=True,
        message="Rover API online."
    )


@app.post("/create-account")
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


@app.post("/login")
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


@app.post("/fwd")
def fwd():
    return run_command("FWD")


@app.post("/backwd")
def backwd():
    return run_command("BACKWD")


@app.post("/left")
def left():
    return run_command("LEFT")


@app.post("/right")
def right():
    return run_command("RIGHT")


@app.post("/stop")
def stop():
    return run_command("STOP")


@app.get("/status")
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
