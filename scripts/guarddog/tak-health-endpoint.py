#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging
    
    def check_health(self):
        healthy = True
        
        result = subprocess.run(['systemctl', 'is-active', 'takserver'], capture_output=True)
        if result.returncode != 0:
            healthy = False
        
        result = subprocess.run(['ss', '-ltn', 'sport = :8089'], capture_output=True, text=True)
        if 'LISTEN' not in (result.stdout or ''):
            healthy = False
        
        result = subprocess.run(['pgrep', '-f', 'spring.profiles.active=messaging'], capture_output=True)
        if result.returncode != 0:
            healthy = False
        
        result = subprocess.run(['pgrep', '-f', 'spring.profiles.active=api'], capture_output=True)
        if result.returncode != 0:
            healthy = False
        
        return healthy
    
    def do_HEAD(self):
        if self.path == '/health':
            healthy = self.check_health()
            if healthy:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Content-Length', '21')
                self.end_headers()
            else:
                self.send_response(503)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Content-Length', '23')
                self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/health':
            healthy = self.check_health()
            if healthy:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'TAK Server: Healthy\n')
            else:
                self.send_response(503)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'TAK Server: Unhealthy\n')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()
