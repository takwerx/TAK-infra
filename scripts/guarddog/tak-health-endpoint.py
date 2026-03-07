#!/usr/bin/env python3
"""Guard Dog health endpoint. Returns 200 if TAK Server is healthy, 503 otherwise.
In two-server mode, also checks remote DB reachability (reads config from
/opt/tak-guarddog/guarddog.conf if present)."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, json, socket, os

_conf_path = '/opt/tak-guarddog/guarddog.conf'
_conf = {}
if os.path.isfile(_conf_path):
    try:
        with open(_conf_path) as f:
            _conf = json.load(f)
    except Exception:
        pass

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def check_health(self):
        checks = {}

        r = subprocess.run(['systemctl', 'is-active', 'takserver'], capture_output=True)
        checks['takserver'] = r.returncode == 0

        r = subprocess.run(['ss', '-ltn', 'sport = :8089'], capture_output=True, text=True)
        checks['port_8089'] = 'LISTEN' in (r.stdout or '')

        r = subprocess.run(['pgrep', '-f', 'spring.profiles.active=messaging'], capture_output=True)
        checks['messaging'] = r.returncode == 0

        r = subprocess.run(['pgrep', '-f', 'spring.profiles.active=api'], capture_output=True)
        checks['api'] = r.returncode == 0

        # Two-server: check remote DB port
        db_host = _conf.get('db_host', '')
        db_port = int(_conf.get('db_port', 0))
        if db_host and db_port:
            try:
                s = socket.create_connection((db_host, db_port), timeout=5)
                s.close()
                checks['remote_db'] = True
            except Exception:
                checks['remote_db'] = False

        checks['healthy'] = all(checks.values())
        return checks

    def do_HEAD(self):
        if self.path == '/health':
            checks = self.check_health()
            self.send_response(200 if checks['healthy'] else 503)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            checks = self.check_health()
            self.send_response(200 if checks['healthy'] else 503)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(checks).encode() + b'\n')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()
