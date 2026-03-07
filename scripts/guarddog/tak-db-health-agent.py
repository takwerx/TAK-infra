#!/usr/bin/env python3
"""Lightweight health endpoint for a TAK Server database server (Server One).
Deployed by Guard Dog in two-server mode. Listens on port 8080 and exposes
/health which checks PostgreSQL cluster status and cot database reachability.
No dependencies beyond Python 3 stdlib + psql on the host."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, json

class DBHealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _check(self):
        checks = {}

        # PostgreSQL cluster running
        r = subprocess.run(['pg_isready', '-q'], capture_output=True, timeout=5)
        checks['pg_ready'] = r.returncode == 0

        # cot database exists and is accessible
        r = subprocess.run(
            ['sudo', '-u', 'postgres', 'psql', '-lqt'],
            capture_output=True, text=True, timeout=10, cwd='/'
        )
        checks['cot_db'] = 'cot' in (r.stdout or '') if r.returncode == 0 else False

        # Disk usage on root
        try:
            r = subprocess.run(['df', '--output=pcent', '/'], capture_output=True, text=True, timeout=5)
            pct = int(r.stdout.strip().split('\n')[-1].strip().rstrip('%'))
            checks['disk_ok'] = pct < 90
            checks['disk_pct'] = pct
        except Exception:
            checks['disk_ok'] = True
            checks['disk_pct'] = -1

        checks['healthy'] = checks['pg_ready'] and checks['cot_db'] and checks['disk_ok']
        return checks

    def do_HEAD(self):
        checks = self._check()
        self.send_response(200 if checks['healthy'] else 503)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            checks = self._check()
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
    server = HTTPServer(('0.0.0.0', 8080), DBHealthHandler)
    server.serve_forever()
