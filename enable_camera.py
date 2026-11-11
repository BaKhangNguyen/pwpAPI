"""Add the camera endpoint to the existing server.py without changing rover code."""

from pathlib import Path

server = Path(__file__).with_name("server.py")
if not server.exists():
    raise SystemExit("ERROR: Put enable_camera.py in the same folder as server.py")

source = server.read_text()
import_line = "from camera import register_video_routes"
route_line = "register_video_routes(app, is_authenticated)"

if "def is_authenticated(" not in source or "app = Flask(" not in source:
    raise SystemExit("ERROR: Expected Flask app and is_authenticated() in server.py. No changes made.")
if "def run_command(" not in source:
    raise SystemExit("ERROR: Could not find run_command() in server.py. No changes made.")

updated = source
if import_line not in updated:
    lines = updated.splitlines(keepends=True)
    insert_at = next((i for i, line in enumerate(lines) if line.startswith("from flask import ")), None)
    if insert_at is None:
        raise SystemExit("ERROR: Flask import not found in server.py. No changes made.")
    lines.insert(insert_at + 1, import_line + "\n")
    updated = "".join(lines)

if route_line not in updated:
    marker = "def run_command("
    updated = updated.replace(marker, route_line + "\n\n" + marker, 1)

if updated == source:
    print("Camera routes already installed. No changes needed.")
else:
    backup = server.with_name("server.py.before_camera_backup")
    if not backup.exists():
        backup.write_text(source)
    compile(updated, str(server), "exec")
    server.write_text(updated)
    print("Updated server.py with /video_feed and /camera_check.")
    print("Backup saved as server.py.before_camera_backup")
