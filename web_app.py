"""Simple browser replacement for the existing Tkinter login and control screens.

Keep the Raspberry Pi's server.py, robot.py, motor_driver.py and database.py unchanged.
Run this on the Mac in the existing pwpAPI folder.
"""

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from config import API_URL, REQUEST_TIMEOUT

app = FastAPI(title="DSE Mars Rover")
ROVER_URL = API_URL.rstrip("/")
movement_lock = asyncio.Lock()


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(Path(__file__).with_name("index.html"), headers={"Cache-Control": "no-store"})


async def relay(method: str, path: str, request: Request, with_body: bool = False):
    """Forward only known requests to the original Raspberry Pi Flask API."""
    headers = {}
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        headers["Authorization"] = authorization

    try:
        body = await request.json() if with_body else None
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, trust_env=False) as client:
            response = await client.request(method, ROVER_URL + path, headers=headers, json=body)
        try:
            content = response.json()
        except ValueError:
            return JSONResponse({"success": False, "message": "Invalid Raspberry Pi response."}, status_code=502)
        return JSONResponse(content, status_code=response.status_code, headers={"Cache-Control": "no-store"})
    except (httpx.RequestError, httpx.TimeoutException):
        return JSONResponse({"success": False, "message": "Raspberry Pi API not reachable."}, status_code=502)
    except ValueError:
        return JSONResponse({"success": False, "message": "Invalid JSON request."}, status_code=400)


@app.get("/api/health")
async def health(request: Request):
    return await relay("GET", "/health", request)


@app.post("/api/create-account")
async def create_account(request: Request):
    return await relay("POST", "/create-account", request, with_body=True)


@app.post("/api/login")
async def login(request: Request):
    return await relay("POST", "/login", request, with_body=True)


@app.get("/api/status")
async def status(request: Request):
    async with movement_lock:
        return await relay("GET", "/status", request)


@app.post("/api/{command}")
async def movement(command: str, request: Request):
    if command not in ("fwd", "backwd", "left", "right", "stop"):
        return JSONResponse({"success": False, "message": "Invalid command."}, status_code=404)
    async with movement_lock:
        return await relay("POST", "/" + command, request)
