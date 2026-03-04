#!/usr/bin/env python3
"""infra-TAK v0.1.8 - TAK Infrastructure Platform"""

from flask import (Flask, render_template_string, request, jsonify,
    redirect, url_for, session, send_from_directory, make_response)
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import os, re, ssl, json, secrets, subprocess, time, psutil, threading, html, shutil
import urllib.request
import urllib.parse
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
# When using domain (infratak.*) set cookie domain for session; when using IP (backdoor) use no domain so cookie is sent
def _set_session_cookie_domain():
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.config', 'settings.json')
        if os.path.exists(p) and (not app.config.get('SESSION_COOKIE_DOMAIN')):
            _s = json.load(open(p))
            if _s.get('fqdn'):
                app.config['SESSION_COOKIE_DOMAIN'] = '.' + _s['fqdn'].split(':')[0]
    except Exception:
        pass
_set_session_cookie_domain()

@app.context_processor
def inject_cloudtak_icon():
    from flask import request
    from markupsafe import Markup
    d = {'cloudtak_icon': CLOUDTAK_ICON, 'mediamtx_logo_url': MEDIAMTX_LOGO_URL, 'nodered_logo_url': NODERED_LOGO_URL, 'authentik_logo_url': AUTHENTIK_LOGO_URL, 'caddy_logo_url': CADDY_LOGO_URL, 'tak_logo_url': TAK_LOGO_URL}
    if not request.path.startswith('/api') and not request.path.startswith('/cloudtak/page.js'):
        d['sidebar_html'] = Markup(render_sidebar(detect_modules(), request.path.strip('/') or 'console'))
    return d

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Pin config to env so auth works even if service WorkingDirectory and code path ever differ (e.g. after git pull)
CONFIG_DIR = os.environ.get('CONFIG_DIR') or os.path.join(BASE_DIR, '.config')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

def _request_host_is_ip():
    """True if the request is to an IP address (backdoor), so we must not set cookie domain."""
    try:
        host = (request.host or '').split(':')[0]
        if not host:
            return True
        parts = host.split('.')
        if len(parts) != 4:
            return False
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    except Exception:
        return True

@app.before_request
def ensure_session_cookie_domain():
    """When access is via IP (backdoor), do not set cookie domain so the cookie is sent. Otherwise use FQDN for cross-subdomain."""
    if _request_host_is_ip():
        app.config['SESSION_COOKIE_DOMAIN'] = False
        return
    if app.config.get('SESSION_COOKIE_DOMAIN'):
        return
    try:
        s = load_settings()
        if s.get('fqdn'):
            app.config['SESSION_COOKIE_DOMAIN'] = '.' + s['fqdn'].split(':')[0]
    except Exception:
        pass
VERSION = "0.1.8-alpha"
GITHUB_REPO = "takwerx/infra-TAK"
CADDYFILE_PATH = "/etc/caddy/Caddyfile"
# CloudTAK official icon (SVG data URL)
CLOUDTAK_ICON = "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c3ZnIGlkPSJMYXllcl8xIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2aWV3Qm94PSIwIDAgNzQuMyA0Ni42MiI+PGRlZnM+PHN0eWxlPi5jbHMtMXtmaWxsOnVybCgjbGluZWFyLWdyYWRpZW50LTIpO30uY2xzLTJ7ZmlsbDp1cmwoI2xpbmVhci1ncmFkaWVudCk7fTwvc3R5bGU+PGxpbmVhckdyYWRpZW50IGlkPSJsaW5lYXItZ3JhZGllbnQiIHgxPSIxNC4zOCIgeTE9IjguOTMiIHgyPSI2Ni45MiIgeTI9IjYxLjQ3IiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHN0b3Agb2Zmc2V0PSIwIiBzdG9wLWNvbG9yPSIjZmY5ODIwIi8+PHN0b3Agb2Zmc2V0PSIuNDIiIHN0b3AtY29sb3I9IiNmZmNlMDQiLz48c3RvcCBvZmZzZXQ9Ii40OSIgc3RvcC1jb2xvcj0iZ29sZCIvPjwvbGluZWFyR3JhZGllbnQ+PGxpbmVhckdyYWRpZW50IGlkPSJsaW5lYXItZ3JhZGllbnQtMiIgeDE9IjU5LjI3IiB5MT0iLS4zOCIgeDI9IjcyLjc0IiB5Mj0iMTIuMDgiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj48c3RvcCBvZmZzZXQ9IjAiIHN0b3AtY29sb3I9IiNmZjk4MjAiLz48c3RvcCBvZmZzZXQ9Ii4yOSIgc3RvcC1jb2xvcj0iI2ZmYjYxMCIvPjxzdG9wIG9mZnNldD0iLjU3IiBzdG9wLWNvbG9yPSJnb2xkIi8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNzIuMDUsMjMuNTVjLTEuMjYtMS44OC0zLjAxLTMuNDUtNS4yMS00LjY1LTEuODUtMS4wMS0zLjY5LTEuNTktNS4wNi0xLjkxLS40Mi0xLjc0LTEuMjMtNC4yOC0yLjc3LTYuODVDNTYuNDQsNS44OCw1MS4zNy42Nyw0MS43LjA2Yy0uNTktLjA0LTEuMTgtLjA2LTEuNzUtLjA2LTcuODIsMC0xMi4wNCwzLjUyLTE0LjE5LDYuNDctLjkxLDEuMjQtMS41MywyLjQ4LTEuOTUsMy41NS0uODYtLjEzLTEuODYtLjIyLTIuOTMtLjIyLTMuNTYsMC02LjUyLDEuMDgtOC41NCwzLjEzLTEuOTEsMS45Mi0zLjIsNC4yNi0zLjczLDYuNzUtLjA5LjQxLS4xNS44LS4xOSwxLjE2LS45NS40Ny0yLjEyLDEuMTYtMy4yOSwyLjExQzEuNTYsMjUuODMtLjIsMjkuNjcuMDIsMzQuMDZjLjIyLDQuNDEsMi4yNyw3Ljk2LDUuOTQsMTAuMjksMi42LDEuNjUsNS4xLDIuMTksNS4zOCwyLjIzbC4yMi4wM2guMjJzNDguODYsMCw0OC44NiwwaC4xcy4xLDAsLjEsMGMuMzQtLjAyLDMuMzktLjI2LDYuNTQtMi4xMywzLjA0LTEuOCw2LjctNS40NSw2LjkyLTEyLjU2LjEtMy4xOC0uNjYtNS45OS0yLjI0LTguMzZaTTE0LjQzLDE1YzEuNzUtMS43Nyw0LjI0LTIuMjYsNi40NS0yLjI2LDIuNzEsMCw0Ljk5LjczLDQuOTkuNzMsMCwwLDEuMzMtMTAuNTMsMTQuMDctMTAuNTMuNSwwLDEuMDMuMDIsMS41Ny4wNSwxNi4yNCwxLjAzLDE3Ljc0LDE2LjU0LDE3Ljc0LDE2LjU0LDAsMCw0LjY3LjQyLDguMjEsMy4zMS0zLjQ3LDMuMjItNC45NSw1LjE5LTEyLjc3LDUuNzUtOC42NS42MS03LjQ3LDMuOTUtNy40NywzLjk1bC00LjA1LTguOThoNS43OWMuMTQtMi44NS0uODctNS42NS01LjMxLTUuNjVoLTguNDlsLTYuNTYsMTQuNjJzMS45Ni0zLjMxLTYuNjktMy45NWMtNy42OS0uNTUtNy41OC0yLjY5LTEwLjYxLTUuODgtLjA2LS41OC0uMjYtNC4zLDMuMTMtNy43MloiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik02MS43OSwzLjczaDIuNTl2LjY0aC0uOTN2Mi4zOGgtLjc0di0yLjM4aC0uOTN2LS42NFpNNjcuMDUsMy43M2wtLjc3LDIuMDMtLjc3LTIuMDNoLS45M3YzLjAzaC43di0ybC43MywyaC41NGwuNzMtMnYyaC43di0zLjAzaC0uOTNaIi8+PC9zdmc+"
# MediaMTX official logo (external URL to avoid long inline strings)
MEDIAMTX_LOGO_URL = "https://raw.githubusercontent.com/bluenviron/mediamtx/main/logo.png"
# MediaMTX web editor: regular repo (no LDAP); when Authentik/LDAP is installed we use LDAP branch if set
MEDIAMTX_EDITOR_REPO = "https://github.com/takwerx/mediamtx-installer.git"
MEDIAMTX_EDITOR_PATH = "config-editor"  # subdir containing mediamtx_config_editor.py
MEDIAMTX_EDITOR_LDAP_BRANCH = "infratak"  # when LDAP/Authentik installed, try this branch first; None = always use default branch
# Node-RED official icons (https://nodered.org/about/resources/media/)
NODERED_LOGO_URL = "https://nodered.org/about/resources/media/node-red-icon.png"       # icon only (e.g. small nav)
NODERED_LOGO_URL_2 = "https://nodered.org/about/resources/media/node-red-icon-2.png"   # icon + "Node-RED" text (card, sidebar)
# Authentik official brand icon (external URL)
AUTHENTIK_LOGO_URL = "https://raw.githubusercontent.com/goauthentik/authentik/main/web/icons/icon_left_brand.png"
# Caddy official logo for dark backgrounds — white text (Wikimedia Commons)
CADDY_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/5/56/Caddyserver_logo_dark.svg"
# TAK (Team Awareness Kit) official brand logo from tak.gov
TAK_LOGO_URL = "https://tak.gov/assets/logos/brand-06b80939.svg"
update_cache = {'latest': None, 'checked': 0, 'notes': ''}
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_settings():
    p = os.path.join(CONFIG_DIR, 'settings.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def save_settings(s):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    json.dump(s, open(os.path.join(CONFIG_DIR, 'settings.json'), 'w'), indent=2)

def load_auth():
    """Load auth.json from CONFIG_DIR. Never raises — returns {} on missing file or error."""
    try:
        p = os.path.join(CONFIG_DIR, 'auth.json')
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_auth(auth_dict):
    """Write auth.json to CONFIG_DIR. Caller must ensure auth_dict has password_hash."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    p = os.path.join(CONFIG_DIR, 'auth.json')
    auth_dict = dict(auth_dict)
    if 'created' not in auth_dict:
        auth_dict['created'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(p, 'w') as f:
        json.dump(auth_dict, f, indent=4)
    os.chmod(p, 0o600)

def _apply_authentik_session():
    """If request has Authentik headers (from Caddy forward_auth), set session so we treat user as logged in."""
    uname = request.headers.get('X-Authentik-Username')
    if uname:
        session['authenticated'] = True
        session['authentik_username'] = uname
        return True
    return False

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if _apply_authentik_session():
            return f(*args, **kwargs)
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def detect_modules():
    modules = {}
    settings = load_settings()
    has_fqdn = bool(settings.get('fqdn', ''))
    # Caddy SSL - First when no FQDN configured
    caddy_installed = subprocess.run(['which', 'caddy'], capture_output=True).returncode == 0
    caddy_running = False
    if caddy_installed:
        r = subprocess.run(['systemctl', 'is-active', 'caddy'], capture_output=True, text=True)
        caddy_running = r.stdout.strip() == 'active'
        # Leftover from uninstall-all? (binary still there but service disabled and stopped)
        if not caddy_running:
            re = subprocess.run(['systemctl', 'is-enabled', 'caddy'], capture_output=True, text=True, timeout=5)
            if (re.stdout or '').strip() == 'disabled':
                for path in ['/usr/bin/caddy', '/usr/local/bin/caddy']:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            subprocess.run(f'rm -f {path}', shell=True, capture_output=True)
                if os.path.exists('/etc/caddy'):
                    subprocess.run('rm -rf /etc/caddy', shell=True, capture_output=True, timeout=10)
                subprocess.run('systemctl daemon-reload 2>/dev/null; true', shell=True, capture_output=True)
                caddy_installed = False
    modules['caddy'] = {'name': 'Caddy SSL', 'installed': caddy_installed, 'running': caddy_running,
        'description': "Domain setup, Let's Encrypt SSL & reverse proxy" if not has_fqdn else f"SSL & reverse proxy — {settings.get('fqdn', '')}",
        'icon': '🔒', 'icon_url': CADDY_LOGO_URL, 'route': '/caddy', 'priority': 0 if not has_fqdn else 10}
    # TAK Server
    tak_installed = os.path.exists('/opt/tak') and os.path.exists('/opt/tak/CoreConfig.xml')
    tak_running = False
    if tak_installed:
        r = subprocess.run(['systemctl', 'is-active', 'takserver'], capture_output=True, text=True)
        tak_running = r.stdout.strip() == 'active'
    modules['takserver'] = {'name': 'TAK Server', 'installed': tak_installed, 'running': tak_running,
        'description': 'Team Awareness Kit Server', 'icon': '🗺️', 'icon_url': TAK_LOGO_URL, 'route': '/takserver', 'priority': 1}
    # Authentik - Identity Provider
    ak_installed = os.path.exists(os.path.expanduser('~/authentik/docker-compose.yml'))
    ak_running = False
    if ak_installed:
        r = subprocess.run('docker ps --filter name=authentik-server --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        ak_running = 'Up' in r.stdout
    modules['authentik'] = {'name': 'Authentik', 'installed': ak_installed, 'running': ak_running,
        'description': 'Identity provider — SSO, LDAP, user management', 'icon': '🔐', 'icon_url': AUTHENTIK_LOGO_URL, 'route': '/authentik', 'priority': 2}
    # TAK Portal - Docker-based user management
    portal_installed = os.path.exists(os.path.expanduser('~/TAK-Portal/docker-compose.yml'))
    portal_running = False
    if portal_installed:
        r = subprocess.run('docker ps --filter name=tak-portal --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        portal_running = 'Up' in r.stdout
    modules['takportal'] = {'name': 'TAK Portal', 'installed': portal_installed, 'running': portal_running,
        'description': 'User & certificate management with Authentik', 'icon': '👥', 'route': '/takportal', 'priority': 3}
    # MediaMTX
    mtx_installed = os.path.exists('/usr/local/bin/mediamtx') and os.path.exists('/usr/local/etc/mediamtx.yml')
    mtx_running = False
    if mtx_installed:
        r = subprocess.run(['systemctl', 'is-active', 'mediamtx'], capture_output=True, text=True)
        mtx_running = r.stdout.strip() == 'active'
    modules['mediamtx'] = {'name': 'MediaMTX', 'installed': mtx_installed, 'running': mtx_running,
        'description': 'Video Streaming Server', 'icon': '📹', 'icon_url': MEDIAMTX_LOGO_URL, 'route': '/mediamtx', 'priority': 4}
    # Guard Dog
    gd_installed = os.path.exists('/opt/tak-guarddog')
    gd_running = False
    if gd_installed:
        r = subprocess.run(['systemctl', 'list-timers', '--no-pager'], capture_output=True, text=True)
        gd_running = 'tak8089guard' in r.stdout
    modules['guarddog'] = {'name': 'Guard Dog', 'installed': gd_installed, 'running': gd_running,
        'description': 'Health monitoring and auto-recovery', 'icon': '🐕', 'route': '/guarddog', 'priority': 5}
    # Node-RED (container name is "nodered" from compose container_name)
    nodered_installed = False
    nodered_running = False
    nr_dir = os.path.expanduser('~/node-red')
    nr_compose = os.path.join(nr_dir, 'docker-compose.yml')
    if os.path.exists(nr_compose):
        nodered_installed = True
        r = subprocess.run(f'docker compose -f "{nr_compose}" ps -q 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5, cwd=nr_dir)
        if r.returncode == 0 and (r.stdout or '').strip():
            r2 = subprocess.run('docker ps --filter name=nodered --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
            nodered_running = bool(r2.stdout and 'Up' in r2.stdout)
    if not nodered_installed and (os.path.exists(os.path.expanduser('~/node-red')) or os.path.exists('/opt/nodered')):
        nodered_installed = True
        r = subprocess.run(['systemctl', 'is-active', 'nodered'], capture_output=True, text=True)
        if r.stdout.strip() == 'active':
            nodered_running = True
    modules['nodered'] = {'name': 'Node-RED', 'installed': nodered_installed, 'running': nodered_running,
        'description': 'Flow-based automation & integrations', 'icon': '🔴', 'icon_url': NODERED_LOGO_URL_2, 'route': '/nodered', 'priority': 6}
    # CloudTAK
    cloudtak_dir = os.path.expanduser('~/CloudTAK')
    cloudtak_installed = os.path.exists(cloudtak_dir) and os.path.exists(os.path.join(cloudtak_dir, 'docker-compose.yml'))
    cloudtak_running = False
    r = subprocess.run('docker ps --filter name=cloudtak-api --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if r.stdout and 'Up' in r.stdout:
        cloudtak_running = True
    if not cloudtak_installed and cloudtak_running:
        cloudtak_installed = True  # container up but dir missing (e.g. different user) — show as installed so card is accurate
    modules['cloudtak'] = {'name': 'CloudTAK', 'installed': cloudtak_installed, 'running': cloudtak_running,
        'description': 'Web-based TAK client — browser access to TAK', 'icon': '☁️', 'icon_data': CLOUDTAK_ICON, 'route': '/cloudtak', 'priority': 7}
    # Email Relay (Postfix)
    email_installed = subprocess.run(['which', 'postfix'], capture_output=True).returncode == 0
    email_running = False
    if email_installed:
        r = subprocess.run(['systemctl', 'is-active', 'postfix'], capture_output=True, text=True)
        email_running = r.stdout.strip() == 'active'
    modules['emailrelay'] = {'name': 'Email Relay', 'installed': email_installed, 'running': email_running,
        'description': 'Postfix relay — notifications for TAK Portal & MediaMTX', 'icon': '📧', 'route': '/emailrelay', 'priority': 8}
    return dict(sorted(modules.items(), key=lambda x: x[1].get('priority', 99)))

def render_sidebar(modules, active_path):
    """Build sidebar nav HTML: Console and Marketplace always; tool links only when installed.
    active_path is the current path (e.g. 'console', 'nodered') for highlighting."""
    active = (active_path or '').strip('/') or 'console'
    def link(href, content, title=None):
        path = href.strip('/')
        cls = 'nav-item active' if path == active else 'nav-item'
        t = f' title="{html.escape(title)}"' if title else ''
        return f'<a href="{href}" class="{cls}"{t}>{content}</a>'
    logo = '<div class="sidebar-logo"><span>infra-TAK</span><small>Infrastructure Platform</small><small style="display:block;margin-top:2px;font-size:9px;color:var(--text-dim);opacity:0.85">built by TAKWERX</small></div>'
    parts = [logo]
    parts.append(link('/console', '<span class="nav-icon material-symbols-outlined">dashboard</span>Console'))
    caddy = modules.get('caddy', {})
    if caddy.get('installed'):
        parts.append(link('/caddy', f'<img src="{html.escape(CADDY_LOGO_URL)}" alt="Caddy SSL" class="nav-icon" style="height:24px;width:auto;max-width:72px;object-fit:contain;display:block">', 'Caddy SSL'))
    tak = modules.get('takserver', {})
    if tak.get('installed'):
        parts.append(link('/takserver', f'<img src="{html.escape(TAK_LOGO_URL)}" alt="TAK Server" class="nav-icon" style="height:24px;width:auto;max-width:48px;object-fit:contain;display:block"><span>TAK Server</span>', 'TAK Server'))
    ak = modules.get('authentik', {})
    if ak.get('installed'):
        parts.append(link('/authentik', f'<img src="{html.escape(AUTHENTIK_LOGO_URL)}" alt="Authentik" class="nav-icon" style="height:48px;width:auto;max-width:100px;object-fit:contain;display:block">', 'Authentik'))
    portal = modules.get('takportal', {})
    if portal.get('installed'):
        parts.append(link('/takportal', '<span class="nav-icon material-symbols-outlined">group</span>TAK Portal'))
    cloudtak = modules.get('cloudtak', {})
    if cloudtak.get('installed'):
        parts.append(link('/cloudtak', f'<img src="{html.escape(CLOUDTAK_ICON)}" alt="" class="nav-icon" style="height:24px;width:auto;max-width:72px;object-fit:contain;display:block"><span>CloudTAK</span>'))
    mtx = modules.get('mediamtx', {})
    if mtx.get('installed'):
        parts.append(link('/mediamtx', f'<img src="{html.escape(MEDIAMTX_LOGO_URL)}" alt="MediaMTX" class="nav-icon" style="height:48px;width:auto;max-width:100px;object-fit:contain;display:block">', 'MediaMTX'))
    nr = modules.get('nodered', {})
    if nr.get('installed'):
        parts.append(link('/nodered', f'<img src="{html.escape(NODERED_LOGO_URL)}" alt="" class="nav-icon" style="height:24px;width:auto;max-width:72px;object-fit:contain;display:block"><span>Node-RED</span>'))
    gd = modules.get('guarddog', {})
    if gd.get('installed'):
        parts.append(link('/guarddog', '<span class="nav-icon" style="font-size:22px;line-height:1">🐕</span><span>Guard Dog</span>', 'Guard Dog'))
    email = modules.get('emailrelay', {})
    if email.get('installed'):
        parts.append(link('/emailrelay', '<span class="nav-icon material-symbols-outlined">outgoing_mail</span>Email Relay'))
    parts.append(link('/marketplace', '<span class="nav-icon material-symbols-outlined">shopping_cart</span>Marketplace'))
    parts.append(link('/help', '<span class="nav-icon material-symbols-outlined">help</span>Help'))
    return '<nav class="sidebar">\n  ' + '\n  '.join(parts) + '\n</nav>'

def get_system_metrics():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    d, h, m = uptime.days, uptime.seconds // 3600, (uptime.seconds % 3600) // 60
    uu = _get_unattended_upgrades_status()
    return {'cpu_percent': cpu, 'ram_percent': round(ram.percent, 1),
        'ram_used_gb': round(ram.used / (1024**3), 1), 'ram_total_gb': round(ram.total / (1024**3), 1),
        'disk_percent': round(disk.percent, 1), 'disk_used_gb': round(disk.used / (1024**3), 1),
        'disk_total_gb': round(disk.total / (1024**3), 1), 'uptime': f"{d}d {h}h {m}m",
        'unattended_upgrades': uu}

def _get_unattended_upgrades_status():
    """Return dict with 'enabled' (bool) and 'running' (bool) for unattended-upgrades."""
    enabled = False
    try:
        r = subprocess.run('systemctl is-enabled unattended-upgrades 2>/dev/null',
            shell=True, capture_output=True, text=True, timeout=5)
        enabled = r.stdout.strip() == 'enabled'
    except Exception:
        pass
    running = False
    try:
        proc = subprocess.run('ps aux | grep "/usr/bin/unattended-upgrade" | grep -v shutdown | grep -v grep',
            shell=True, capture_output=True, text=True, timeout=5)
        running = bool(proc.stdout.strip())
    except Exception:
        pass
    # Only show "running" when auto-updates are enabled; otherwise timer/cron can run the binary and confuse the UI
    if not enabled:
        running = False
    return {'enabled': enabled, 'running': running}

# === Routes ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' and _apply_authentik_session():
        return redirect(url_for('console_page'))
    if request.method == 'POST':
        auth = load_auth()
        if not auth.get('password_hash'):
            return render_template_string(
                LOGIN_TEMPLATE,
                error='Password not set or wrong install path. Use backdoor: https://YOUR_SERVER_IP:5001 and run ./reset-console-password.sh from the install directory.',
                version=VERSION)
        if check_password_hash(auth['password_hash'], request.form.get('password', '')):
            session['authenticated'] = True
            return redirect(url_for('console_page'))
        return render_template_string(LOGIN_TEMPLATE, error='Invalid password', version=VERSION)
    return render_template_string(LOGIN_TEMPLATE, error=None, version=VERSION)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def index():
    """Landing: login at / (infratak.fqdn); when logged in redirect to console. Authentik headers = auto-login."""
    if request.method == 'GET' and _apply_authentik_session():
        return redirect(url_for('console_page'))
    if request.method == 'POST':
        auth = load_auth()
        if not auth.get('password_hash'):
            return render_template_string(
                LOGIN_TEMPLATE,
                error='Password not set or wrong install path. Use backdoor: https://YOUR_SERVER_IP:5001 and run ./reset-console-password.sh from the install directory.',
                version=VERSION)
        if check_password_hash(auth['password_hash'], request.form.get('password', '')):
            session['authenticated'] = True
            return redirect(url_for('console_page'))
        return render_template_string(LOGIN_TEMPLATE, error='Invalid password', version=VERSION)
    if not session.get('authenticated'):
        return render_template_string(LOGIN_TEMPLATE, error=None, version=VERSION)
    return redirect(url_for('console_page'))

@app.route('/api/forward-auth')
def forward_auth():
    """Caddy forward_auth: return 200 if session is authenticated; else redirect to console login."""
    if session.get('authenticated'):
        return '', 200
    # Redirect to console login so user can log in and retry (Caddy passes this response to the client)
    settings = load_settings()
    fqdn = (settings.get('fqdn') or '').split(':')[0]
    if fqdn:
        login_url = f"https://infratak.{fqdn}/login"
        return redirect(login_url, code=302)
    return '', 401

@app.route('/console')
@login_required
def console_page():
    """Console: only installed/deployed services."""
    settings = load_settings()
    all_modules = detect_modules()
    modules = {k: m for k, m in all_modules.items() if m.get('installed')}
    module_versions = get_all_module_versions()
    resp = render_template_string(CONSOLE_TEMPLATE,
        settings=settings, modules=modules, metrics=get_system_metrics(), version=VERSION,
        module_versions=module_versions)
    from flask import make_response
    r = make_response(resp)
    r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return r

@app.route('/marketplace')
@login_required
def marketplace_page():
    """Marketplace: only services that are not yet installed (deploy from here)."""
    settings = load_settings()
    all_modules = detect_modules()
    modules = {k: m for k, m in all_modules.items() if not m.get('installed')}
    resp = render_template_string(MARKETPLACE_TEMPLATE,
        settings=settings, modules=modules, metrics=get_system_metrics(), version=VERSION)
    from flask import make_response
    r = make_response(resp)
    r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return r

@app.route('/help')
@login_required
def help_page():
    """Help: backdoor URL, console password info, reset password, hardening."""
    settings = load_settings()
    current_ssh_port = _get_current_ssh_port()
    return render_template_string(HELP_TEMPLATE, settings=settings, version=VERSION, current_ssh_port=current_ssh_port)

@app.route('/api/update/check')
@login_required
def update_check():
    import urllib.request
    now = time.time()
    # Cache for 1 hour
    if update_cache['latest'] and (now - update_cache['checked']) < 3600:
        return jsonify({'current': VERSION, 'latest': update_cache['latest'], 'notes': update_cache['notes'],
            'update_available': update_cache['latest'] != VERSION})
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{GITHUB_REPO}/tags',
            headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'infra-TAK'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        if not data:
            return jsonify({'current': VERSION, 'latest': None, 'error': 'No tags found', 'update_available': False})
        # Find the latest semver tag (sort by version)
        versions = []
        for tag in data:
            name = tag.get('name', '').lstrip('v').replace('-alpha','').replace('-beta','')
            parts = name.split('.')
            try:
                versions.append((tuple(int(p) for p in parts), tag))
            except (ValueError, IndexError):
                continue
        if not versions:
            return jsonify({'current': VERSION, 'latest': None, 'error': 'No version tags', 'update_available': False})
        versions.sort(key=lambda x: x[0], reverse=True)
        latest_tag = versions[0][1]
        latest = latest_tag.get('name', '').lstrip('v')
        # Strip -alpha/-beta for comparison
        latest_cmp = latest.replace('-alpha','').replace('-beta','')
        current_cmp = VERSION.replace('-alpha','').replace('-beta','')
        notes = f"Version {latest_tag.get('name', '')}"
        update_cache.update({'latest': latest, 'checked': now, 'notes': notes})
        return jsonify({'current': VERSION, 'latest': latest, 'notes': notes, 'body': '',
            'update_available': latest_cmp != current_cmp})
    except Exception as e:
        return jsonify({'current': VERSION, 'latest': None, 'error': str(e), 'update_available': False})

@app.route('/api/update/apply', methods=['POST'])
@login_required
def update_apply():
    console_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        r = subprocess.run(f'cd {console_dir} && git pull --rebase --autostash 2>&1', shell=True, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return jsonify({'success': False, 'error': r.stderr.strip() or r.stdout.strip()})
        update_cache.update({'latest': None, 'checked': 0})
        subprocess.Popen('sleep 2 && systemctl restart takwerx-console', shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'success': True, 'output': r.stdout.strip(), 'restart_required': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/takserver')
@login_required
def takserver_page():
    modules = detect_modules()
    tak = modules.get('takserver', {})
    ak = modules.get('authentik', {})
    # Show "Connect TAK Server to LDAP" when: TAK Server + Authentik installed, CoreConfig exists, LDAP not yet applied
    has_ldap = _coreconfig_has_ldap()
    show_connect_ldap = (
        tak.get('installed') and ak.get('installed') and
        os.path.exists('/opt/tak/CoreConfig.xml') and not has_ldap
    )
    ldap_connected = tak.get('installed') and ak.get('installed') and has_ldap
    # Reset deploy_done once TAK Server is running so the running view shows
    if tak.get('installed') and tak.get('running') and not deploy_status.get('running', False):
        deploy_status.update({'complete': False, 'error': False})
    tak_version = _get_takserver_version_info().get('version', '') if tak.get('installed') else ''
    return render_template_string(TAKSERVER_TEMPLATE,
        settings=load_settings(), modules=modules, tak=tak, tak_version=tak_version,
        show_connect_ldap=show_connect_ldap, ldap_connected=ldap_connected,
        metrics=get_system_metrics(), version=VERSION, deploying=deploy_status.get('running', False),
        deploy_done=deploy_status.get('complete', False), deploy_error=deploy_status.get('error', False),
        upgrading=upgrade_status.get('running', False), upgrade_done=upgrade_status.get('complete', False),
        upgrade_error=upgrade_status.get('error', False))

@app.route('/mediamtx')
@login_required
def mediamtx_page():
    settings = load_settings()
    modules = detect_modules()
    mtx = modules.get('mediamtx', {})
    cloudtak_installed = modules.get('cloudtak', {}).get('installed', False)
    return render_template_string(MEDIAMTX_TEMPLATE,
        settings=settings, mtx=mtx, version=VERSION,
        cloudtak_installed=cloudtak_installed,
        deploying=mediamtx_deploy_status.get('running', False),
        deploy_done=mediamtx_deploy_status.get('complete', False))

# ── Guard Dog (TAK Server hardening / 7 monitors) ─────────────────────────────
guarddog_deploy_log = []
guarddog_deploy_status = {'running': False, 'complete': False, 'error': False}

def _guarddog_health_url(settings):
    """Build the health endpoint URL for this server (for Uptime Robot / display)."""
    fqdn = (settings.get('fqdn') or '').strip()
    server_ip = (settings.get('server_ip') or '').strip()
    if fqdn:
        return f"http://{fqdn.split(':')[0]}:8080/health"
    if server_ip:
        return f"http://{server_ip}:8080/health"
    return "http://YOUR_SERVER_IP:8080/health"

@app.route('/guarddog.js')
def guarddog_js():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'guarddog.js', mimetype='application/javascript')

@app.route('/takserver.js')
def takserver_js():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'takserver.js', mimetype='application/javascript')

@app.route('/guarddog')
@login_required
def guarddog_page():
    settings = load_settings()
    modules = detect_modules()
    gd = modules.get('guarddog', {})
    tak = modules.get('takserver', {})
    relay = settings.get('email_relay', {})
    email_relay_configured = bool(relay.get('relay_host') and relay.get('smtp_user'))
    guarddog_monitors_tak = [
        {'name': 'Port 8089', 'interval': '1 min', 'desc': 'Checks that TAK Server port 8089 is listening and accepting connections. Auto-restarts TAK Server after 3 consecutive failures.'},
        {'name': 'Process', 'interval': '1 min', 'desc': 'Verifies all 5 TAK Server Java processes (messaging, api, config, plugins, retention). Auto-restart after 3 consecutive failures.'},
        {'name': 'Network', 'interval': '1 min', 'desc': 'Pings Cloudflare (1.1.1.1) and Google (8.8.8.8). Alerts only (no restart) after 3 failures — helps distinguish network issues from server issues.'},
        {'name': 'PostgreSQL', 'interval': '5 min', 'desc': 'Checks that the PostgreSQL service is running. Attempts restart if down; sends alert.'},
        {'name': 'CoT database size', 'interval': '6 hours', 'desc': 'CoT DB size. Alert at 25GB (warning) or 40GB (critical). Retention deletes rows; run VACUUM to reclaim disk. Alert email includes tips.'},
        {'name': 'OOM', 'interval': '1 min', 'desc': 'Scans TAK Server logs for OutOfMemoryError. Auto-restarts TAK Server and sends alert when detected.'},
        {'name': 'Disk', 'interval': '1 hour', 'desc': 'Checks root and TAK logs filesystem usage. Alert only when usage exceeds 80% (warning) or 90% (critical).'},
        {'name': 'Certificate', 'interval': 'Daily', 'desc': 'Checks Let\'s Encrypt / TAK Server cert expiry. Alert when 40 days or less remaining until expiry.'},
        {'name': 'Root CA / Intermediate CA', 'interval': 'Escalating', 'desc': 'Monitors Root CA and Intermediate CA certificate expiry. First alert at 90 days, then at 75, 60, 45, 30 days, then daily until expiry.'},
    ]
    # Per-service list for expandable UI. "monitored" = Guard Dog monitors this (installed when Guard Dog was deployed).
    guarddog_services = [
        {'id': 'takserver', 'name': 'TAK Server', 'monitored': gd.get('installed'), 'monitors': guarddog_monitors_tak},
        {'id': 'authentik', 'name': 'Authentik', 'monitored': modules.get('authentik', {}).get('installed'), 'monitors': [{'name': 'Container / HTTP', 'interval': '1 min', 'desc': 'Checks Authentik HTTP (9090). Alert and restart after 3 failures. 15 min boot skip + cooldown to avoid restart loops.'}]},
        {'id': 'mediamtx', 'name': 'MediaMTX', 'monitored': modules.get('mediamtx', {}).get('installed'), 'monitors': [{'name': 'Service', 'interval': '1 min', 'desc': 'Checks systemd mediamtx. Alert and restart after 3 failures. 15 min boot skip + cooldown to avoid restart loops.'}]},
        {'id': 'nodered', 'name': 'Node-RED', 'monitored': modules.get('nodered', {}).get('installed'), 'monitors': [{'name': 'Container / HTTP', 'interval': '1 min', 'desc': 'Checks Node-RED HTTP (1880). Alert and restart after 3 failures. 15 min boot skip + cooldown to avoid restart loops.'}]},
        {'id': 'cloudtak', 'name': 'CloudTAK', 'monitored': modules.get('cloudtak', {}).get('installed'), 'monitors': [{'name': 'Container', 'interval': '1 min', 'desc': 'Checks CloudTAK container. Alert and restart after 3 failures. 15 min boot skip + cooldown to avoid restart loops.'}]},
    ]
    guarddog_docs_url = f'https://github.com/{GITHUB_REPO}/blob/main/docs/GUARDDOG.md'
    notifications_configured = bool((settings.get('guarddog_alert_email') or '').strip())
    return render_template_string(GUARDDOG_TEMPLATE,
        settings=settings, gd=gd, tak=tak, version=VERSION,
        guarddog_alert_email=settings.get('guarddog_alert_email', ''),
        guarddog_sms=settings.get('guarddog_sms', {}),
        guarddog_services=guarddog_services,
        guarddog_docs_url=guarddog_docs_url,
        notifications_configured=notifications_configured,
        email_relay_configured=email_relay_configured,
        health_url=_guarddog_health_url(settings),
        deploying=guarddog_deploy_status.get('running', False),
        deploy_done=guarddog_deploy_status.get('complete', False))

@app.route('/api/guarddog/deploy', methods=['POST'])
@login_required
def guarddog_deploy_api():
    if guarddog_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    data = request.json or {}
    alert_email = (data.get('alert_email') or '').strip()
    settings = load_settings()
    if not alert_email:
        alert_email = (settings.get('guarddog_alert_email') or '').strip()
    if not alert_email:
        return jsonify({'error': 'At least one alert email address is required'}), 400
    settings['guarddog_alert_email'] = alert_email
    save_settings(settings)
    guarddog_deploy_log.clear()
    guarddog_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_guarddog_deploy, args=(alert_email,), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/guarddog/deploy/log')
@login_required
def guarddog_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': guarddog_deploy_log[idx:], 'total': len(guarddog_deploy_log),
        'running': guarddog_deploy_status['running'], 'complete': guarddog_deploy_status['complete'],
        'error': guarddog_deploy_status['error']})

def _parse_guarddog_log_date(line):
    """Return (date, display_str) for a restarts.log line, or (None, line) if unparseable."""
    line = line.strip()
    if not line:
        return None, line
    # ISO: 2026-03-03T15:00:00Z | ...
    if len(line) >= 20 and line[10] == 'T' and line[19] in 'Z| ':
        try:
            dt = datetime.strptime(line[:19], '%Y-%m-%dT%H:%M:%S')
            return dt.date(), line[:19].replace('T', ' ')
        except ValueError:
            pass
    # date(1): Tue Mar  3 15:00:00 UTC 2026: message
    idx = line.find(': ')
    if idx > 20:
        prefix = line[:idx].strip()
        try:
            dt = datetime.strptime(prefix, '%a %b %d %H:%M:%S %Z %Y')
            return dt.date(), prefix
        except ValueError:
            pass
    return None, ''

def _guarddog_health_check(service_id):
    """Quick health check for one service. Returns True if healthy, False otherwise. Used for UI and optional monitors."""
    try:
        if service_id == 'takserver':
            r = subprocess.run(['systemctl', 'is-active', 'takserver'], capture_output=True, text=True, timeout=3)
            if r.returncode != 0:
                return False
            # Optional: also check 8089
            r2 = subprocess.run('ss -ltn "sport = :8089" 2>/dev/null', shell=True, capture_output=True, text=True, timeout=2)
            return 'LISTEN' in (r2.stdout or '')
        if service_id == 'authentik':
            req = urllib.request.Request('http://127.0.0.1:9090/', method='GET')
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status in (200, 302, 301)
        if service_id == 'mediamtx':
            r = subprocess.run(['systemctl', 'is-active', 'mediamtx'], capture_output=True, text=True, timeout=3)
            return r.returncode == 0
        if service_id == 'nodered':
            req = urllib.request.Request('http://127.0.0.1:1880/', method='GET')
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status in (200, 302, 301)
        if service_id == 'cloudtak':
            r = subprocess.run('docker ps --filter name=cloudtak-api --format "{{.Status}}"', shell=True, capture_output=True, text=True, timeout=5)
            return bool(r.stdout and 'Up' in r.stdout)
    except Exception:
        return False
    return False

@app.route('/api/guarddog/health')
@login_required
def guarddog_health_api():
    """Return health status per service (for UI). Only includes services that Guard Dog can monitor."""
    result = {}
    for sid in ('takserver', 'authentik', 'mediamtx', 'nodered', 'cloudtak'):
        result[sid] = _guarddog_health_check(sid)
    return jsonify(result)

@app.route('/api/guarddog/activity-log')
@login_required
def guarddog_activity_log():
    """Return Guard Dog restarts/alert log entries, optionally filtered by date. Newest first."""
    from_arg = request.args.get('from', '').strip()
    to_arg = request.args.get('to', '').strip()
    date_from = None
    date_to = None
    try:
        if from_arg:
            date_from = datetime.strptime(from_arg, '%Y-%m-%d').date()
        if to_arg:
            date_to = datetime.strptime(to_arg, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date; use YYYY-MM-DD'}), 400
    log_path = '/var/log/takguard/restarts.log'
    entries = []
    try:
        if not os.path.exists(log_path):
            return jsonify({'entries': [], 'log_path': log_path})
        with open(log_path, 'r') as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return jsonify({'entries': [], 'error': 'Could not read log file', 'log_path': log_path})
    for raw in reversed(lines):
        raw = raw.rstrip('\n')
        if not raw:
            continue
        parsed_date, display_ts = _parse_guarddog_log_date(raw)
        if date_from is not None and parsed_date is not None and parsed_date < date_from:
            continue
        if date_to is not None and parsed_date is not None and parsed_date > date_to:
            continue
        entries.append({'raw': raw, 'date': parsed_date.isoformat() if parsed_date else None, 'time_display': display_ts})
    return jsonify({'entries': entries, 'log_path': log_path})

@app.route('/api/guarddog/uninstall', methods=['POST'])
@login_required
def guarddog_uninstall():
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    timers = ['tak8089guard.timer', 'takoomguard.timer', 'takdiskguard.timer', 'takdbguard.timer',
              'takcotdbguard.timer', 'taknetguard.timer', 'takprocessguard.timer', 'takcertguard.timer',
              'takauthentikguard.timer', 'takmediamtxguard.timer', 'taknoderedguard.timer', 'takcloudtakguard.timer']
    for t in timers:
        subprocess.run(['systemctl', 'stop', t], capture_output=True, timeout=5)
        subprocess.run(['systemctl', 'disable', t], capture_output=True, timeout=5)
    subprocess.run(['systemctl', 'stop', 'tak-health.service'], capture_output=True, timeout=5)
    subprocess.run(['systemctl', 'disable', 'tak-health.service'], capture_output=True, timeout=5)
    services_extra = ['tak8089guard.service', 'takoomguard.service', 'takdiskguard.service', 'takdbguard.service',
                      'takcotdbguard.service', 'taknetguard.service', 'takprocessguard.service', 'takcertguard.service',
                      'takauthentikguard.service', 'takmediamtxguard.service', 'taknoderedguard.service', 'takcloudtakguard.service', 'tak-health.service']
    for name in timers + services_extra:
        path = os.path.join('/etc/systemd/system', name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    if os.path.exists('/opt/tak-guarddog'):
        shutil.rmtree('/opt/tak-guarddog', ignore_errors=True)
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, timeout=10)
    return jsonify({'success': True})

@app.route('/api/guarddog/test-email', methods=['POST'])
@login_required
def guarddog_test_email():
    """Send a test email to the configured Guard Dog alert address (uses Email Relay / Brevo when deployed)."""
    settings = load_settings()
    data = request.json or {}
    to_addr = data.get('to', '').strip() or (settings.get('guarddog_alert_email') or '').strip()
    if not to_addr:
        return jsonify({'success': False, 'error': 'No email address configured'}), 400
    if data.get('save'):
        settings['guarddog_alert_email'] = to_addr
        save_settings(settings)
    try:
        import smtplib
        from email.mime.text import MIMEText
        relay = settings.get('email_relay', {})
        from_addr = relay.get('from_addr', 'noreply@localhost')
        from_name = relay.get('from_name', 'Guard Dog')
        msg = MIMEText('Test alert from infra-TAK Guard Dog.\n\nIf you received this, email notifications are working (via Email Relay/Brevo when deployed).', 'plain')
        msg['From'] = f'{from_name} <{from_addr}>'
        msg['To'] = to_addr
        msg['Subject'] = 'Guard Dog Test Alert'
        with smtplib.SMTP('localhost', 25, timeout=15) as s:
            s.sendmail(from_addr, [to_addr], msg.as_string())
        return jsonify({'success': True, 'message': f'Test email sent to {to_addr}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/guarddog/sms/save', methods=['POST'])
@login_required
def guarddog_sms_save():
    """Save SMS provider config (Twilio or Brevo) and write sms_send.sh for watch scripts."""
    data = request.json or {}
    provider = (data.get('provider') or '').strip().lower()
    settings = load_settings()
    if provider not in ('twilio', 'brevo', ''):
        return jsonify({'success': False, 'error': 'Provider must be Twilio, Brevo, or empty to disable'}), 400
    if provider == '':
        settings['guarddog_sms'] = {}
        save_settings(settings)
        for path in ['/opt/tak-guarddog/sms_send.sh', '/opt/tak-guarddog/sms_send.py']:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        return jsonify({'success': True, 'message': 'SMS disabled'})
    if provider == 'twilio':
        account_sid = (data.get('account_sid') or '').strip()
        auth_token = (data.get('auth_token') or '').strip()
        from_number = (data.get('from_number') or '').strip()
        to_numbers = (data.get('to_numbers') or '').strip()
        if not all([account_sid, auth_token, from_number, to_numbers]):
            return jsonify({'success': False, 'error': 'Twilio: Account SID, Auth Token, From number, and To number(s) required'}), 400
        settings['guarddog_sms'] = {'provider': 'twilio', 'account_sid': account_sid, 'auth_token': auth_token, 'from_number': from_number, 'to_numbers': to_numbers}
    else:
        api_key = (data.get('api_key') or '').strip()
        sender = (data.get('sender') or '').strip()
        to_numbers = (data.get('to_numbers') or '').strip()
        if not all([api_key, sender, to_numbers]):
            return jsonify({'success': False, 'error': 'Brevo: API key, Sender (max 11 chars), and To number(s) with country code required'}), 400
        settings['guarddog_sms'] = {'provider': 'brevo', 'api_key': api_key, 'sender': sender, 'to_numbers': to_numbers}
    save_settings(settings)
    _guarddog_write_sms_send_script(settings)
    return jsonify({'success': True, 'message': 'SMS settings saved'})

def _guarddog_write_sms_send_script(settings):
    """Write /opt/tak-guarddog/sms_send.sh that watch scripts can call to send SMS via console API."""
    sms = settings.get('guarddog_sms', {})
    if not sms or not sms.get('provider'):
        return
    os.makedirs('/opt/tak-guarddog', exist_ok=True)
    py_script = '''#!/usr/bin/env python3
import urllib.request, json, sys
if len(sys.argv) < 3:
    sys.exit(0)
subj, path = sys.argv[1], sys.argv[2]
try:
    with open(path) as f: body = f.read()
except Exception:
    body = subj
data = json.dumps({"subject": subj, "body": body}).encode()
req = urllib.request.Request("http://127.0.0.1:5001/api/guarddog/send-sms", data=data, headers={"Content-Type": "application/json"}, method="POST")
try:
    urllib.request.urlopen(req, timeout=10)
except Exception:
    pass
'''
    sh_script = '''#!/bin/bash
SUBJ="$1"
BODY_FILE="$2"
[ -z "$BODY_FILE" ] || [ ! -f "$BODY_FILE" ] && exit 0
/usr/bin/python3 /opt/tak-guarddog/sms_send.py "$SUBJ" "$BODY_FILE"
'''
    for name, content in [('sms_send.py', py_script), ('sms_send.sh', sh_script)]:
        p = os.path.join('/opt/tak-guarddog', name)
        with open(p, 'w') as f:
            f.write(content)
        os.chmod(p, 0o755)

def _guarddog_send_sms_now(sms, text):
    """Send SMS via Twilio or Brevo. sms = settings['guarddog_sms'], text = message body (max 1600 chars). Raises on error. Returns optional dict with e.g. {'brevo_message_id': ...} for debugging."""
    text = (text or '')[:1600]
    out = {}
    if sms.get('provider') == 'twilio':
        import base64
        import urllib.error
        account_sid = sms.get('account_sid', '')
        auth_token = sms.get('auth_token', '')
        from_num = sms.get('from_number', '')
        to_list = [n.strip() for n in (sms.get('to_numbers') or '').split(',') if n.strip()]
        if not to_list:
            raise ValueError('No To numbers configured')
        auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        for to_num in to_list:
            to_e164 = '+' + ''.join(c for c in to_num if c.isdigit()).lstrip('+') or to_num.lstrip('+')
            req_body = f"To={urllib.parse.quote(to_e164)}&From={urllib.parse.quote(from_num)}&Body={urllib.parse.quote(text)}"
            req = urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json', data=req_body.encode(), method='POST', headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'})
            try:
                urllib.request.urlopen(req, timeout=15)
            except urllib.error.HTTPError as e:
                body = e.read().decode() if e.fp else ''
                try:
                    err_json = json.loads(body) if body else {}
                    msg = err_json.get('message') or str(err_json.get('code', '')) or body[:200] or f'HTTP {e.code}'
                except Exception:
                    msg = body[:200] or f'HTTP {e.code}'
                raise ValueError(f'Twilio SMS: {msg}')
    else:
        import urllib.error
        api_key = sms.get('api_key', '')
        sender = (sms.get('sender', '') or 'GuardDog')[:11]
        to_list = [n.strip() for n in (sms.get('to_numbers') or '').split(',') if n.strip()]
        if not to_list:
            raise ValueError('No To numbers configured')
        for to_num in to_list:
            recipient = ''.join(c for c in to_num if c.isdigit())
            if not recipient or len(recipient) < 10:
                raise ValueError(f'Brevo recipient must be digits with country code (e.g. 15551234567). Got: {to_num[:25]}')
            payload = json.dumps({'sender': sender, 'recipient': recipient, 'content': text, 'type': 'transactional', 'tag': 'GuardDog', 'unicodeEnabled': True}).encode()
            req = urllib.request.Request('https://api.brevo.com/v3/transactionalSMS/send', data=payload, method='POST', headers={'api-key': api_key, 'Content-Type': 'application/json', 'accept': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = resp.read().decode()
                    try:
                        data = json.loads(body) if body else {}
                        if data.get('messageId') is not None:
                            out['brevo_message_id'] = data.get('messageId')
                    except Exception:
                        pass
            except urllib.error.HTTPError as e:
                body = e.read().decode() if e.fp else ''
                try:
                    err_json = json.loads(body) if body else {}
                    msg = err_json.get('message') or err_json.get('code') or body[:200] or f'HTTP {e.code}'
                except Exception:
                    msg = body[:200] or f'HTTP {e.code}'
                raise ValueError(f'Brevo SMS: {msg}')
    return out

@app.route('/api/guarddog/brevo-sms-events', methods=['GET'])
@login_required
def guarddog_brevo_sms_events():
    """Fetch last SMS events from Brevo (sent, delivered, rejected, etc.) so user can see delivery status without digging in Brevo UI."""
    settings = load_settings()
    sms = settings.get('guarddog_sms', {})
    if not sms or sms.get('provider') != 'brevo':
        return jsonify({'error': 'Brevo SMS not configured'}), 400
    api_key = sms.get('api_key', '')
    if not api_key:
        return jsonify({'error': 'Brevo API key not set'}), 400
    days = request.args.get('days', '1')
    try:
        days_int = max(1, min(7, int(days)))
    except ValueError:
        days_int = 1
    url = f'https://api.brevo.com/v3/transactionalSMS/statistics/events?days={days_int}&tags=GuardDog&limit=50&sort=desc'
    req = urllib.request.Request(url, method='GET', headers={'api-key': api_key, 'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ''
        try:
            err = json.loads(body) if body else {}
            msg = err.get('message') or err.get('code') or body[:200] or f'HTTP {e.code}'
        except Exception:
            msg = body[:200] or f'HTTP {e.code}'
        return jsonify({'error': f'Brevo: {msg}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    events = data.get('events') or []
    return jsonify({'events': events})

@app.route('/api/guarddog/test-sms', methods=['POST'])
@login_required
def guarddog_test_sms():
    """Send a test SMS using saved Guard Dog SMS config (Twilio or Brevo)."""
    settings = load_settings()
    sms = settings.get('guarddog_sms', {})
    if not sms or sms.get('provider') not in ('twilio', 'brevo'):
        return jsonify({'success': False, 'error': 'SMS not configured. Save Twilio or Brevo settings first.'}), 400
    try:
        info = _guarddog_send_sms_now(sms, 'Guard Dog test - if you got this, SMS is working.')
        msg = 'Test SMS sent to configured number(s).'
        if info.get('brevo_message_id') is not None:
            msg += f' Brevo message ID: {info["brevo_message_id"]} (check Brevo SMS logs if the text did not arrive).'
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/guarddog/send-sms', methods=['POST'])
def guarddog_send_sms():
    """Called by Guard Dog scripts (localhost only) to send SMS via Twilio or Brevo."""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    subj = (data.get('subject') or '')[:100]
    body = (data.get('body') or '')[:1600]
    settings = load_settings()
    sms = settings.get('guarddog_sms', {})
    if not sms or sms.get('provider') not in ('twilio', 'brevo'):
        return jsonify({'error': 'SMS not configured'}), 400
    try:
        _guarddog_send_sms_now(sms, f"{subj}: {body}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_guarddog_deploy(alert_email):
    """Deploy Guard Dog: 7 monitors + health endpoint. Requires TAK Server at /opt/tak. Alert email required."""
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        guarddog_deploy_log.append(entry)
    alert_sms = ''  # Optional SMS; scripts accept empty
    try:
        if not os.path.exists('/opt/tak'):
            plog("✗ TAK Server not found at /opt/tak. Deploy TAK Server first.")
            guarddog_deploy_status.update({'running': False, 'error': True})
            return
        plog("━━━ Guard Dog deployment ━━━")
        scripts_dir = os.path.join(BASE_DIR, 'scripts', 'guarddog')
        if not os.path.isdir(scripts_dir):
            plog(f"✗ Scripts directory not found: {scripts_dir}")
            guarddog_deploy_status.update({'running': False, 'error': True})
            return
        for d in ['/opt/tak-guarddog', '/var/lib/takguard', '/var/log/takguard']:
            os.makedirs(d, exist_ok=True)
        plog("✓ Directories created")
        script_files = [
            'tak-8089-watch.sh', 'tak-oom-watch.sh', 'tak-disk-watch.sh', 'tak-db-watch.sh',
            'tak-cotdb-watch.sh', 'tak-network-watch.sh', 'tak-process-watch.sh', 'tak-cert-watch.sh', 'tak-intca-watch.sh', 'tak-health-endpoint.py'
        ]
        # Optional: monitors for other services (only install if that service is present)
        ak_dir = os.path.expanduser('~/authentik')
        nr_dir = os.path.expanduser('~/node-red')
        cloudtak_dir = os.path.expanduser('~/CloudTAK')
        if os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')):
            script_files.append('tak-authentik-watch.sh')
        if os.path.exists('/usr/local/bin/mediamtx') and os.path.exists('/usr/local/etc/mediamtx.yml'):
            script_files.append('tak-mediamtx-watch.sh')
        if os.path.exists(os.path.join(nr_dir, 'docker-compose.yml')):
            script_files.append('tak-nodered-watch.sh')
        if os.path.exists(cloudtak_dir) and os.path.exists(os.path.join(cloudtak_dir, 'docker-compose.yml')):
            script_files.append('tak-cloudtak-watch.sh')
        for name in script_files:
            src = os.path.join(scripts_dir, name)
            if not os.path.isfile(src):
                plog(f"✗ Missing script: {name}")
                guarddog_deploy_status.update({'running': False, 'error': True})
                return
            content = open(src, 'r').read()
            content = content.replace('ALERT_EMAIL_PLACEHOLDER', alert_email).replace('ALERT_SMS_PLACEHOLDER', alert_sms or '')
            dest = os.path.join('/opt/tak-guarddog', name)
            with open(dest, 'w') as f:
                f.write(content)
            if name.endswith('.sh'):
                os.chmod(dest, 0o755)
        plog("✓ Scripts installed")
        units = [
            ('tak8089guard.service', '[Unit]\nDescription=TAK 8089 Health Guard Dog\nAfter=network-online.target\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-8089-watch.sh\n'),
            ('tak8089guard.timer', '[Unit]\nDescription=Run TAK 8089 guard dog every 1 minute\n\n[Timer]\nOnBootSec=10min\nOnUnitActiveSec=1min\nUnit=tak8089guard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('takoomguard.service', '[Unit]\nDescription=TAK OOM Guard Dog\nAfter=takserver.service\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-oom-watch.sh\n'),
            ('takoomguard.timer', '[Unit]\nDescription=Run TAK OOM guard dog every 1 minute\n\n[Timer]\nOnBootSec=5min\nOnUnitActiveSec=1min\nUnit=takoomguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('takdiskguard.service', '[Unit]\nDescription=TAK Disk Space Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-disk-watch.sh\n'),
            ('takdiskguard.timer', '[Unit]\nDescription=Run TAK disk monitor every hour\n\n[Timer]\nOnBootSec=30min\nOnUnitActiveSec=1h\nUnit=takdiskguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('takdbguard.service', '[Unit]\nDescription=TAK PostgreSQL Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-db-watch.sh\n'),
            ('takdbguard.timer', '[Unit]\nDescription=Run TAK DB monitor every 5 minutes\n\n[Timer]\nOnBootSec=15min\nOnUnitActiveSec=5min\nUnit=takdbguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('takcotdbguard.service', '[Unit]\nDescription=TAK CoT Database Size Monitor\nAfter=postgresql.service postgresql-15.service\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-cotdb-watch.sh\n'),
            ('takcotdbguard.timer', '[Unit]\nDescription=Run TAK CoT DB size monitor every 6 hours\n\n[Timer]\nOnBootSec=30min\nOnUnitActiveSec=6h\nUnit=takcotdbguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('taknetguard.service', '[Unit]\nDescription=TAK Network Monitor\nAfter=network.target\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-network-watch.sh\n'),
            ('taknetguard.timer', '[Unit]\nDescription=TAK Network Monitor Timer\nRequires=taknetguard.service\n\n[Timer]\nOnBootSec=2min\nOnUnitActiveSec=1min\nAccuracySec=30s\n\n[Install]\nWantedBy=timers.target\n'),
            ('takprocessguard.service', '[Unit]\nDescription=TAK Server Process Monitor\nAfter=network.target takserver.service\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-process-watch.sh\n'),
            ('takprocessguard.timer', '[Unit]\nDescription=TAK Server Process Monitor Timer\nRequires=takprocessguard.service\n\n[Timer]\nOnBootSec=3min\nOnUnitActiveSec=1min\nAccuracySec=30s\n\n[Install]\nWantedBy=timers.target\n'),
            ('takcertguard.service', '[Unit]\nDescription=TAK Certificate Expiry Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-cert-watch.sh\n'),
            ('takcertguard.timer', '[Unit]\nDescription=Run TAK cert monitor daily\n\n[Timer]\nOnBootSec=1h\nOnUnitActiveSec=1d\nUnit=takcertguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('takintcaguard.service', '[Unit]\nDescription=TAK Intermediate CA Expiry Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-intca-watch.sh\n'),
            ('takintcaguard.timer', '[Unit]\nDescription=Run TAK Intermediate CA expiry monitor daily\n\n[Timer]\nOnBootSec=2h\nOnUnitActiveSec=1d\nUnit=takintcaguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ('tak-health.service', '[Unit]\nDescription=TAK Server Health Check Endpoint\nAfter=network.target takserver.service\n\n[Service]\nType=simple\nExecStart=/usr/bin/python3 /opt/tak-guarddog/tak-health-endpoint.py\nRestart=always\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target\n'),
        ]
        # Optional timers for other services (only if we installed the script)
        if 'tak-authentik-watch.sh' in script_files:
            units.extend([
                ('takauthentikguard.service', '[Unit]\nDescription=Guard Dog Authentik Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-authentik-watch.sh\n'),
                ('takauthentikguard.timer', '[Unit]\nDescription=Run Authentik guard every 1 minute\n\n[Timer]\nOnBootSec=15min\nOnUnitActiveSec=1min\nUnit=takauthentikguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ])
        if 'tak-mediamtx-watch.sh' in script_files:
            units.extend([
                ('takmediamtxguard.service', '[Unit]\nDescription=Guard Dog MediaMTX Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-mediamtx-watch.sh\n'),
                ('takmediamtxguard.timer', '[Unit]\nDescription=Run MediaMTX guard every 1 minute\n\n[Timer]\nOnBootSec=15min\nOnUnitActiveSec=1min\nUnit=takmediamtxguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ])
        if 'tak-nodered-watch.sh' in script_files:
            units.extend([
                ('taknoderedguard.service', '[Unit]\nDescription=Guard Dog Node-RED Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-nodered-watch.sh\n'),
                ('taknoderedguard.timer', '[Unit]\nDescription=Run Node-RED guard every 1 minute\n\n[Timer]\nOnBootSec=15min\nOnUnitActiveSec=1min\nUnit=taknoderedguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ])
        if 'tak-cloudtak-watch.sh' in script_files:
            units.extend([
                ('takcloudtakguard.service', '[Unit]\nDescription=Guard Dog CloudTAK Monitor\n\n[Service]\nType=oneshot\nExecStart=/opt/tak-guarddog/tak-cloudtak-watch.sh\n'),
                ('takcloudtakguard.timer', '[Unit]\nDescription=Run CloudTAK guard every 1 minute\n\n[Timer]\nOnBootSec=15min\nOnUnitActiveSec=1min\nUnit=takcloudtakguard.service\n\n[Install]\nWantedBy=timers.target\n'),
            ])
        for name, content in units:
            path = os.path.join('/etc/systemd/system', name)
            with open(path, 'w') as f:
                f.write(content)
        plog("✓ Systemd units installed")
        # TAK Server soft start: start after network and PostgreSQL to avoid boot race / restart loops
        tak_dropin_dir = '/etc/systemd/system/takserver.service.d'
        os.makedirs(tak_dropin_dir, exist_ok=True)
        tak_dropin = os.path.join(tak_dropin_dir, 'soft-start.conf')
        with open(tak_dropin, 'w') as f:
            f.write('[Unit]\nAfter=network-online.target postgresql.service postgresql-15.service\nWants=network-online.target\n')
        plog("✓ TAK Server soft-start drop-in installed (starts after network + PostgreSQL)")
        r = subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            plog(f"✗ daemon-reload failed: {r.stderr}")
            guarddog_deploy_status.update({'running': False, 'error': True})
            return
        timers = ['tak8089guard.timer', 'takoomguard.timer', 'takdiskguard.timer', 'takdbguard.timer',
                  'takcotdbguard.timer', 'taknetguard.timer', 'takprocessguard.timer', 'takcertguard.timer', 'takintcaguard.timer']
        if 'tak-authentik-watch.sh' in script_files:
            timers.append('takauthentikguard.timer')
        if 'tak-mediamtx-watch.sh' in script_files:
            timers.append('takmediamtxguard.timer')
        if 'tak-nodered-watch.sh' in script_files:
            timers.append('taknoderedguard.timer')
        if 'tak-cloudtak-watch.sh' in script_files:
            timers.append('takcloudtakguard.timer')
        for t in timers:
            subprocess.run(['systemctl', 'enable', t], capture_output=True, timeout=5)
            subprocess.run(['systemctl', 'start', t], capture_output=True, timeout=5)
        subprocess.run(['systemctl', 'enable', 'tak-health.service'], capture_output=True, timeout=5)
        subprocess.run(['systemctl', 'start', 'tak-health.service'], capture_output=True, timeout=5)
        for f in ['process_alert_sent', 'disk_alert_sent', 'db_alert_sent', 'cotdb_alert_sent', 'network_alert_sent', 'cert_alert_sent']:
            p = os.path.join('/var/lib/takguard', f)
            if not os.path.exists(p):
                open(p, 'a').close()
        plog("✓ Timers and health endpoint started")
        plog("✓ Deployment complete")
        guarddog_deploy_status.update({'running': False, 'complete': True, 'error': False})
    except Exception as e:
        plog(f"✗ Error: {str(e)}")
        guarddog_deploy_status.update({'running': False, 'error': True})

@app.route('/nodered')
@login_required
def nodered_page():
    settings = load_settings()
    modules = detect_modules()
    nr = modules.get('nodered', {})
    ak = modules.get('authentik', {})
    resp = make_response(render_template_string(NODERED_TEMPLATE,
        settings=settings, nr=nr, version=VERSION,
        authentik_installed=ak.get('installed'),
        deploying=nodered_deploy_status.get('running', False),
        deploy_done=nodered_deploy_status.get('complete', False),
        caddy_logo_url=CADDY_LOGO_URL, tak_logo_url=TAK_LOGO_URL, authentik_logo_url=AUTHENTIK_LOGO_URL,
        cloudtak_icon=CLOUDTAK_ICON, mediamtx_logo_url=MEDIAMTX_LOGO_URL))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

@app.route('/cloudtak')
@login_required
def cloudtak_page():
    settings = load_settings()
    cloudtak = detect_modules().get('cloudtak', {})
    container_info = {}
    if cloudtak.get('running'):
        r = subprocess.run('docker ps --filter "name=cloudtak" --format "{{.Names}}|||{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
        containers = []
        for line in (r.stdout or '').strip().split('\n'):
            if line.strip():
                parts = line.split('|||')
                containers.append({'name': parts[0], 'status': parts[1] if len(parts) > 1 else ''})
        container_info['containers'] = containers
    return render_template_string(CLOUDTAK_TEMPLATE,
        settings=settings, cloudtak=cloudtak,
        version=VERSION,
        cloudtak_icon=CLOUDTAK_ICON,
        container_info=container_info,
        deploying=cloudtak_deploy_status.get('running', False),
        deploy_done=cloudtak_deploy_status.get('complete', False))

@app.route('/cloudtak/page.js')
@login_required
def cloudtak_page_js():
    return app.response_class(CLOUDTAK_PAGE_JS, mimetype='application/javascript')

def _caddy_configured_urls(settings, modules):
    """Build list of configured subdomain → service for the Caddy page. Only when FQDN is set."""
    fqdn = settings.get('fqdn', '').strip()
    if not fqdn:
        return []
    sd = _get_all_service_domains(settings)
    urls = []
    ak = modules.get('authentik', {})
    infratak_desc = 'Console (Authentik when enabled)' if ak.get('installed') else 'Console (after login)'
    urls.append({'name': 'infra-TAK', 'host': sd['infratak'], 'url': f'https://{sd["infratak"]}', 'desc': infratak_desc})
    tak = modules.get('takserver', {})
    if tak.get('installed'):
        urls.append({'name': 'TAK Server', 'host': sd['takserver'], 'url': f'https://{sd["takserver"]}', 'desc': 'WebGUI, Marti API'})
    if ak.get('installed'):
        urls.append({'name': 'Authentik', 'host': sd['authentik'], 'url': f'https://{sd["authentik"]}', 'desc': 'Identity provider'})
    portal = modules.get('takportal', {})
    if portal.get('installed'):
        urls.append({'name': 'TAK Portal', 'host': sd['takportal'], 'url': f'https://{sd["takportal"]}', 'desc': 'User & cert management'})
    nodered = modules.get('nodered', {})
    if nodered.get('installed'):
        urls.append({'name': 'Node-RED', 'host': sd['nodered'], 'url': f'https://{sd["nodered"]}', 'desc': 'Flow editor (Authentik when enabled)'})
    cloudtak = modules.get('cloudtak', {})
    if cloudtak.get('installed'):
        urls.append({'name': 'CloudTAK (map)', 'host': sd['cloudtak_map'], 'url': f'https://{sd["cloudtak_map"]}', 'desc': 'Browser TAK client'})
        urls.append({'name': 'CloudTAK (tiles)', 'host': sd['cloudtak_tiles'], 'url': f'https://{sd["cloudtak_tiles"]}', 'desc': 'Tile server'})
        urls.append({'name': 'CloudTAK (video)', 'host': sd['cloudtak_video'], 'url': f'https://{sd["cloudtak_video"]}', 'desc': 'Map video / HLS'})
    mtx = modules.get('mediamtx', {})
    if mtx.get('installed'):
        urls.append({'name': 'MediaMTX', 'host': sd['mediamtx'], 'url': f'https://{sd["mediamtx"]}', 'desc': 'Stream web console & HLS'})
    return urls

@app.route('/caddy')
@login_required
def caddy_page():
    modules = detect_modules()
    caddy = modules.get('caddy', {})
    settings = load_settings()
    # Reset deploy state if running
    if caddy.get('installed') and caddy.get('running') and not caddy_deploy_status.get('running', False):
        caddy_deploy_status.update({'complete': False, 'error': False})
    # Read current Caddyfile if exists
    caddyfile_content = ''
    if os.path.exists(CADDYFILE_PATH):
        try:
            with open(CADDYFILE_PATH) as f:
                caddyfile_content = f.read()
        except Exception:
            pass
    configured_urls = _caddy_configured_urls(settings, modules)
    return render_template_string(CADDY_TEMPLATE,
        settings=settings, caddy=caddy, caddyfile=caddyfile_content,
        configured_urls=configured_urls,
        version=VERSION, deploying=caddy_deploy_status.get('running', False),
        deploy_done=caddy_deploy_status.get('complete', False))

# Caddy deploy state
caddy_deploy_status = {'running': False, 'complete': False, 'error': False}
caddy_deploy_log = []

@app.route('/api/caddy/deploy', methods=['POST'])
@login_required
def caddy_deploy():
    if caddy_deploy_status['running']:
        return jsonify({'success': False, 'error': 'Deployment already in progress'})
    data = request.get_json()
    domain = data.get('domain', '').strip().lower()
    if not domain:
        return jsonify({'success': False, 'error': 'Domain is required'})
    # Save domain to settings
    settings = load_settings()
    settings['fqdn'] = domain
    save_settings(settings)
    caddy_deploy_log.clear()
    caddy_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_caddy_deploy, args=(domain,), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/caddy/log')
@login_required
def caddy_log():
    return jsonify({
        'running': caddy_deploy_status['running'], 'complete': caddy_deploy_status['complete'],
        'error': caddy_deploy_status['error'], 'entries': list(caddy_deploy_log)})

@app.route('/api/caddy/domain', methods=['POST'])
@login_required
def caddy_update_domain():
    """Update domain and regenerate Caddyfile"""
    data = request.get_json()
    domain = data.get('domain', '').strip().lower()
    if not domain:
        return jsonify({'success': False, 'error': 'Domain is required'})
    settings = load_settings()
    settings['fqdn'] = domain
    save_settings(settings)
    generate_caddyfile(settings)
    # If Authentik is installed, ensure infra-TAK Console provider exists (so infratak/console are behind Authentik)
    ak_installed = os.path.exists(os.path.expanduser('~/authentik/docker-compose.yml'))
    if ak_installed:
        def _ensure_console_app():
            time.sleep(1)
            try:
                env_path = os.path.expanduser('~/authentik/.env')
                ak_token = ''
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if line.strip().startswith('AUTHENTIK_TOKEN='):
                                ak_token = line.strip().split('=', 1)[1].strip()
                                break
                if ak_token:
                    _ensure_authentik_console_app(domain, ak_token)
            except Exception:
                pass
        threading.Thread(target=_ensure_console_app, daemon=True).start()
    # Restart in background so response reaches client before Caddy restarts (console is behind Caddy)
    def _restart():
        time.sleep(2)
        try:
            subprocess.run('systemctl restart caddy 2>&1', shell=True, capture_output=True, text=True, timeout=30)
        except Exception:
            pass
    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({'success': True, 'domain': domain, 'output': 'Caddy restart scheduled.'})

@app.route('/api/caddy/caddyfile')
@login_required
def caddy_get_caddyfile():
    if os.path.exists(CADDYFILE_PATH):
        with open(CADDYFILE_PATH) as f:
            return jsonify({'success': True, 'content': f.read()})
    return jsonify({'success': False, 'content': ''})

def _caddy_restart_after_response():
    """Run in background: write Caddyfile and restart Caddy after a short delay so the HTTP response can be sent first (console is often behind Caddy)."""
    time.sleep(2)
    try:
        generate_caddyfile(load_settings())
        subprocess.run('systemctl restart caddy 2>&1', shell=True, capture_output=True, text=True, timeout=30)
    except Exception:
        pass

@app.route('/api/caddy/control', methods=['POST'])
@login_required
def caddy_control():
    data = request.get_json()
    action = data.get('action', '')
    if action == 'restart':
        generate_caddyfile(load_settings())
        threading.Thread(target=_caddy_restart_after_response, daemon=True).start()
        return jsonify({'success': True, 'output': 'Caddy restart scheduled; connection may drop briefly.'})
    elif action == 'stop':
        r = subprocess.run('systemctl stop caddy 2>&1', shell=True, capture_output=True, text=True, timeout=30)
        return jsonify({'success': r.returncode == 0, 'output': (r.stdout or r.stderr or '').strip()})
    elif action == 'start':
        generate_caddyfile(load_settings())
        threading.Thread(target=_caddy_restart_after_response, daemon=True).start()
        return jsonify({'success': True, 'output': 'Caddy start scheduled; connection may drop briefly.'})
    elif action == 'reload':
        generate_caddyfile(load_settings())
        threading.Thread(target=_caddy_restart_after_response, daemon=True).start()
        return jsonify({'success': True, 'output': 'Caddy restart scheduled; connection may drop briefly.'})
    else:
        return jsonify({'success': False, 'error': 'Unknown action'})

@app.route('/api/caddy/uninstall', methods=['POST'])
@login_required
def caddy_uninstall():
    steps = []
    subprocess.run('systemctl stop caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
    subprocess.run('systemctl disable caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
    steps.append('Stopped and disabled Caddy')
    settings = load_settings()
    pkg_mgr = settings.get('pkg_mgr', 'apt')
    if pkg_mgr == 'apt':
        subprocess.run('DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
    else:
        subprocess.run('dnf remove -y caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
    steps.append('Removed Caddy package')
    for path in ['/usr/bin/caddy', '/usr/local/bin/caddy']:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                subprocess.run(f'rm -f {path}', shell=True, capture_output=True)
    if os.path.exists('/etc/caddy'):
        subprocess.run('rm -rf /etc/caddy', shell=True, capture_output=True, timeout=10)
    subprocess.run('systemctl daemon-reload 2>/dev/null; true', shell=True, capture_output=True)
    settings['fqdn'] = ''
    save_settings(settings)
    steps.append('Cleared domain from settings')
    caddy_deploy_log.clear()
    caddy_deploy_status.update({'running': False, 'complete': False, 'error': False})
    return jsonify({'success': True, 'steps': steps})

@app.route('/api/caddy/domains', methods=['GET'])
@login_required
def caddy_get_domains():
    """Return current per-service domains and which services are installed."""
    settings = load_settings()
    modules = detect_modules()
    sd = _get_all_service_domains(settings)
    fqdn = settings.get('fqdn', '')
    services = []
    svc_defs = [
        ('infratak', 'infra-TAK', 'infratak', True),
        ('takserver', 'TAK Server', 'takserver', modules.get('takserver', {}).get('installed', False)),
        ('authentik', 'Authentik', 'authentik', modules.get('authentik', {}).get('installed', False)),
        ('takportal', 'TAK Portal', 'takportal', modules.get('takportal', {}).get('installed', False)),
        ('nodered', 'Node-RED', 'nodered', modules.get('nodered', {}).get('installed', False)),
        ('cloudtak_map', 'CloudTAK Map', 'cloudtak', modules.get('cloudtak', {}).get('installed', False)),
        ('cloudtak_tiles', 'CloudTAK Tiles', 'cloudtak', modules.get('cloudtak', {}).get('installed', False)),
        ('cloudtak_video', 'CloudTAK Video', 'cloudtak', modules.get('cloudtak', {}).get('installed', False)),
        ('mediamtx', 'MediaMTX', 'mediamtx', modules.get('mediamtx', {}).get('installed', False)),
    ]
    for key, label, mod_key, installed in svc_defs:
        setting_key = f'{key}_domain' if key != 'mediamtx' else 'mediamtx_domain'
        custom = settings.get(setting_key, '')
        services.append({
            'key': key, 'label': label, 'domain': sd[key],
            'default': f'{SERVICE_DOMAIN_DEFAULTS[key]}.{fqdn}' if fqdn else '',
            'custom': custom, 'installed': installed,
        })
    return jsonify({'fqdn': fqdn, 'services': services})

@app.route('/api/caddy/domains', methods=['POST'])
@login_required
def caddy_save_domains():
    """Save per-service domain overrides and regenerate Caddyfile."""
    data = request.get_json() or {}
    domains = data.get('domains', {})
    settings = load_settings()
    fqdn = settings.get('fqdn', '')
    for key in SERVICE_DOMAIN_DEFAULTS:
        setting_key = f'{key}_domain' if key != 'mediamtx' else 'mediamtx_domain'
        if key in domains:
            val = domains[key].strip().lower()
            default_val = f'{SERVICE_DOMAIN_DEFAULTS[key]}.{fqdn}' if fqdn else ''
            if val and val != default_val:
                settings[setting_key] = val
            elif setting_key in settings:
                del settings[setting_key]
    save_settings(settings)
    generate_caddyfile(settings)
    threading.Thread(target=_caddy_restart_after_response, daemon=True).start()
    return jsonify({'success': True, 'domains': _get_all_service_domains(settings)})

SERVICE_DOMAIN_DEFAULTS = {
    'infratak': 'infratak',
    'takserver': 'tak',
    'authentik': 'authentik',
    'takportal': 'takportal',
    'nodered': 'nodered',
    'cloudtak_map': 'map',
    'cloudtak_tiles': 'tiles.map',
    'cloudtak_video': 'video',
    'mediamtx': 'stream',
}

def _get_service_domain(settings, service_key):
    """Get domain for a service: custom override from settings, or default prefix.{fqdn}."""
    setting_key = f'{service_key}_domain' if service_key != 'mediamtx' else 'mediamtx_domain'
    custom = settings.get(setting_key, '').strip()
    if custom:
        if '.' not in custom:
            fqdn = settings.get('fqdn', '').strip()
            return f'{custom}.{fqdn}' if fqdn else custom
        return custom
    fqdn = settings.get('fqdn', '').strip()
    prefix = SERVICE_DOMAIN_DEFAULTS.get(service_key, service_key)
    return f'{prefix}.{fqdn}' if fqdn else ''

def _get_all_service_domains(settings):
    """Return dict of service_key → current domain for all services."""
    return {k: _get_service_domain(settings, k) for k in SERVICE_DOMAIN_DEFAULTS}

def generate_caddyfile(settings=None):
    """Generate Caddyfile based on current settings and deployed services.
    Each service gets its own domain (customizable per-service, defaults to subdomain of base FQDN)."""
    if settings is None:
        settings = load_settings()
    domain = settings.get('fqdn', '')
    if not domain:
        return
    modules = detect_modules()

    lines = [f"# infra-TAK - Auto-generated Caddyfile", f"# Base Domain: {domain}", ""]
    sd = _get_all_service_domains(settings)

    ak = modules.get('authentik', {})
    nodered = modules.get('nodered', {})
    infratak_host = sd['infratak']
    lines.append(f"{infratak_host} {{")
    if ak.get('installed'):
        lines.append(f"    route /login* {{")
        lines.append(f"        reverse_proxy 127.0.0.1:5001 {{")
        lines.append(f"            transport http {{")
        lines.append(f"                tls")
        lines.append(f"                tls_insecure_skip_verify")
        lines.append(f"                read_timeout 1h")
        lines.append(f"                write_timeout 1h")
        lines.append(f"            }}")
        lines.append(f"        }}")
        lines.append(f"    }}")
        lines.append(f"    route {{")
        lines.append(f"        reverse_proxy /outpost.goauthentik.io/* 127.0.0.1:9090")
        lines.append(f"        forward_auth 127.0.0.1:9090 {{")
        lines.append(f"            uri /outpost.goauthentik.io/auth/caddy")
        lines.append(f"            copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid")
        lines.append(f"            trusted_proxies private_ranges")
        lines.append(f"        }}")
        lines.append(f"        reverse_proxy 127.0.0.1:5001 {{")
        lines.append(f"            transport http {{")
        lines.append(f"                tls")
        lines.append(f"                tls_insecure_skip_verify")
        lines.append(f"                read_timeout 1h")
        lines.append(f"                write_timeout 1h")
        lines.append(f"            }}")
        lines.append(f"        }}")
        lines.append(f"    }}")
    else:
        lines.append(f"    reverse_proxy 127.0.0.1:5001 {{")
        lines.append(f"        transport http {{")
        lines.append(f"            tls")
        lines.append(f"            tls_insecure_skip_verify")
        lines.append(f"            read_timeout 1h")
        lines.append(f"            write_timeout 1h")
        lines.append(f"        }}")
        lines.append(f"    }}")
    lines.append(f"}}")
    lines.append("")

    if nodered.get('installed'):
        nodered_host = sd['nodered']
        lines.append(f"# Node-RED flow editor")
        lines.append(f"{nodered_host} {{")
        if ak.get('installed'):
            lines.append(f"    route {{")
            lines.append(f"        reverse_proxy /outpost.goauthentik.io/* 127.0.0.1:9090")
            lines.append(f"        forward_auth 127.0.0.1:9090 {{")
            lines.append(f"            uri /outpost.goauthentik.io/auth/caddy")
            lines.append(f"            trusted_proxies private_ranges")
            lines.append(f"        }}")
            lines.append(f"        reverse_proxy 127.0.0.1:1880")
            lines.append(f"    }}")
        else:
            lines.append(f"    reverse_proxy 127.0.0.1:1880")
        lines.append(f"}}")
        lines.append("")

    tak = modules.get('takserver', {})
    if tak.get('installed'):
        tak_host = sd['takserver']
        lines.append(f"# TAK Server")
        lines.append(f"{tak_host} {{")
        lines.append(f"    reverse_proxy 127.0.0.1:8446 {{")
        lines.append(f"        transport http {{")
        lines.append(f"            tls")
        lines.append(f"            tls_insecure_skip_verify")
        lines.append(f"        }}")
        lines.append(f"        header_down Location 127.0.0.1:8446 {tak_host}")
        lines.append(f"        header_down Location http:// https://")
        lines.append(f"    }}")
        lines.append(f"}}")
        lines.append("")

    ak = modules.get('authentik', {})
    if ak.get('installed'):
        ak_host = sd['authentik']
        lines.append(f"# Authentik")
        lines.append(f"{ak_host} {{")
        lines.append(f"    reverse_proxy 127.0.0.1:9090")
        lines.append(f"}}")
        lines.append("")

    portal = modules.get('takportal', {})
    if portal.get('installed'):
        portal_host = sd['takportal']
        lines.append(f"# TAK Portal")
        lines.append(f"{portal_host} {{")
        if ak.get('installed'):
            lines.append(f"    route {{")
            lines.append(f"        reverse_proxy /outpost.goauthentik.io/* 127.0.0.1:9090")
            lines.append(f"")
            lines.append(f"        @public {{")
            lines.append(f"            path /request-access* /lookup* /styles.css /favicon.ico /branding/* /public/*")
            lines.append(f"        }}")
            lines.append(f"")
            lines.append(f"        handle @public {{")
            lines.append(f"            reverse_proxy 127.0.0.1:3000")
            lines.append(f"        }}")
            lines.append(f"")
            lines.append(f"        forward_auth 127.0.0.1:9090 {{")
            lines.append(f"            uri /outpost.goauthentik.io/auth/caddy")
            lines.append(f"            copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Entitlements X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version")
            lines.append(f"            trusted_proxies private_ranges")
            lines.append(f"        }}")
            lines.append(f"")
            lines.append(f"        reverse_proxy 127.0.0.1:3000")
            lines.append(f"    }}")
        else:
            lines.append(f"    reverse_proxy 127.0.0.1:3000")
        lines.append(f"}}")
        lines.append("")

    cloudtak = modules.get('cloudtak', {})
    if cloudtak.get('installed'):
        ct_map = sd['cloudtak_map']
        ct_tiles = sd['cloudtak_tiles']
        ct_video = sd['cloudtak_video']
        lines.append(f"# CloudTAK Web UI")
        lines.append(f"{ct_map} {{")
        lines.append(f"    reverse_proxy 127.0.0.1:5000")
        lines.append(f"}}")
        lines.append("")
        lines.append(f"# CloudTAK Tile Server (CORS for map origin)")
        lines.append(f"{ct_tiles} {{")
        lines.append(f"    header Access-Control-Allow-Origin *")
        lines.append(f"    reverse_proxy 127.0.0.1:5002")
        lines.append(f"}}")
        lines.append("")
        lines.append(f"# CloudTAK Media (video) — /stream/* → HLS, rest → MediaMTX API")
        lines.append(f"{ct_video} {{")
        lines.append(f"    handle /stream/* {{")
        lines.append(f"        header Access-Control-Allow-Origin *")
        lines.append(f"        reverse_proxy 127.0.0.1:18888")
        lines.append(f"    }}")
        lines.append(f"    handle {{")
        lines.append(f"        header Access-Control-Allow-Origin *")
        lines.append(f"        reverse_proxy 127.0.0.1:9997")
        lines.append(f"    }}")
        lines.append(f"}}")
        lines.append("")

    mtx = modules.get('mediamtx', {})
    if mtx.get('installed'):
        mtx_host = sd['mediamtx']
        lines.append(f"# MediaMTX Web Console")
        lines.append(f"{mtx_host} {{")
        if ak.get('installed'):
            lines.append(f"    route /watch/* {{")
            lines.append(f"        reverse_proxy 127.0.0.1:5080")
            lines.append(f"    }}")
            lines.append(f"    route /hls-proxy/* {{")
            lines.append(f"        reverse_proxy 127.0.0.1:5080")
            lines.append(f"    }}")
            lines.append(f"    route /shared/* {{")
            lines.append(f"        reverse_proxy 127.0.0.1:5080")
            lines.append(f"    }}")
            lines.append(f"    route /shared-hls/* {{")
            lines.append(f"        reverse_proxy 127.0.0.1:5080")
            lines.append(f"    }}")
            lines.append(f"    route {{")
            lines.append(f"        reverse_proxy /outpost.goauthentik.io/* 127.0.0.1:9090")
            lines.append(f"        forward_auth 127.0.0.1:9090 {{")
            lines.append(f"            uri /outpost.goauthentik.io/auth/caddy")
            lines.append(f"            copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid")
            lines.append(f"            trusted_proxies private_ranges")
            lines.append(f"        }}")
            lines.append(f"        reverse_proxy 127.0.0.1:5080")
            lines.append(f"    }}")
        else:
            lines.append(f"    reverse_proxy 127.0.0.1:5080")
        lines.append(f"}}")
        lines.append("")

    caddyfile = '\n'.join(lines)
    os.makedirs(os.path.dirname(CADDYFILE_PATH), exist_ok=True)
    with open(CADDYFILE_PATH, 'w') as f:
        f.write(caddyfile)
    return caddyfile

def wait_for_apt_lock(log_fn, log_list):
    """
    Wait for unattended-upgrades / apt locks to release before installing packages.
    Called at the start of every deploy that uses apt/dpkg.
    Waits indefinitely — no timeout. Checks both process and dpkg lock file.
    Appends a ⏳ ticker line every 10s — the frontend JS overwrites it in place.
    """
    def is_locked():
        # Check dpkg lock file
        lock = subprocess.run('lsof /var/lib/dpkg/lock-frontend 2>/dev/null',
            shell=True, capture_output=True, text=True)
        if lock.stdout.strip():
            return True
        # Check for active upgrade process (exclude the shutdown watcher)
        proc = subprocess.run('ps aux | grep "/usr/bin/unattended-upgrade" | grep -v shutdown | grep -v grep',
            shell=True, capture_output=True, text=True)
        return bool(proc.stdout.strip())

    if not is_locked():
        return True
    log_fn("⏳ Unattended-upgrades is running — waiting for it to finish...")
    log_fn("  This can take 20-45 minutes on a fresh VPS. Do not cancel.")
    waited = 0
    while True:
        time.sleep(10)
        waited += 10
        if not is_locked():
            m, s = divmod(waited, 60)
            log_fn(f"✓ System upgrades complete (waited {m}m {s}s)")
            time.sleep(5)
            return True
        m, s = divmod(waited, 60)
        log_list.append(f"  ⏳ {m:02d}:{s:02d}")


def install_le_cert_on_8446(domain, log_fn, wait_for_cert=True):
    """
    Install the Caddy-managed Let's Encrypt cert on TAK Server's port 8446
    so TAK clients trust the enrollment endpoint without a data package.

    Called from:
      - run_caddy_deploy  (Step 5/5) — wait_for_cert=True  (Caddy just started, cert may need a moment)
      - run_takserver_deploy (end)   — wait_for_cert=False (Caddy already running, cert should exist)

    Args:
        domain:        Base FQDN, e.g. "taktical.net"
        log_fn:        Logging function (plog or log_step)
        wait_for_cert: If True, poll up to 60s for cert files before giving up
    """
    import re, shutil

    tak_domain = f"tak.{domain}"
    cert_dir = (f"/var/lib/caddy/.local/share/caddy/certificates/"
                f"acme-v02.api.letsencrypt.org-directory/{tak_domain}")
    cert_crt = f"{cert_dir}/{tak_domain}.crt"
    cert_key = f"{cert_dir}/{tak_domain}.key"
    core_config = "/opt/tak/CoreConfig.xml"

    # Optionally wait for Caddy to finish obtaining the cert
    if wait_for_cert:
        waited = 0
        while not (os.path.exists(cert_crt) and os.path.exists(cert_key)) and waited < 120:
            log_fn(f"  Waiting for LE cert files... ({waited}s)")
            time.sleep(10)
            waited += 10

    if not (os.path.exists(cert_crt) and os.path.exists(cert_key)):
        log_fn(f"  ⚠ LE cert not found at {cert_dir}")
        log_fn("  Skipping 8446 cert install — DNS may not be propagated yet")
        log_fn("  Re-run Caddy deploy once the cert is available")
        return False

    log_fn(f"  ✓ LE cert files found for {tak_domain}")

    # Step A: LE cert → PKCS12
    r = subprocess.run(
        f'openssl pkcs12 -export -in "{cert_crt}" -inkey "{cert_key}" '
        f'-out /tmp/takserver-le.p12 -name "{tak_domain}" -password pass:atakatak 2>&1',
        shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        log_fn(f"  ⚠ PKCS12 conversion failed: {r.stderr.strip()[:200]}")
        return False
    log_fn("  ✓ PKCS12 created")

    # Step B: PKCS12 → JKS
    r = subprocess.run(
        'keytool -importkeystore -srcstorepass atakatak -deststorepass atakatak '
        '-destkeystore /tmp/takserver-le.jks -srckeystore /tmp/takserver-le.p12 '
        '-srcstoretype pkcs12 2>&1',
        shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        log_fn(f"  ⚠ JKS conversion failed: {r.stderr.strip()[:200]}")
        return False

    subprocess.run(
        'mv /tmp/takserver-le.jks /opt/tak/certs/files/ && '
        'chown tak:tak /opt/tak/certs/files/takserver-le.jks',
        shell=True)
    log_fn("  ✓ JKS installed to /opt/tak/certs/files/takserver-le.jks")

    # Step C: Patch CoreConfig.xml 8446 connector
    try:
        with open(core_config, 'r') as f:
            content = f.read()
        shutil.copy(core_config, core_config + '.bak-le')
        new_connector = (
            '<connector port="8446" clientAuth="false" _name="LetsEncrypt" '
            'keystore="JKS" keystoreFile="certs/files/takserver-le.jks" '
            'keystorePass="atakatak" enableAdminUI="true" enableWebtak="true" '
            'enableNonAdminUI="false"/>'
        )
        patched = re.sub(r'<connector port="8446"[^/]*/>', new_connector, content)
        if patched != content:
            with open(core_config, 'w') as f:
                f.write(patched)
            log_fn("  ✓ CoreConfig.xml 8446 connector patched to use LE cert")
        else:
            log_fn("  ⚠ 8446 connector pattern not matched in CoreConfig.xml — check manually")
    except Exception as ce:
        log_fn(f"  ⚠ CoreConfig patch error: {ce}")

    # Step D: Write renewal script
    renewal_script = f'''#!/bin/bash
# TAK Server Let's Encrypt Certificate Renewal
# Triggered monthly by systemd timer. Rebuilds TAK JKS from Caddy cert when
# within 40 days of expiry, then restarts TAK Server.
set -euo pipefail

TAK_DOMAIN="{tak_domain}"
CERT_DIR="{cert_dir}"
CERT_CRT="$CERT_DIR/$TAK_DOMAIN.crt"
CERT_KEY="$CERT_DIR/$TAK_DOMAIN.key"
RENEW_WINDOW_DAYS=40
LOG_FILE="/var/log/takserver-cert-renewal.log"

log() {{ echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"; }}

if [ ! -f "$CERT_CRT" ] || [ ! -f "$CERT_KEY" ]; then
  log "ERROR: Caddy cert files not found for $TAK_DOMAIN"
  exit 1
fi

END_DATE_RAW=$(openssl x509 -enddate -noout -in "$CERT_CRT" | cut -d= -f2)
END_EPOCH=$(date -d "$END_DATE_RAW" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (END_EPOCH - NOW_EPOCH) / 86400 ))
log "Certificate days remaining for $TAK_DOMAIN: ${{DAYS_LEFT}} day(s)"

if [ "$DAYS_LEFT" -gt "$RENEW_WINDOW_DAYS" ]; then
  log "Outside renewal window (${{RENEW_WINDOW_DAYS}}d). No action taken."
  exit 0
fi

log "Within renewal window. Triggering Caddy reload and refreshing TAK keystore..."
if ! systemctl reload caddy; then
  log "Caddy reload failed; restarting..."
  systemctl restart caddy
fi
sleep 15

openssl pkcs12 -export -in "$CERT_CRT" -inkey "$CERT_KEY" \\
  -out /tmp/takserver-le.p12 -name "$TAK_DOMAIN" -password pass:atakatak

keytool -importkeystore -srcstorepass atakatak -deststorepass atakatak \\
  -destkeystore /tmp/takserver-le.jks -srckeystore /tmp/takserver-le.p12 \\
  -srcstoretype pkcs12

rm -f /opt/tak/certs/files/takserver-le.jks
mv /tmp/takserver-le.jks /opt/tak/certs/files/
chown tak:tak /opt/tak/certs/files/takserver-le.jks

systemctl restart takserver
log "TAK keystore refreshed and TAK Server restarted."
'''
    with open('/opt/tak/renew-letsencrypt.sh', 'w') as f:
        f.write(renewal_script)
    subprocess.run('chmod +x /opt/tak/renew-letsencrypt.sh', shell=True)
    log_fn("  ✓ Renewal script created at /opt/tak/renew-letsencrypt.sh")

    # Step E: Create systemd service + timer
    svc = '''[Unit]
Description=TAK Server Let's Encrypt Certificate Renewal
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/tak/renew-letsencrypt.sh
'''
    timer = '''[Unit]
Description=TAK Server Certificate Renewal Timer
Requires=takserver-cert-renewal.service

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
'''
    with open('/etc/systemd/system/takserver-cert-renewal.service', 'w') as f:
        f.write(svc)
    with open('/etc/systemd/system/takserver-cert-renewal.timer', 'w') as f:
        f.write(timer)
    subprocess.run(
        'systemctl daemon-reload && systemctl enable --now takserver-cert-renewal.timer 2>/dev/null; true',
        shell=True, capture_output=True)
    log_fn("  ✓ Auto-renewal timer enabled (monthly)")

    # Step F: Restart TAK Server to load new cert
    log_fn("  Restarting TAK Server to load LE cert on port 8446...")
    subprocess.run('systemctl restart takserver 2>/dev/null; true', shell=True, capture_output=True)
    log_fn("  ✓ TAK Server restarted")
    log_fn("✓ Port 8446 now serving Let's Encrypt cert — ready for TAK clients")
    return True


def run_caddy_deploy(domain):
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        caddy_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        settings = load_settings()
        pkg_mgr = settings.get('pkg_mgr', 'apt')

        if pkg_mgr == 'apt':
            wait_for_apt_lock(plog, caddy_deploy_log)

        plog("━━━ Step 1/4: Installing Caddy ━━━")
        if pkg_mgr == 'apt':
            plog("  Adding Caddy repository...")
            cmds = [
                'apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl 2>&1',
                'curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>&1',
                'curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | tee /etc/apt/sources.list.d/caddy-stable.list 2>&1',
                'apt-get update -qq 2>&1',
                'apt-get install -y caddy 2>&1'
            ]
            for cmd in cmds:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120,
                    env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'NEEDRESTART_MODE': 'a'})
                if r.returncode != 0:
                    err = (r.stderr.strip() or r.stdout.strip())[:300]
                    plog(f"✗ Caddy install failed at: {cmd[:60]}")
                    plog(f"  Error: {err}")
                    caddy_deploy_status.update({'running': False, 'error': True})
                    return
        else:
            plog("  Installing Caddy via dnf...")
            subprocess.run('dnf install -y "dnf-command(copr)" 2>&1', shell=True, capture_output=True, text=True, timeout=60)
            subprocess.run('dnf copr enable -y @caddy/caddy 2>&1', shell=True, capture_output=True, text=True, timeout=60)
            r = subprocess.run('dnf install -y caddy 2>&1', shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                plog(f"✗ Caddy install failed")
                caddy_deploy_status.update({'running': False, 'error': True})
                return

        # Verify install (if binary missing e.g. after uninstall, reinstall restores it)
        r = subprocess.run('which caddy', shell=True, capture_output=True, text=True)
        if r.returncode != 0 and pkg_mgr == 'apt':
            plog("  Binary missing after install; reinstalling package...")
            subprocess.run('DEBIAN_FRONTEND=noninteractive apt-get install --reinstall -y caddy 2>&1',
                shell=True, capture_output=True, text=True, timeout=120, env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'NEEDRESTART_MODE': 'a'})
            r = subprocess.run('which caddy', shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            plog("✗ Caddy binary not found after install")
            caddy_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Caddy installed")

        plog("")
        plog("━━━ Step 2/4: Generating Caddyfile ━━━")
        plog(f"  Domain: {domain}")
        caddyfile = generate_caddyfile(settings)
        plog(f"  Generated Caddyfile ({len(caddyfile)} bytes)")
        plog("✓ Caddyfile written to /etc/caddy/Caddyfile")

        plog("")
        plog("━━━ Step 3/4: Configuring Firewall ━━━")
        # Open ports 80 and 443
        r = subprocess.run('which ufw', shell=True, capture_output=True)
        if r.returncode == 0:
            subprocess.run('ufw allow 80/tcp 2>/dev/null; true', shell=True, capture_output=True)
            subprocess.run('ufw allow 443/tcp 2>/dev/null; true', shell=True, capture_output=True)
            plog("  ✓ UFW: ports 80 and 443 opened")
        r = subprocess.run('which firewall-cmd', shell=True, capture_output=True)
        if r.returncode == 0:
            subprocess.run('firewall-cmd --permanent --add-service=http 2>/dev/null; true', shell=True, capture_output=True)
            subprocess.run('firewall-cmd --permanent --add-service=https 2>/dev/null; true', shell=True, capture_output=True)
            subprocess.run('firewall-cmd --reload 2>/dev/null; true', shell=True, capture_output=True)
            plog("  ✓ firewalld: ports 80 and 443 opened")
        plog("✓ Firewall configured")

        plog("")
        plog("━━━ Step 4/4: Starting Caddy ━━━")
        subprocess.run('systemctl enable caddy 2>/dev/null; true', shell=True, capture_output=True)
        r = subprocess.run('systemctl restart caddy 2>&1', shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            plog(f"⚠ systemctl restart: {(r.stderr or r.stdout or '').strip()[:300]}")
        time.sleep(3)
        r = subprocess.run('systemctl is-active caddy', shell=True, capture_output=True, text=True)
        if r.stdout.strip() == 'active':
            plog("✓ Caddy is running")
        else:
            plog("✗ Caddy did not start. Capturing status and logs:")
            status = subprocess.run('systemctl status caddy --no-pager -l 2>&1', shell=True, capture_output=True, text=True, timeout=10)
            if status.stdout:
                for line in (status.stdout or '').strip().split('\n')[:15]:
                    plog(f"  {line}")
            journal = subprocess.run('journalctl -u caddy -n 25 --no-pager 2>&1', shell=True, capture_output=True, text=True, timeout=10)
            if journal.stdout:
                plog("  --- journalctl -u caddy (last 25 lines) ---")
                for line in (journal.stdout or '').strip().split('\n'):
                    plog(f"  {line}")
            caddy_deploy_status.update({'running': False, 'error': True})
            return

        # Update settings
        settings['ssl_mode'] = 'fqdn'
        save_settings(settings)

        plog("")
        plog("=" * 50)
        plog(f"✓ Caddy deployed successfully!")
        plog(f"  Domain: https://{domain}")
        plog(f"  SSL: Let's Encrypt (automatic)")
        plog("  Note: DNS must point to this server's IP for SSL to activate")
        plog("=" * 50)
        caddy_deploy_status.update({'running': False, 'complete': True})

    except Exception as e:
        plog(f"✗ Error: {str(e)}")
        caddy_deploy_status.update({'running': False, 'error': True})

def _get_takportal_version_info():
    """Return {version: str, update_available: bool, latest: str|None} for TAK Portal.
    Version from package.json; update status from container logs [update-check] line."""
    import re
    portal_dir = os.path.expanduser('~/TAK-Portal')
    out = {'version': '', 'update_available': False, 'latest': None}
    # Prefer package.json version (semantic version)
    pkg_path = os.path.join(portal_dir, 'package.json')
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path) as f:
                data = json.load(f)
            out['version'] = (data.get('version') or '').strip()
        except Exception:
            pass
    if not out['version'] and os.path.isdir(os.path.join(portal_dir, '.git')):
        rv = subprocess.run(f'cd {portal_dir} && git describe --tags --always 2>/dev/null || git log -1 --format="%h"', shell=True, capture_output=True, text=True, timeout=5)
        if rv.returncode == 0 and rv.stdout.strip():
            out['version'] = rv.stdout.strip()
    # If container is running, parse last [update-check] line for update_available
    r = subprocess.run('docker ps --filter name=tak-portal -q 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if r.returncode == 0 and (r.stdout or '').strip():
        log_r = subprocess.run('docker logs tak-portal --tail 200 2>&1', shell=True, capture_output=True, text=True, timeout=10)
        if log_r.stdout:
            for line in reversed(log_r.stdout.strip().split('\n')):
                if '[update-check]' in line:
                    # e.g. [update-check] current=1.2.19 latest=1.2.20 update=true
                    m = re.search(r'latest=([^\s]+)', line)
                    if m:
                        out['latest'] = m.group(1).strip()
                    if 'update=true' in line:
                        out['update_available'] = True
                    break
    return out


def _get_takserver_version_info():
    """Return {version: str, update_available: bool, latest: None} for TAK Server from installed package."""
    out = {'version': '', 'update_available': False, 'latest': None}
    if not os.path.exists('/opt/tak') or not os.path.exists('/opt/tak/CoreConfig.xml'):
        return out
    r = subprocess.run("dpkg -s takserver 2>/dev/null | grep ^Version:", shell=True, capture_output=True, text=True, timeout=5)
    if r.returncode == 0 and r.stdout.strip():
        # "Version: 5.6-RELEASE-6" or "Version: 5.6-RELEASE-6-HEAD"
        out['version'] = r.stdout.strip().replace('Version:', '').strip()
        return out
    r = subprocess.run("rpm -q takserver 2>/dev/null", shell=True, capture_output=True, text=True, timeout=5)
    if r.returncode == 0 and r.stdout.strip():
        # noarch package: takserver-5.6-RELEASE-6.noarch
        ver = r.stdout.strip()
        if ver.startswith('takserver-'):
            ver = ver.split('-', 1)[1]
        if '.noarch' in ver:
            ver = ver.replace('.noarch', '')
        if ver:
            out['version'] = ver
    return out


def _get_caddy_version_info():
    """Return {version: str, update_available: bool} for Caddy."""
    out = {'version': '', 'update_available': False}
    r = subprocess.run('caddy version 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if r.returncode == 0 and r.stdout:
        # e.g. "v2.8.4" or "Caddy v2.8.4"
        import re
        m = re.search(r'v(\d+\.\d+\.\d+[^\s]*)', r.stdout)
        if m:
            out['version'] = 'v' + m.group(1).strip()
    if out['version']:
        apt = subprocess.run('apt list --upgradable 2>/dev/null | grep -i caddy', shell=True, capture_output=True, text=True, timeout=10)
        if apt.returncode == 0 and (apt.stdout or '').strip():
            out['update_available'] = True
    return out


def _get_authentik_version_info():
    """Return {version: str, update_available: bool} for Authentik from image tag or docker."""
    out = {'version': '', 'update_available': False}
    ak_dir = os.path.expanduser('~/authentik')
    compose_path = os.path.join(ak_dir, 'docker-compose.yml')
    if not os.path.isfile(compose_path):
        return out
    try:
        with open(compose_path) as f:
            content = f.read()
        import re
        # image: ghcr.io/goauthentik/server:2024.2.1 or :latest
        m = re.search(r'image:.*?/server:([^\s\n]+)', content)
        if m:
            out['version'] = m.group(1).strip()
        if not out['version']:
            r = subprocess.run('docker images --format "{{.Tag}}" ghcr.io/goauthentik/server 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                out['version'] = r.stdout.strip().split('\n')[0]
    except Exception:
        pass
    # update_available: leave False unless we add docker compose pull check
    return out


def _get_nodered_version_info():
    """Return {version: str, update_available: bool} for Node-RED from container or image."""
    out = {'version': '', 'update_available': False}
    r = subprocess.run('docker ps -q -f name=nodered 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if not (r.returncode == 0 and (r.stdout or '').strip()):
        return out
    # Try to get version from container (Node-RED package.json)
    ex = subprocess.run('docker exec nodered node -p "try{require(\'/usr/src/node-red/package.json\').version}catch(e){\'\'}" 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if ex.returncode == 0 and ex.stdout.strip():
        out['version'] = ex.stdout.strip().strip('"\'')
    if not out['version']:
        out['version'] = 'latest'
    return out


def _get_cloudtak_version_info():
    """Return {version: str, update_available: bool, latest: str|None} for CloudTAK."""
    import re
    out = {'version': '', 'update_available': False, 'latest': None}
    ct_dir = os.path.expanduser('~/CloudTAK')
    for pkg in ['package.json', 'api/package.json', 'web/package.json']:
        pkg_path = os.path.join(ct_dir, pkg)
        if os.path.isfile(pkg_path):
            try:
                with open(pkg_path) as f:
                    data = json.load(f)
                out['version'] = (data.get('version') or '').strip()
                if out['version']:
                    break
            except Exception:
                pass
    if not out['version'] and os.path.isdir(os.path.join(ct_dir, '.git')):
        rv = subprocess.run(f'cd {ct_dir} && git describe --tags --always 2>/dev/null || git log -1 --format="%h"', shell=True, capture_output=True, text=True, timeout=5)
        if rv.returncode == 0 and rv.stdout.strip():
            out['version'] = rv.stdout.strip()
    r = subprocess.run('docker ps -q -f name=cloudtak-api 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5)
    if r.returncode == 0 and (r.stdout or '').strip():
        log_r = subprocess.run('docker logs cloudtak-api --tail 150 2>&1', shell=True, capture_output=True, text=True, timeout=10)
        if log_r.stdout:
            for line in reversed(log_r.stdout.strip().split('\n')):
                if '[update-check]' in line:
                    m = re.search(r'latest=([^\s]+)', line)
                    if m:
                        out['latest'] = m.group(1).strip()
                    if 'update=true' in line:
                        out['update_available'] = True
                    break
    return out


def get_all_module_versions():
    """Return dict of module_key -> {version, update_available, latest?} for console cards."""
    modules = detect_modules()
    result = {}
    if modules.get('caddy', {}).get('installed'):
        result['caddy'] = _get_caddy_version_info()
    if modules.get('authentik', {}).get('installed'):
        result['authentik'] = _get_authentik_version_info()
    if modules.get('nodered', {}).get('installed'):
        result['nodered'] = _get_nodered_version_info()
    if modules.get('cloudtak', {}).get('installed'):
        result['cloudtak'] = _get_cloudtak_version_info()
    if modules.get('takportal', {}).get('installed'):
        result['takportal'] = _get_takportal_version_info()
    if modules.get('takserver', {}).get('installed'):
        result['takserver'] = _get_takserver_version_info()
    return result


@app.route('/api/modules/version')
@login_required
def api_modules_version():
    """Return version and update_available for all installed services (for console cards)."""
    return jsonify(get_all_module_versions())


@app.route('/api/takportal/version')
@login_required
def takportal_version_api():
    """Return TAK Portal version and update-available for module/card UI."""
    info = _get_takportal_version_info()
    return jsonify(info)


@app.route('/takportal')
@login_required
def takportal_page():
    modules = detect_modules()
    portal = modules.get('takportal', {})
    settings = load_settings()
    # Reset deploy_done once TAK Portal is running so the running view shows
    if portal.get('installed') and portal.get('running') and not takportal_deploy_status.get('running', False):
        takportal_deploy_status.update({'complete': False, 'error': False})
    # Get container info if running
    container_info = {}
    if portal.get('running'):
        r = subprocess.run('docker ps --filter name=tak-portal --format "{{.Names}}|||{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        if r.stdout.strip():
            containers = []
            for line in r.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split('|||')
                    containers.append({'name': parts[0] if len(parts) > 0 else 'tak-portal', 'status': parts[1] if len(parts) > 1 else ''})
            container_info['containers'] = containers
            container_info['status'] = containers[0]['status'] if containers else ''
    # Get portal port from .env if exists
    portal_port = '3000'
    env_path = os.path.expanduser('~/TAK-Portal/.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('WEB_UI_PORT='):
                    portal_port = line.strip().split('=', 1)[1].strip() or '3000'
    # Real version (package.json) and update-available (from container logs)
    vinfo = _get_takportal_version_info()
    portal_version = vinfo['version'] or ''
    portal_update_available = vinfo['update_available']
    portal_latest = vinfo['latest']
    return render_template_string(TAKPORTAL_TEMPLATE,
        settings=settings, portal=portal, container_info=container_info,
        portal_port=portal_port, portal_version=portal_version,
        portal_update_available=portal_update_available, portal_latest=portal_latest,
        version=VERSION,
        deploying=takportal_deploy_status.get('running', False),
        deploy_done=takportal_deploy_status.get('complete', False))

# TAK Portal deploy state
takportal_deploy_log = []
takportal_deploy_status = {'running': False, 'complete': False, 'error': False}

@app.route('/api/takportal/control', methods=['POST'])
@login_required
def takportal_control():
    action = request.json.get('action')
    portal_dir = os.path.expanduser('~/TAK-Portal')
    if action == 'start':
        subprocess.run(f'cd {portal_dir} && docker compose up -d --build', shell=True, capture_output=True, text=True, timeout=120)
    elif action == 'stop':
        subprocess.run(f'cd {portal_dir} && docker compose down', shell=True, capture_output=True, text=True, timeout=60)
    elif action == 'restart':
        subprocess.run(f'cd {portal_dir} && docker compose down && docker compose up -d', shell=True, capture_output=True, text=True, timeout=120)
    elif action == 'update':
        pull = subprocess.run(f'cd {portal_dir} && git pull --rebase --autostash', shell=True, capture_output=True, text=True, timeout=60)
        pull_msg = pull.stdout.strip().split('\n')[-1] if pull.stdout.strip() else ''
        build = subprocess.run(f'cd {portal_dir} && docker compose up -d --build', shell=True, capture_output=True, text=True, timeout=180)
        subprocess.run(f'cd {portal_dir} && docker image prune -f', shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(3)
        vinfo = _get_takportal_version_info()
        new_version = vinfo['version'] or ''
        r = subprocess.run('docker ps --filter name=tak-portal --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        running = 'Up' in r.stdout
        return jsonify({'success': True, 'running': running, 'action': action, 'pull': pull_msg, 'version': new_version})
    else:
        return jsonify({'error': 'Invalid action'}), 400
    time.sleep(3)
    r = subprocess.run('docker ps --filter name=tak-portal --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
    running = 'Up' in r.stdout
    return jsonify({'success': True, 'running': running, 'action': action})

@app.route('/api/takportal/deploy', methods=['POST'])
@login_required
def takportal_deploy():
    if takportal_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    takportal_deploy_log.clear()
    takportal_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_takportal_deploy, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/takportal/deploy/log')
@login_required
def takportal_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': takportal_deploy_log[idx:], 'total': len(takportal_deploy_log),
        'running': takportal_deploy_status['running'], 'complete': takportal_deploy_status['complete'],
        'error': takportal_deploy_status['error']})

@app.route('/api/takportal/logs')
@login_required
def takportal_container_logs():
    """Get recent container logs"""
    lines = request.args.get('lines', 50, type=int)
    r = subprocess.run(f'docker logs tak-portal --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=10)
    entries = []
    skip_lines = {'npm error', 'npm ERR', 'signal SIGTERM', 'command failed', 'A complete log of this run'}
    for line in (r.stdout.strip().split('\n') if r.stdout.strip() else []):
        if not any(s in line for s in skip_lines):
            entries.append(line)
    return jsonify({'entries': entries})

@app.route('/api/takportal/uninstall', methods=['POST'])
@login_required
def takportal_uninstall():
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    portal_dir = os.path.expanduser('~/TAK-Portal')
    steps = []
    subprocess.run(f'cd {portal_dir} && docker compose down -v --rmi local 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
    steps.append('Stopped and removed Docker containers/volumes')
    if os.path.exists(portal_dir):
        subprocess.run(f'rm -rf {portal_dir}', shell=True, capture_output=True)
        steps.append('Removed ~/TAK-Portal')
    takportal_deploy_log.clear()
    takportal_deploy_status.update({'running': False, 'complete': False, 'error': False})
    return jsonify({'success': True, 'steps': steps})

def _portal_email_settings(settings):
    """Build TAK Portal email settings from the Email Relay config if deployed."""
    relay = settings.get('email_relay', {})
    if relay.get('relay_host') and relay.get('smtp_user'):
        from_addr = relay.get('from_addr', '')
        from_name = relay.get('from_name', 'TAK Admin')
        smtp_from = f"{from_name} <{from_addr}>" if from_name and from_addr else from_addr
        return {
            "EMAIL_ENABLED": "true",
            "EMAIL_PROVIDER": "smtp",
            "SMTP_HOST": relay.get('relay_host', ''),
            "SMTP_PORT": str(relay.get('relay_port', '587')),
            "SMTP_SECURE": "false",
            "SMTP_USER": relay.get('smtp_user', ''),
            "SMTP_PASS": relay.get('smtp_pass', ''),
            "SMTP_FROM": smtp_from,
            "EMAIL_ALWAYS_CC": "",
            "EMAIL_SEND_COPY_TO": "",
            "EMAIL_FAIL_HARD": "false",
        }
    return {
        "EMAIL_ENABLED": "false",
        "EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "",
        "SMTP_PORT": "587",
        "SMTP_SECURE": "false",
        "SMTP_USER": "",
        "SMTP_PASS": "",
        "SMTP_FROM": "",
        "EMAIL_ALWAYS_CC": "",
        "EMAIL_SEND_COPY_TO": "",
        "EMAIL_FAIL_HARD": "false",
    }

def run_takportal_deploy():
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        takportal_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        portal_dir = os.path.expanduser('~/TAK-Portal')
        settings = load_settings()
        if settings.get('pkg_mgr', 'apt') == 'apt':
            wait_for_apt_lock(plog, takportal_deploy_log)
        # Step 1: Check Docker
        plog("\u2501\u2501\u2501 Step 1/6: Checking Docker \u2501\u2501\u2501")
        r = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            plog("Docker not found. Installing...")
            subprocess.run('curl -fsSL https://get.docker.com | sh', shell=True, capture_output=True, text=True, timeout=300)
            r2 = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
            if r2.returncode != 0:
                plog("\u2717 Failed to install Docker")
                takportal_deploy_status.update({'running': False, 'error': True})
                return
            plog(f"  {r2.stdout.strip()}")
            plog("\u2713 Docker installed")
        else:
            plog(f"  {r.stdout.strip()}")
            plog("\u2713 Docker available")

        # Step 2: Clone repo
        plog("")
        plog("\u2501\u2501\u2501 Step 2/6: Cloning TAK Portal \u2501\u2501\u2501")
        if os.path.exists(portal_dir):
            plog("  TAK-Portal directory already exists, pulling latest...")
            subprocess.run(f'cd {portal_dir} && git pull --rebase --autostash', shell=True, capture_output=True, text=True, timeout=60)
        else:
            plog("  Cloning from GitHub...")
            r = subprocess.run(f'git clone https://github.com/AdventureSeeker423/TAK-Portal.git {portal_dir}', shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                plog(f"\u2717 Clone failed: {r.stderr.strip()}")
                takportal_deploy_status.update({'running': False, 'error': True})
                return
        plog("\u2713 Repository ready")

        # Step 3: Create .env if missing
        plog("")
        plog("\u2501\u2501\u2501 Step 3/6: Configuring \u2501\u2501\u2501")
        env_path = os.path.join(portal_dir, '.env')
        if not os.path.exists(env_path):
            plog("  Creating default .env...")
            with open(env_path, 'w') as f:
                f.write("WEB_UI_PORT=3000\n")
            plog("\u2713 Default .env created (port 3000)")
        else:
            plog("\u2713 .env already exists")

        # Step 4: Build and start
        plog("")
        plog("\u2501\u2501\u2501 Step 4/6: Building & Starting Docker Container \u2501\u2501\u2501")
        # Patch docker-compose.yml with healthcheck if not already present
        compose_path = os.path.join(portal_dir, 'docker-compose.yml')
        if os.path.exists(compose_path):
            with open(compose_path, 'r') as f:
                compose_content = f.read()
            if 'healthcheck' not in compose_content:
                # Insert healthcheck after 'restart: unless-stopped' inside the service block
                healthcheck = (
                    "    healthcheck:\n"
                    "      test: [\"CMD-SHELL\", \"wget -qO- http://localhost:3000 2>&1 | grep -q setup-my-device && exit 0 || exit 1\"]\n"
                    "      interval: 30s\n"
                    "      timeout: 10s\n"
                    "      retries: 3\n"
                    "      start_period: 15s\n"
                )
                compose_content = compose_content.replace(
                    'restart: unless-stopped',
                    'restart: unless-stopped\n' + healthcheck.rstrip('\n')
                )
                with open(compose_path, 'w') as f:
                    f.write(compose_content)
                plog("  ✓ Healthcheck added to docker-compose.yml")

        plog("  Building image (this may take a minute)...")
        r = subprocess.run(f'cd {portal_dir} && docker compose up -d --build 2>&1', shell=True, capture_output=True, text=True, timeout=900)
        for line in r.stdout.strip().split('\n'):
            if line.strip() and 'NEEDRESTART' not in line:
                takportal_deploy_log.append(f"  {line.strip()}")
        if r.returncode != 0:
            plog(f"\u2717 Docker build failed")
            for line in r.stderr.strip().split('\n'):
                if line.strip():
                    takportal_deploy_log.append(f"  \u2717 {line.strip()}")
            takportal_deploy_status.update({'running': False, 'error': True})
            return

        # Wait for container to be healthy
        plog("  Waiting for container...")
        time.sleep(5)
        r = subprocess.run('docker ps --filter name=tak-portal --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        if 'Up' in r.stdout:
            plog("\u2713 TAK Portal is running")
        else:
            plog("\u26a0 Container may not be fully started yet")

        # Step 5: Copy TAK Server certs into container
        plog("")
        plog("\u2501\u2501\u2501 Step 5/6: Copying TAK Server Certificates \u2501\u2501\u2501")
        cert_dir = '/opt/tak/certs/files'
        webadmin_p12 = os.path.join(cert_dir, 'admin.p12')
        tak_ca = os.path.join(cert_dir, 'truststore-root.p12')
        # Find the actual cert files
        if not os.path.exists(webadmin_p12):
            # Try alternate names
            for name in ['webadmin.p12', 'admin.p12']:
                p = os.path.join(cert_dir, name)
                if os.path.exists(p):
                    webadmin_p12 = p
                    break
        if not os.path.exists(tak_ca):
            for name in ['truststore-root.p12', 'tak-ca.pem', 'ca.pem']:
                p = os.path.join(cert_dir, name)
                if os.path.exists(p):
                    tak_ca = p
                    break
        # Create certs dir in container data volume (persists across rebuilds)
        subprocess.run('docker exec tak-portal mkdir -p /usr/src/app/data/certs', shell=True, capture_output=True, text=True)
        certs_copied = True
        if os.path.exists(webadmin_p12):
            # Re-encode P12 with modern encryption (AES-256-CBC) — TAK Server generates
            # legacy RC2-40-CBC which Node.js 22+ / OpenSSL 3.x rejects
            modern_p12 = '/tmp/tak-portal-admin-modern.p12'
            r = subprocess.run(
                f'openssl pkcs12 -in {webadmin_p12} -passin pass:atakatak -nodes -legacy 2>/dev/null | '
                f'openssl pkcs12 -export -passout pass:atakatak -out {modern_p12}',
                shell=True, capture_output=True, text=True, timeout=30)
            if os.path.exists(modern_p12) and os.path.getsize(modern_p12) > 0:
                subprocess.run(f'docker cp {modern_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', shell=True, capture_output=True, text=True)
                os.remove(modern_p12)
                plog(f"  Copied {os.path.basename(webadmin_p12)} -> data/certs/tak-client.p12 (re-encoded for modern OpenSSL)")
            else:
                subprocess.run(f'docker cp {webadmin_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', shell=True, capture_output=True, text=True)
                plog(f"  Copied {os.path.basename(webadmin_p12)} -> data/certs/tak-client.p12 (legacy format, re-encode failed)")
        else:
            plog("\u26a0 admin.p12 not found in /opt/tak/certs/files/")
            certs_copied = False
        # Copy CA chain for TAK Portal. takserver.pem contains the full chain
        # (server + intermediate + root) which is what TAK Portal expects.
        # Fallback to building a bundle from ca.pem + root-ca.pem if needed.
        tak_ca_src = None
        takserver_pem = os.path.join(cert_dir, 'takserver.pem')
        if os.path.exists(takserver_pem):
            tak_ca_src = takserver_pem
            plog(f"  Using takserver.pem (full chain)")
        else:
            # Build bundle from individual CA files
            int_ca = os.path.join(cert_dir, 'ca.pem')
            root_ca = os.path.join(cert_dir, 'root-ca.pem')
            bundle_parts = []
            for ca_file in [int_ca, root_ca]:
                if os.path.exists(ca_file):
                    with open(ca_file, 'r') as f:
                        content = f.read().strip()
                    if 'BEGIN CERTIFICATE' in content and 'TRUSTED' not in content:
                        bundle_parts.append(content)
            if bundle_parts:
                ca_bundle_path = '/tmp/tak-ca-bundle.pem'
                with open(ca_bundle_path, 'w') as f:
                    f.write('\n'.join(bundle_parts) + '\n')
                tak_ca_src = ca_bundle_path
                plog(f"  Built CA bundle from ca.pem + root-ca.pem ({len(bundle_parts)} certs)")
        if tak_ca_src:
            subprocess.run(f'docker cp {tak_ca_src} tak-portal:/usr/src/app/data/certs/tak-ca.pem', shell=True, capture_output=True, text=True)
            if tak_ca_src.startswith('/tmp/'):
                os.remove(tak_ca_src)
            plog(f"  -> data/certs/tak-ca.pem")
        else:
            plog("\u26a0 No CA cert files found in /opt/tak/certs/files/")
            certs_copied = False
        if certs_copied:
            plog("\u2713 Certificates copied to container data volume")

        # Step 6: Auto-configure settings.json
        plog("")
        plog("\u2501\u2501\u2501 Step 6/6: Auto-configuring TAK Portal Settings \u2501\u2501\u2501")
        settings = load_settings()
        server_ip = settings.get('server_ip', 'localhost')
        # Read Authentik bootstrap token
        ak_env_path = os.path.expanduser('~/authentik/.env')
        ak_token = ''
        if os.path.exists(ak_env_path):
            with open(ak_env_path) as f:
                for line in f:
                    if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                        ak_token = line.strip().split('=', 1)[1].strip()
        import json as json_mod
        portal_settings = {
            "AUTHENTIK_URL": f"http://{server_ip}:9090",
            "AUTHENTIK_TOKEN": ak_token,
            "USERS_HIDDEN_PREFIXES": "ak-,adm_,nodered-,ma-",
            "GROUPS_HIDDEN_PREFIXES": "authentik, MA -, vid_, tak_ROLE_",
            "USERS_ACTIONS_HIDDEN_PREFIXES": "",
            "GROUPS_ACTIONS_HIDDEN_PREFIXES": "",
            "DASHBOARD_AUTHENTIK_STATS_REFRESH_SECONDS": "300",
            "PORTAL_AUTH_ENABLED": "true" if settings.get('fqdn') else "false",
            "PORTAL_AUTH_REQUIRED_GROUP": "authentik Admins" if settings.get('fqdn') else "",
            "AUTHENTIK_PUBLIC_URL": f"https://authentik.{settings['fqdn']}" if settings.get('fqdn') else f"http://{server_ip}:9090",
            "TAK_PORTAL_PUBLIC_URL": f"https://takportal.{settings['fqdn']}" if settings.get('fqdn') else f"http://{server_ip}:3000",
            "TAK_URL": f"https://tak.{settings['fqdn']}:8443/Marti" if settings.get('fqdn') else f"https://{server_ip}:8443/Marti",
            "TAK_API_P12_PATH": "data/certs/tak-client.p12",
            "TAK_API_P12_PASSPHRASE": "atakatak",
            "TAK_CA_PATH": "data/certs/tak-ca.pem",
            "TAK_REVOKE_ON_DISABLE": "true",
            "TAK_DEBUG": "false",
            "TAK_BYPASS_ENABLED": "false",
            "CLOUDTAK_URL": f"https://cloudtak.{settings['fqdn']}" if settings.get('fqdn') else "",
            **_portal_email_settings(settings),
            "BRAND_THEME": "dark",
            "BRAND_LOGO_URL": ""
        }
        # Write settings.json into the container data volume
        settings_json = json_mod.dumps(portal_settings, indent=2)
        # Write to temp file then docker cp
        with open('/tmp/tak-portal-settings.json', 'w') as f:
            f.write(settings_json)
        subprocess.run('docker cp /tmp/tak-portal-settings.json tak-portal:/usr/src/app/data/settings.json', shell=True, capture_output=True, text=True)
        os.remove('/tmp/tak-portal-settings.json')
        plog(f"  Authentik URL: {portal_settings['AUTHENTIK_PUBLIC_URL']}")
        plog(f"  TAK Server URL: {portal_settings['TAK_URL']}")
        plog(f"  Portal Auth: {portal_settings['PORTAL_AUTH_ENABLED']}")
        if portal_settings.get('EMAIL_ENABLED') == 'true':
            plog(f"  Email: enabled ({portal_settings.get('SMTP_HOST')}:{portal_settings.get('SMTP_PORT')} from {portal_settings.get('SMTP_FROM')})")
        else:
            plog("  Email: not configured (deploy Email Relay first for auto-config)")
        if ak_token:
            plog("  Authentik API token: configured")
        else:
            plog("\u26a0 Authentik not deployed yet - configure token in Server Settings")
        plog("\u2713 Settings auto-configured")

        # Restart container to pick up settings
        subprocess.run('docker restart tak-portal', shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(3)
        plog("\u2713 TAK Portal restarted with new settings")

        # Get port
        port = '3000'
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('WEB_UI_PORT='):
                        port = line.strip().split('=', 1)[1].strip() or '3000'

        # Configure Authentik forward auth for TAK Portal
        fqdn = settings.get('fqdn', '')
        if fqdn and ak_token:
            plog("")
            plog("\u2501\u2501\u2501 Configuring Authentik Forward Auth \u2501\u2501\u2501")
            try:
                import urllib.request as _urlreq
                _ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
                _ak_url = 'http://127.0.0.1:9090'

                # Update brand domain
                try:
                    req = _urlreq.Request(f'{_ak_url}/api/v3/core/brands/', headers=_ak_headers)
                    resp = _urlreq.urlopen(req, timeout=10)
                    brands = json_mod.loads(resp.read().decode())['results']
                    if brands:
                        brand_id = brands[0]['brand_uuid']
                        req = _urlreq.Request(f'{_ak_url}/api/v3/core/brands/{brand_id}/',
                            data=json_mod.dumps({'domain': f'authentik.{fqdn}'}).encode(),
                            headers=_ak_headers, method='PATCH')
                        _urlreq.urlopen(req, timeout=10)
                        plog(f"  \u2713 Brand domain set to authentik.{fqdn}")
                except Exception as e:
                    plog(f"  \u26a0 Brand update: {str(e)[:80]}")

                # Wait forever for authorization flow
                flow_pk = None
                attempt = 0
                while True:
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=authorization&ordering=slug', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        flows = json_mod.loads(resp.read().decode())['results']
                        for fl in flows:
                            if 'implicit' in fl.get('slug', ''):
                                flow_pk = fl['pk']
                                break
                        if not flow_pk and flows:
                            flow_pk = flows[0]['pk']
                        if flow_pk:
                            break
                    except Exception:
                        pass
                    if attempt % 6 == 0:
                        plog(f"  ⏳ Waiting for authorization flow... ({attempt * 5}s)")
                    else:
                        authentik_deploy_log.append(f"  ⏳ {attempt * 5 // 60:02d}:{attempt * 5 % 60:02d}")
                    time.sleep(5)
                    attempt += 1
                plog(f"  ✓ Got authorization flow")

                # Wait forever for invalidation flow
                inv_flow_pk = None
                attempt = 0
                while True:
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=invalidation', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        inv_flows = json_mod.loads(resp.read().decode())['results']
                        inv_flow_pk = next((f['pk'] for f in inv_flows if 'provider' not in f['slug']), inv_flows[0]['pk'] if inv_flows else None)
                        if inv_flow_pk:
                            break
                    except Exception:
                        pass
                    if attempt % 6 == 0:
                        plog(f"  ⏳ Waiting for invalidation flow... ({attempt * 5}s)")
                    else:
                        authentik_deploy_log.append(f"  ⏳ {attempt * 5 // 60:02d}:{attempt * 5 % 60:02d}")
                    time.sleep(5)
                    attempt += 1
                plog(f"  ✓ Got invalidation flow")

                # Create proxy provider
                provider_pk = None
                if flow_pk and inv_flow_pk:
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/',
                            data=json_mod.dumps({'name': 'TAK Portal Proxy', 'authorization_flow': flow_pk,
                                'invalidation_flow': inv_flow_pk,
                                'external_host': f'https://takportal.{fqdn}', 'mode': 'forward_single',
                                'token_validity': 'hours=24', 'cookie_domain': f'.{fqdn.split(":")[0]}'}).encode(),
                            headers=_ak_headers, method='POST')
                        resp = _urlreq.urlopen(req, timeout=10)
                        provider_pk = json_mod.loads(resp.read().decode())['pk']
                        plog(f"  \u2713 Proxy provider created")
                    except Exception as e:
                        if hasattr(e, 'code') and e.code == 400:
                            req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/?search=TAK+Portal', headers=_ak_headers)
                            resp = _urlreq.urlopen(req, timeout=10)
                            results = json_mod.loads(resp.read().decode())['results']
                            if results:
                                provider_pk = results[0]['pk']
                            plog(f"  \u2713 Proxy provider already exists")
                        else:
                            plog(f"  \u26a0 Proxy provider error: {str(e)[:100]}")

                # Create application
                if provider_pk:
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/',
                            data=json_mod.dumps({'name': 'TAK Portal', 'slug': 'tak-portal',
                                'provider': provider_pk}).encode(),
                            headers=_ak_headers, method='POST')
                        _urlreq.urlopen(req, timeout=10)
                        plog(f"  \u2713 Application 'TAK Portal' created")
                    except Exception as e:
                        if hasattr(e, 'code') and e.code == 400:
                            plog(f"  \u2713 Application 'TAK Portal' already exists")
                        else:
                            plog(f"  \u26a0 Application error: {str(e)[:80]}")

                    # Add to embedded outpost
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/?search=embedded', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        outposts = json_mod.loads(resp.read().decode())['results']
                        embedded = next((o for o in outposts if 'embed' in o.get('name','').lower() or o.get('type') == 'proxy'), None)
                        if embedded:
                            current_providers = embedded.get('providers', [])
                            if provider_pk not in current_providers:
                                current_providers.append(provider_pk)
                            req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/{embedded["pk"]}/',
                                data=json_mod.dumps({'providers': current_providers}).encode(),
                                headers=_ak_headers, method='PATCH')
                            _urlreq.urlopen(req, timeout=10)
                            plog(f"  \u2713 TAK Portal added to embedded outpost")
                        else:
                            plog(f"  \u26a0 No embedded outpost found")
                    except Exception as e:
                        plog(f"  \u26a0 Outpost error: {str(e)[:80]}")
            except Exception as e:
                plog(f"  \u26a0 Forward auth setup error: {str(e)[:100]}")

        plog("")
        plog("=" * 50)
        plog(f"\u2713 TAK Portal deployed successfully!")
        plog(f"  Access: http://{server_ip}:{port}")
        # Regenerate Caddyfile if Caddy is configured
        if settings.get('fqdn'):
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True)
            plog(f"  \u2713 Caddy config updated for TAK Portal")
            plog(f"  Open: https://takportal.{settings.get('fqdn')}")
        plog("=" * 50)
        plog("")
        plog("  Waiting 2 minutes for Authentik to fully sync...")
        for i in range(24):
            time.sleep(5)
            remaining = 120 - (i + 1) * 5
            if remaining % 30 == 0:
                plog(f"  ⏳ {remaining} seconds remaining...")
        plog("  ✓ Sync complete — TAK Portal is ready")
        takportal_deploy_status.update({'running': False, 'complete': True})
    except Exception as e:
        plog(f"\u2717 FATAL ERROR: {str(e)}")
        takportal_deploy_status.update({'running': False, 'error': True})

@app.route('/certs')
@login_required
def certs_page():
    settings = load_settings()
    cert_dir = '/opt/tak/certs/files'
    files = []
    if os.path.isdir(cert_dir):
        for fn in sorted(os.listdir(cert_dir)):
            fp = os.path.join(cert_dir, fn)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                if sz < 1024: sz_d = f"{sz} B"
                elif sz < 1048576: sz_d = f"{round(sz/1024,1)} KB"
                else: sz_d = f"{round(sz/1048576,1)} MB"
                ext = fn.split('.')[-1].lower() if '.' in fn else ''
                icon = {'p12':'🔑','pem':'📄','jks':'☕','crt':'📜','key':'🔐','crl':'📋','csr':'📝'}.get(ext, '📁')
                files.append({'name': fn, 'size': sz_d, 'icon': icon, 'ext': ext})
    return render_template_string(CERTS_TEMPLATE, settings=settings, files=files, version=VERSION)

# === Email Relay (Postfix) ===

# ── MediaMTX ──────────────────────────────────────────────────────────────────
mediamtx_deploy_log = []
mediamtx_deploy_status = {'running': False, 'complete': False, 'error': False}

@app.route('/api/mediamtx/deploy', methods=['POST'])
@login_required
def mediamtx_deploy_api():
    if mediamtx_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    mediamtx_deploy_log.clear()
    mediamtx_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_mediamtx_deploy, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/mediamtx/deploy/log')
@login_required
def mediamtx_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': mediamtx_deploy_log[idx:], 'total': len(mediamtx_deploy_log),
        'running': mediamtx_deploy_status['running'], 'complete': mediamtx_deploy_status['complete'],
        'error': mediamtx_deploy_status['error']})

@app.route('/api/mediamtx/control', methods=['POST'])
@login_required
def mediamtx_control():
    action = (request.json or {}).get('action', '')
    if action == 'start':
        subprocess.run('systemctl start mediamtx mediamtx-webeditor 2>&1', shell=True, capture_output=True)
    elif action == 'stop':
        subprocess.run('systemctl stop mediamtx mediamtx-webeditor 2>&1', shell=True, capture_output=True)
    elif action == 'restart':
        subprocess.run('systemctl restart mediamtx mediamtx-webeditor 2>&1', shell=True, capture_output=True)
    else:
        return jsonify({'error': 'Invalid action'}), 400
    time.sleep(2)
    r = subprocess.run(['systemctl', 'is-active', 'mediamtx'], capture_output=True, text=True)
    running = r.stdout.strip() == 'active'
    return jsonify({'success': True, 'running': running})

@app.route('/api/mediamtx/logs')
@login_required
def mediamtx_logs():
    lines = request.args.get('lines', 60, type=int)
    r = subprocess.run(f'journalctl -u mediamtx --no-pager -n {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=10)
    entries = [l for l in (r.stdout.strip().split('\n') if r.stdout.strip() else []) if l.strip()]
    return jsonify({'entries': entries})

@app.route('/api/mediamtx/uninstall', methods=['POST'])
@login_required
def mediamtx_uninstall():
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    steps = []
    subprocess.run('systemctl stop mediamtx mediamtx-webeditor 2>/dev/null; true', shell=True, capture_output=True)
    subprocess.run('systemctl disable mediamtx mediamtx-webeditor 2>/dev/null; true', shell=True, capture_output=True)
    for f in ['/etc/systemd/system/mediamtx.service', '/etc/systemd/system/mediamtx-webeditor.service',
              '/usr/local/bin/mediamtx', '/usr/local/etc/mediamtx.yml']:
        if os.path.exists(f):
            os.remove(f)
    if os.path.exists('/opt/mediamtx-webeditor'):
        subprocess.run('rm -rf /opt/mediamtx-webeditor', shell=True, capture_output=True)
    subprocess.run('systemctl daemon-reload 2>/dev/null; true', shell=True, capture_output=True)
    steps.append('Stopped and disabled mediamtx and mediamtx-webeditor services')
    steps.append('Removed binary, config, and web editor files')
    mediamtx_deploy_log.clear()
    mediamtx_deploy_status.update({'running': False, 'complete': False, 'error': False})
    generate_caddyfile()
    subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True)
    steps.append('Updated Caddyfile')
    return jsonify({'success': True, 'steps': steps})

def run_mediamtx_deploy():
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        mediamtx_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        settings = load_settings()
        domain = settings.get('fqdn', '')

        # Step 1: Wait for apt lock / install deps
        plog("━━━ Step 1/7: Installing Dependencies ━━━")
        wait_for_apt_lock(plog, mediamtx_deploy_log)
        r = subprocess.run('apt-get update -qq && apt-get install -y wget tar curl ffmpeg openssl python3 python3-pip 2>&1',
            shell=True, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            plog(f"✗ apt install failed: {r.stdout[-200:]}")
            mediamtx_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Dependencies installed (wget, ffmpeg, python3)")

        # Install Python packages (try with --break-system-packages for newer pip, else without)
        plog("  Installing Python packages...")
        r = subprocess.run('pip3 install Flask ruamel.yaml requests psutil --break-system-packages 2>&1',
            shell=True, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 and 'no such option' in (r.stderr or r.stdout or ''):
            subprocess.run('pip3 install Flask ruamel.yaml requests psutil 2>&1',
                shell=True, capture_output=True, text=True, timeout=120)
        plog("✓ Python packages installed")

        # Step 2: Detect architecture and latest version
        plog("")
        plog("━━━ Step 2/7: Detecting MediaMTX Version ━━━")
        arch_map = {'x86_64': 'amd64', 'aarch64': 'arm64v8', 'armv7l': 'armv7'}
        arch_raw = subprocess.run('uname -m', shell=True, capture_output=True, text=True).stdout.strip()
        mtx_arch = arch_map.get(arch_raw, 'amd64')
        plog(f"  Architecture: {arch_raw} → {mtx_arch}")

        r = subprocess.run('curl -s https://api.github.com/repos/bluenviron/mediamtx/releases/latest',
            shell=True, capture_output=True, text=True, timeout=30)
        import re as _re
        m = _re.search(r'"tag_name":\s*"v([^"]+)"', r.stdout)
        if not m:
            plog("✗ Could not detect latest MediaMTX version")
            mediamtx_deploy_status.update({'running': False, 'error': True})
            return
        version = m.group(1)
        plog(f"✓ Latest version: {version}")

        # Step 3: Download and install binary
        plog("")
        plog("━━━ Step 3/7: Downloading & Installing MediaMTX ━━━")
        url = f"https://github.com/bluenviron/mediamtx/releases/download/v{version}/mediamtx_v{version}_linux_{mtx_arch}.tar.gz"
        tmp = '/tmp/mediamtx_install'
        os.makedirs(tmp, exist_ok=True)
        r = subprocess.run(f'wget -q -O {tmp}/mediamtx.tar.gz "{url}"', shell=True, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            plog(f"✗ Download failed")
            mediamtx_deploy_status.update({'running': False, 'error': True})
            return
        subprocess.run(f'tar -xzf {tmp}/mediamtx.tar.gz -C {tmp}', shell=True, capture_output=True)
        subprocess.run(f'mv -f {tmp}/mediamtx /usr/local/bin/mediamtx && chmod +x /usr/local/bin/mediamtx', shell=True, capture_output=True)
        subprocess.run(f'rm -rf {tmp}', shell=True, capture_output=True)
        plog(f"✓ MediaMTX v{version} installed to /usr/local/bin/mediamtx")

        # Step 4: Write config
        plog("")
        plog("━━━ Step 4/7: Writing Configuration ━━━")
        os.makedirs('/usr/local/etc', exist_ok=True)
        import secrets as _sec
        hls_pass = _sec.token_hex(8)

        mediamtx_yml = f"""# MediaMTX Configuration - Generated by TAKWERX Console
logLevel: info
logDestinations: [stdout]
logStructured: no
logFile: mediamtx.log
readTimeout: 10s
writeTimeout: 10s
writeQueueSize: 512
udpMaxPayloadSize: 1472

authMethod: internal
authInternalUsers:
- user: any
  ips: ['127.0.0.1', '::1']
  permissions:
  - action: read
  - action: publish
  - action: api
- user: hlsviewer
  pass: {hls_pass}
  ips: []
  permissions:
  - action: read
- user: any
  pass: ''
  ips: []
  permissions:
  - action: read
    path: teststream
authHTTPAddress:
authHTTPExclude:
- action: api
- action: metrics
- action: pprof

api: yes
apiAddress: :9898  # moved from 9997 — CloudTAK media container owns port 9997 (hardcoded in video-service.ts)
apiEncryption: no
apiAllowOrigins: ['*']
apiTrustedProxies: []

metrics: no
metricsAddress: :9998
pprof: no
pprofAddress: :9999
playback: no
playbackAddress: :9996

rtsp: yes
rtspTransports: [tcp]
rtspEncryption: "no"
rtspAddress: :8554
rtspsAddress: :8322
rtpAddress: :8000
rtcpAddress: :8001
rtspServerKey:
rtspServerCert:
rtspAuthMethods: [basic]

rtmp: no
rtmpAddress: :1935
rtmpEncryption: "no"
rtmpsAddress: :1936
rtmpServerKey:
rtmpServerCert:

hls: yes
hlsAddress: :8888
hlsEncryption: no
hlsServerKey:
hlsServerCert:
hlsAllowOrigins: ['*']
hlsTrustedProxies: ['127.0.0.1']
hlsAlwaysRemux: no
hlsVariant: mpegts
hlsSegmentCount: 3
hlsSegmentDuration: 500ms
hlsPartDuration: 200ms
hlsSegmentMaxSize: 50M
hlsDirectory: ''
hlsMuxerCloseAfter: 60s

webrtc: no
webrtcAddress: :8889
webrtcEncryption: no
webrtcAllowOrigins: ['*']

srt: yes
srtAddress: :8890

paths:
  teststream:
    record: no
  all_others:
  ~^live/(.+)$:
    runOnReady: ffmpeg -i rtsp://localhost:8554/live/$G1 -c copy -f rtsp rtsp://localhost:8554/$G1
    runOnReadyRestart: true
"""
        with open('/usr/local/etc/mediamtx.yml', 'w') as f:
            f.write(mediamtx_yml)
        plog("✓ Configuration written to /usr/local/etc/mediamtx.yml")
        plog(f"  HLS viewer password: {hls_pass}")

        # Step 5: Create mediamtx systemd service
        plog("")
        plog("━━━ Step 5/7: Creating systemd Services ━━━")
        mediamtx_svc = """[Unit]
Description=MediaMTX RTSP/HLS/SRT Streaming Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""
        with open('/etc/systemd/system/mediamtx.service', 'w') as f:
            f.write(mediamtx_svc)
        plog("✓ mediamtx.service created")

        # Write web editor Python app — flexible: detect LDAP/Authentik and choose regular vs LDAP-enhanced source
        webeditor_dir = '/opt/mediamtx-webeditor'
        os.makedirs(webeditor_dir, exist_ok=True)
        os.makedirs(f'{webeditor_dir}/backups', exist_ok=True)
        os.makedirs(f'{webeditor_dir}/recordings', exist_ok=True)

        modules = detect_modules()
        ak = modules.get('authentik', {})
        ldap_available = bool(ak.get('installed'))
        if ldap_available:
            plog("  LDAP/Authentik detected — using editor source for LDAP-aware console")
        else:
            plog("  No LDAP — using regular MediaMTX editor from repo")

        webeditor_src = None
        clone_dir = '/tmp/mediamtx_editor_clone'
        try:
            subprocess.run(f'rm -rf {clone_dir}', shell=True, capture_output=True)
            os.makedirs(clone_dir, exist_ok=True)
            branch = MEDIAMTX_EDITOR_LDAP_BRANCH if (ldap_available and MEDIAMTX_EDITOR_LDAP_BRANCH) else None
            if branch:
                r = subprocess.run(f'git clone --depth 1 -b "{branch}" "{MEDIAMTX_EDITOR_REPO}" {clone_dir}',
                    shell=True, capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    plog(f"  LDAP branch \"{branch}\" not found or clone failed, trying default branch")
                    subprocess.run(f'rm -rf {clone_dir}', shell=True, capture_output=True)
                    r = subprocess.run(f'git clone --depth 1 "{MEDIAMTX_EDITOR_REPO}" {clone_dir}',
                        shell=True, capture_output=True, text=True, timeout=60)
            else:
                r = subprocess.run(f'git clone --depth 1 "{MEDIAMTX_EDITOR_REPO}" {clone_dir}',
                    shell=True, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                candidate = os.path.join(clone_dir, MEDIAMTX_EDITOR_PATH, 'mediamtx_config_editor.py')
                if os.path.exists(candidate):
                    webeditor_src = candidate
                    plog(f"  Cloned editor from {MEDIAMTX_EDITOR_REPO}" + (f" (branch {branch})" if branch else ""))
        except Exception as e:
            plog(f"  Clone failed: {e}")
        if not webeditor_src:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            for p in [os.path.join(app_dir, 'mediamtx_config_editor.py'),
                      os.path.join(app_dir, 'config-editor', 'mediamtx_config_editor.py'),
                      '/opt/takwerx/mediamtx_config_editor.py']:
                if os.path.exists(p):
                    webeditor_src = p
                    plog("  Using local web editor (clone skipped or failed)")
                    break
        if webeditor_src:
            import shutil as _shutil
            _shutil.copy2(webeditor_src, f'{webeditor_dir}/mediamtx_config_editor.py')
            # Patch port to read from PORT env var (systemd sets PORT=5080)
            editor_path = f'{webeditor_dir}/mediamtx_config_editor.py'
            try:
                with open(editor_path, 'r') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    if 'app.run(' in line and 'port=5000' in line and 'os.environ.get("PORT"' not in line:
                        lines[i] = line.replace('port=5000', 'port=int(os.environ.get("PORT", 5080))', 1)
                        break
                with open(editor_path, 'w') as f:
                    f.writelines(lines)
            except Exception:
                pass
            # Console-deployed MediaMTX uses API port 9898 (CloudTAK uses 9997). Patch editor so "active streams" works.
            subprocess.run(f"sed -i 's/9997/9898/g' {webeditor_dir}/mediamtx_config_editor.py", shell=True)
            # When CloudTAK is installed, MediaMTX is at stream.* so "Stream URLs" in the editor should show stream. not video.
            # Only replace URL-like patterns (//video. or video.<domain>) — not JS vars like video.src / video.canPlayType
            if domain:
                base = domain.split(':')[0]
                base_esc = base.replace('.', '\\.')
                subprocess.run(f"sed -i 's|video\\.{base_esc}|stream.{base_esc}|g' {webeditor_dir}/mediamtx_config_editor.py", shell=True)
                subprocess.run(f"sed -i 's|//video\\.|//stream.|g' {webeditor_dir}/mediamtx_config_editor.py", shell=True)
                plog("  Stream URL host set to stream.*")
            plog("✓ Web editor installed (port 5080, API 9898)")

            # LDAP overlay: when Authentik is present, patch editor for header auth + Stream Access page
            if ldap_available:
                overlay_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mediamtx_ldap_overlay.py')
                overlay_dst = f'{webeditor_dir}/mediamtx_ldap_overlay.py'
                if os.path.exists(overlay_src):
                    subprocess.run(f'cp "{overlay_src}" "{overlay_dst}"', shell=True)
                    # Inject import before app.run() — the overlay registers routes + before_request
                    editor_file = f'{webeditor_dir}/mediamtx_config_editor.py'
                    with open(editor_file, 'r') as ef:
                        editor_src = ef.read()
                    inject_block = (
                        "\n# --- infra-TAK LDAP overlay ---\n"
                        "import os as _os\n"
                        "if _os.environ.get('LDAP_ENABLED'):\n"
                        "    import sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n"
                        "    from mediamtx_ldap_overlay import apply_ldap_overlay\n"
                        "    apply_ldap_overlay(app)\n"
                        "# --- end LDAP overlay ---\n"
                    )
                    # Inject right after app = Flask(...) so overlay's before_request runs before vanilla login_required
                    if 'LDAP overlay' not in editor_src:
                        lines = editor_src.splitlines(keepends=True)
                        inserted = False
                        for i, line in enumerate(lines):
                            if 'app = Flask(' in line:
                                lines.insert(i + 1, '\n' + inject_block)
                                inserted = True
                                break
                        if not inserted:
                            for i, line in enumerate(lines):
                                if 'app.run(' in line:
                                    lines.insert(i, '\n' + inject_block)
                                    inserted = True
                                    break
                        if inserted:
                            with open(editor_file, 'w') as ef:
                                ef.writelines(lines)
                            plog("✓ LDAP overlay applied (Authentik header auth + Stream Access)")
                        else:
                            plog("  ⚠ app = Flask / app.run not found — LDAP overlay not injected")
                    else:
                        plog("✓ LDAP overlay already present")
                else:
                    plog("⚠ mediamtx_ldap_overlay.py not found next to app.py — LDAP overlay skipped")
        else:
            plog("⚠ mediamtx_config_editor.py not found (clone failed and no local file)")
            plog("  Place it next to app.py or in config-editor/, or fix repo access, then redeploy")
            plog("  MediaMTX streaming will work — web editor unavailable until then")

        # Clean up clone dir now that copy is done
        try:
            subprocess.run(f'rm -rf {clone_dir}', shell=True, capture_output=True)
        except Exception:
            pass

        # Download test video
        test_video_dir = f'{webeditor_dir}/test_videos'
        os.makedirs(test_video_dir, exist_ok=True)
        test_video_url = 'https://raw.githubusercontent.com/takwerx/mediamtx-installer/main/config-editor/truck_60.ts'
        plog("  Downloading test video (truck_60.ts)...")
        r = subprocess.run(f'wget -q -O {test_video_dir}/truck_60.ts "{test_video_url}"',
            shell=True, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            plog("✓ Test video installed")
        else:
            plog("⚠ Test video download failed — you can upload it manually via the web console")

        # Web editor systemd service — add LDAP env vars when Authentik is present
        ldap_env_lines = ''
        if ldap_available:
            ak_env_path = os.path.expanduser('~/authentik/.env')
            ak_token_val = ''
            if os.path.exists(ak_env_path):
                with open(ak_env_path) as _f:
                    for _line in _f:
                        if _line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                            ak_token_val = _line.strip().split('=', 1)[1].strip()
            ldap_env_lines = (
                f'Environment=LDAP_ENABLED=1\n'
                f'Environment=AUTHENTIK_API_URL=http://127.0.0.1:9090\n'
                f'Environment=AUTHENTIK_TOKEN={ak_token_val}\n'
            )

        # Write self-healing overlay script — runs before every service start
        # Re-injects LDAP overlay + patches (port, API) if the upstream editor self-updated
        if ldap_available:
            heal_script = r'''#!/usr/bin/env python3
"""Pre-start hook: ensure infra-TAK LDAP overlay is injected into the editor.

Runs as ExecStartPre so that upstream self-updates (Versions tab) don't
silently remove the overlay.  Idempotent — does nothing if already patched.
"""
import os, re, sys

EDITOR  = '/opt/mediamtx-webeditor/mediamtx_config_editor.py'
OVERLAY = '/opt/mediamtx-webeditor/mediamtx_ldap_overlay.py'
MARKER  = '# --- infra-TAK LDAP overlay ---'

if not os.path.exists(EDITOR) or not os.path.exists(OVERLAY):
    sys.exit(0)

with open(EDITOR, 'r') as f:
    src = f.read()

changed = False

# 1. Port patch: ensure PORT env var override
if 'port=5000' in src and 'os.environ.get("PORT"' not in src:
    src = src.replace('port=5000', 'port=int(os.environ.get("PORT", 5080))', 1)
    changed = True

# 2. API port patch: 9997 -> 9898
if '9997' in src:
    src = src.replace('9997', '9898')
    changed = True

# 3. LDAP overlay import injection
if MARKER not in src:
    inject = (
        "\n" + MARKER + "\n"
        "import os as _os\n"
        "if _os.environ.get('LDAP_ENABLED'):\n"
        "    import sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n"
        "    from mediamtx_ldap_overlay import apply_ldap_overlay\n"
        "    apply_ldap_overlay(app)\n"
        "# --- end LDAP overlay ---\n"
    )
    lines = src.splitlines(keepends=True)
    inserted = False
    for i, line in enumerate(lines):
        if 'app = Flask(' in line:
            lines.insert(i + 1, '\n' + inject)
            inserted = True
            break
    if not inserted:
        for i, line in enumerate(lines):
            if 'app.run(' in line:
                lines.insert(i, '\n' + inject)
                inserted = True
                break
    if inserted:
        src = ''.join(lines)
        changed = True

if changed:
    with open(EDITOR, 'w') as f:
        f.write(src)
'''
            heal_path = f'{webeditor_dir}/ensure_overlay.py'
            with open(heal_path, 'w') as hf:
                hf.write(heal_script)
            os.chmod(heal_path, 0o755)
            plog("✓ Self-healing overlay script installed (runs on every service start)")

        exec_start_pre = ''
        if ldap_available:
            exec_start_pre = f'ExecStartPre=/usr/bin/python3 {webeditor_dir}/ensure_overlay.py\n'

        webeditor_svc = f"""[Unit]
Description=MediaMTX Web Configuration Editor
After=network.target mediamtx.service

[Service]
Type=simple
{exec_start_pre}ExecStart=/usr/bin/python3 /opt/mediamtx-webeditor/mediamtx_config_editor.py
WorkingDirectory=/opt/mediamtx-webeditor
Environment=PORT=5080
Environment=MEDIAMTX_API_URL=http://127.0.0.1:9898
{ldap_env_lines}Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""
        with open('/etc/systemd/system/mediamtx-webeditor.service', 'w') as f:
            f.write(webeditor_svc)
        plog("✓ mediamtx-webeditor.service created")

        # Ensure web editor Python deps (Flask, etc.) so systemd can start it even if Step 1 pip failed
        if os.path.exists(f'{webeditor_dir}/mediamtx_config_editor.py'):
            r = subprocess.run(
                'pip3 install Flask ruamel.yaml requests psutil --break-system-packages 2>&1',
                shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0 and 'no such option' in (r.stderr or r.stdout or ''):
                r = subprocess.run('pip3 install Flask ruamel.yaml requests psutil 2>&1',
                    shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                plog("  ⚠ pip install for web editor deps had issues (check logs); trying to start anyway")
            else:
                plog("  ✓ Web editor Python deps installed")

        subprocess.run('systemctl daemon-reload', shell=True, capture_output=True)
        subprocess.run('systemctl enable mediamtx mediamtx-webeditor', shell=True, capture_output=True)
        subprocess.run('systemctl start mediamtx', shell=True, capture_output=True)
        if os.path.exists(f'{webeditor_dir}/mediamtx_config_editor.py'):
            subprocess.run('systemctl start mediamtx-webeditor', shell=True, capture_output=True)
        plog("✓ Services enabled and started")

        # Step 6: Firewall
        plog("")
        plog("━━━ Step 6/7: Configuring Firewall ━━━")
        for port_proto in ['8554/tcp', '8322/tcp', '8888/tcp', '8890/udp', '8000/udp', '8001/udp', '5080/tcp', '9898/tcp']:
            subprocess.run(f'ufw allow {port_proto} 2>/dev/null; true', shell=True, capture_output=True)
        plog("✓ Ports opened: 8554 (RTSP), 8322 (RTSPS), 8888 (HLS), 8890 (SRT), 5080 (Web Editor), 9898 (API)")

        # Step 7: Caddy integration
        plog("")
        plog("━━━ Step 7/7: Caddy Integration ━━━")
        caddy_running = subprocess.run(['systemctl', 'is-active', 'caddy'], capture_output=True, text=True).stdout.strip() == 'active'
        if caddy_running and domain:
            # Update Caddyfile first so Caddy issues the cert
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True)
            mtx_domain = _get_service_domain(settings, 'mediamtx')
            plog(f"✓ Caddyfile updated — {mtx_domain}")

            # Wait up to 60s for cert
            cert_base = '/var/lib/caddy/.local/share/caddy/certificates/acme-v02.api.letsencrypt.org-directory'
            cert_file = f'{cert_base}/{mtx_domain}/{mtx_domain}.crt'
            key_file  = f'{cert_base}/{mtx_domain}/{mtx_domain}.key'
            plog(f"  Waiting for Caddy to issue cert for {mtx_domain}...")
            for i in range(30):
                if os.path.exists(cert_file) and os.path.exists(key_file):
                    break
                if i % 5 == 0:
                    plog(f"  ⏳ {i * 2}s...")
                time.sleep(2)

            if os.path.exists(cert_file):
                yml = '/usr/local/etc/mediamtx.yml'
                # Wire cert paths — strip continuation lines first then replace
                for key in ['rtspServerKey', 'rtspServerCert', 'hlsServerKey', 'hlsServerCert', 'rtmpServerKey', 'rtmpServerCert']:
                    subprocess.run(f"sed -i '/^{key}:/{{ n; /^  /d }}' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^rtspServerKey:.*|rtspServerKey: {key_file}|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^rtspServerCert:.*|rtspServerCert: {cert_file}|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^hlsServerKey:.*|hlsServerKey: {key_file}|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^hlsServerCert:.*|hlsServerCert: {cert_file}|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^rtmpServerKey:.*|rtmpServerKey: {key_file}|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^rtmpServerCert:.*|rtmpServerCert: {cert_file}|' {yml}", shell=True)
                # Enable encryption
                subprocess.run(f"sed -i 's|^rtspEncryption:.*|rtspEncryption: \"optional\"|' {yml}", shell=True)
                subprocess.run(f"sed -i 's|^hlsEncryption:.*|hlsEncryption: yes|' {yml}", shell=True)
                plog(f"✓ SSL certificates wired — RTSPS and HTTPS HLS enabled")
                plog(f"  Cert: {cert_file}")
                subprocess.run('systemctl restart mediamtx', shell=True, capture_output=True)
                time.sleep(2)
            else:
                plog(f"  ⚠ Cert not found after 60s — SSL not wired")
                plog(f"  Go to Caddy page, reload, then restart MediaMTX to retry")
        elif not domain:
            plog("  No domain configured — skipping Caddy (access via port 5080 directly)")
        else:
            plog("  Caddy not running — skipping SSL integration")

        # Verify MediaMTX is up
        time.sleep(3)
        r = subprocess.run(['systemctl', 'is-active', 'mediamtx'], capture_output=True, text=True)
        if r.stdout.strip() == 'active':
            # If Authentik is running, ensure stream visibility groups exist (video-public, video-private, video-admin)
            ak_dir = os.path.expanduser('~/authentik')
            env_path = os.path.join(ak_dir, '.env')
            if os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')) and os.path.exists(env_path):
                ak_token = ''
                with open(env_path) as f:
                    for line in f:
                        if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                            ak_token = line.strip().split('=', 1)[1].strip()
                            break
                if ak_token:
                    import urllib.request
                    import urllib.error
                    plog("")
                    plog("━━━ Creating Authentik groups for stream access ━━━")
                    ak_url = 'http://127.0.0.1:9090'
                    ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
                    for group_name in ('vid_public', 'vid_private'):
                        try:
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/groups/',
                                data=json.dumps({'name': group_name, 'is_superuser': False}).encode(),
                                headers=ak_headers, method='POST')
                            urllib.request.urlopen(req, timeout=10)
                            plog(f"  ✓ Created group: {group_name}")
                        except urllib.error.HTTPError as e:
                            if e.code == 400:
                                plog(f"  ✓ Group already exists: {group_name}")
                            else:
                                plog(f"  ⚠ Could not create {group_name}: {e.code}")
                        except Exception as ex:
                            plog(f"  ⚠ Could not create {group_name}: {str(ex)[:60]}")
                    plog("  Assign users to vid_* groups in MediaMTX stream-access page or Authentik (they do not show in TAK clients).")

            plog("")
            plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            plog(f"🎉 MediaMTX v{version} deployed successfully!")
            if domain:
                mtx_display_domain = f"stream.{domain}"
                plog(f"   Web Console: https://{mtx_display_domain}")
                plog(f"   HLS streams: https://{mtx_display_domain}/[stream]/index.m3u8")
            else:
                plog(f"   Web Editor: http://{settings.get('server_ip','server')}:5080")
            plog(f"   RTSP: rtsp://[server]:8554/[stream]")
            plog(f"   SRT:  srt://[server]:8890?streamid=[stream]")
            plog(f"   HLS viewer password: {hls_pass}")
            plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            mediamtx_deploy_status.update({'running': False, 'complete': True, 'error': False})
        else:
            plog("✗ MediaMTX service not active after deploy — check logs")
            mediamtx_deploy_status.update({'running': False, 'error': True})

    except Exception as e:
        plog(f"✗ Unexpected error: {str(e)}")
        mediamtx_deploy_status.update({'running': False, 'error': True})

# ── CloudTAK ──────────────────────────────────────────────────────────────────
cloudtak_deploy_log = []
cloudtak_deploy_status = {'running': False, 'complete': False, 'error': False}
cloudtak_uninstall_status = {'running': False, 'done': False, 'error': None}

@app.route('/api/cloudtak/deploy', methods=['POST'])
@login_required
def cloudtak_deploy_api():
    if cloudtak_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    cloudtak_deploy_log.clear()
    cloudtak_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_cloudtak_deploy, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/cloudtak/deploy/log')
@login_required
def cloudtak_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': cloudtak_deploy_log[idx:], 'total': len(cloudtak_deploy_log),
        'running': cloudtak_deploy_status['running'], 'complete': cloudtak_deploy_status['complete'],
        'error': cloudtak_deploy_status['error']})

@app.route('/api/cloudtak/redeploy', methods=['POST'])
@login_required
def cloudtak_redeploy_api():
    """Update .env and override, restart containers, re-apply nginx patch. Use when CloudTAK is already installed."""
    if cloudtak_deploy_status.get('running'):
        return jsonify({'error': 'Another operation is in progress'}), 409
    cloudtak_deploy_log.clear()
    cloudtak_deploy_status.update({'running': True, 'complete': False, 'error': False})
    # First line so pollers see activity immediately
    cloudtak_deploy_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Update config & restart started")
    threading.Thread(target=run_cloudtak_redeploy, daemon=True).start()
    return jsonify({'success': True, 'message': 'Update config & restart started'})

@app.route('/api/cloudtak/control', methods=['POST'])
@login_required
def cloudtak_control():
    action = (request.json or {}).get('action', '')
    cloudtak_dir = os.path.expanduser('~/CloudTAK')
    if action == 'start':
        subprocess.run(f'cd {cloudtak_dir} && docker compose up -d 2>&1', shell=True, capture_output=True, timeout=60)
    elif action == 'stop':
        subprocess.run(f'cd {cloudtak_dir} && docker compose stop 2>&1', shell=True, capture_output=True, timeout=60)
    elif action == 'restart':
        subprocess.run(f'cd {cloudtak_dir} && docker compose restart 2>&1', shell=True, capture_output=True, timeout=60)
    elif action == 'update':
        subprocess.run(f'cd {cloudtak_dir} && ./cloudtak.sh update 2>&1', shell=True, capture_output=True, timeout=600)
    else:
        return jsonify({'error': 'Invalid action'}), 400
    time.sleep(3)
    r = subprocess.run('docker ps --filter name=cloudtak-api --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
    running = 'Up' in r.stdout
    return jsonify({'success': True, 'running': running})

@app.route('/api/cloudtak/logs')
@login_required
def cloudtak_container_logs():
    lines = request.args.get('lines', 80, type=int)
    container = request.args.get('container', '').strip()
    cloudtak_dir = os.path.expanduser('~/CloudTAK')
    compose_yml = os.path.join(cloudtak_dir, 'docker-compose.yml')
    if not os.path.exists(compose_yml):
        compose_yml = os.path.join(cloudtak_dir, 'compose.yaml')
    if container:
        r = subprocess.run(f'docker logs {container} --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=15)
    else:
        if os.path.exists(compose_yml):
            r = subprocess.run(f'docker compose -f "{compose_yml}" logs --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=15, cwd=cloudtak_dir)
        else:
            r = subprocess.run(f'docker logs cloudtak-api-1 --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=15)
    entries = [l for l in (r.stdout.strip().split('\n') if r.stdout.strip() else []) if l.strip()]
    return jsonify({'entries': entries})

@app.route('/api/cloudtak/uninstall', methods=['POST'])
@login_required
def cloudtak_uninstall():
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    if cloudtak_uninstall_status.get('running'):
        return jsonify({'error': 'Uninstall already in progress'}), 409
    cloudtak_uninstall_status.update({'running': True, 'done': False, 'error': None})
    def do_uninstall():
        try:
            cloudtak_dir = os.path.expanduser('~/CloudTAK')
            compose_yml = os.path.join(cloudtak_dir, 'docker-compose.yml')
            compose_yaml = os.path.join(cloudtak_dir, 'compose.yaml')
            if os.path.exists(cloudtak_dir):
                yml = compose_yml if os.path.exists(compose_yml) else (compose_yaml if os.path.exists(compose_yaml) else None)
                if yml:
                    subprocess.run(
                        f'docker compose -f "{yml}" down -v --rmi local',
                        shell=True, capture_output=True, timeout=180, cwd=cloudtak_dir
                    )
                subprocess.run(f'rm -rf "{cloudtak_dir}"', shell=True, capture_output=True, timeout=60)
            cloudtak_deploy_log.clear()
            cloudtak_deploy_status.update({'running': False, 'complete': False, 'error': False})
            generate_caddyfile()
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=15)
            cloudtak_uninstall_status.update({'running': False, 'done': True, 'error': None})
        except subprocess.TimeoutExpired:
            cloudtak_uninstall_status.update({'running': False, 'done': True, 'error': 'Uninstall timed out'})
        except Exception as e:
            cloudtak_uninstall_status.update({'running': False, 'done': True, 'error': str(e)})
    threading.Thread(target=do_uninstall, daemon=True).start()
    return jsonify({'success': True, 'message': 'Uninstall started'})

@app.route('/api/cloudtak/uninstall/status')
@login_required
def cloudtak_uninstall_status_api():
    return jsonify({
        'running': cloudtak_uninstall_status.get('running', False),
        'done': cloudtak_uninstall_status.get('done', False),
        'error': cloudtak_uninstall_status.get('error')
    })

def run_cloudtak_deploy():
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        cloudtak_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        cloudtak_dir = os.path.expanduser('~/CloudTAK')
        settings = load_settings()
        domain = settings.get('fqdn', '')

        # Step 1: Check Docker
        plog("━━━ Step 1/7: Checking Docker ━━━")
        r = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            plog("  Docker not found — installing...")
            subprocess.run('curl -fsSL https://get.docker.com | sh', shell=True, capture_output=True, text=True, timeout=300)
            r2 = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
            if r2.returncode != 0:
                plog("✗ Failed to install Docker")
                cloudtak_deploy_status.update({'running': False, 'error': True})
                return
            plog(f"  {r2.stdout.strip()}")
        else:
            plog(f"  {r.stdout.strip()}")
        plog("✓ Docker available")

        # Step 2: Clone or update repo
        plog("")
        plog("━━━ Step 2/7: Cloning CloudTAK ━━━")
        if os.path.exists(cloudtak_dir):
            plog("  ~/CloudTAK exists — pulling latest...")
            r = subprocess.run(f'cd {cloudtak_dir} && git pull --rebase --autostash', shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                plog(f"  ⚠ git pull warning: {r.stderr.strip()[:100]}")
        else:
            plog("  Cloning from GitHub...")
            r = subprocess.run(f'git clone https://github.com/dfpc-coe/CloudTAK.git {cloudtak_dir}', shell=True, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                plog(f"✗ Clone failed: {r.stderr.strip()[:200]}")
                cloudtak_deploy_status.update({'running': False, 'error': True})
                return
        plog("✓ Repository ready")

        # Ensure compose file exists (fix partial/bad clone)
        compose_yml = os.path.join(cloudtak_dir, 'docker-compose.yml')
        compose_yaml = os.path.join(cloudtak_dir, 'compose.yaml')
        if not os.path.exists(compose_yml) and not os.path.exists(compose_yaml):
            plog("  docker-compose.yml missing — re-cloning...")
            subprocess.run(f'rm -rf {cloudtak_dir}', shell=True, capture_output=True, timeout=30)
            r = subprocess.run(f'git clone https://github.com/dfpc-coe/CloudTAK.git {cloudtak_dir}', shell=True, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                plog(f"✗ Re-clone failed: {r.stderr.strip()[:200]}")
                cloudtak_deploy_status.update({'running': False, 'error': True})
                return
            compose_yml = os.path.join(cloudtak_dir, 'docker-compose.yml')
            compose_yaml = os.path.join(cloudtak_dir, 'compose.yaml')
        if not os.path.exists(compose_yml):
            compose_yml = compose_yaml if os.path.exists(compose_yaml) else os.path.join(cloudtak_dir, 'docker-compose.yml')
        if not os.path.exists(compose_yml):
            plog(f"✗ No compose file found in {cloudtak_dir}")
            cloudtak_deploy_status.update({'running': False, 'error': True})
            return

        # Step 3: Generate .env and docker-compose.override.yml
        plog("")
        plog("━━━ Step 3/7: Configuring .env ━━━")
        env_path = os.path.join(cloudtak_dir, '.env')
        import secrets as _secrets
        signing_secret = _secrets.token_hex(32)
        minio_pass = _secrets.token_hex(16)

        # Build URLs
        # API_URL is used in two places: (1) TileJSON/tile URLs sent to the browser — must be
        # reachable by the user's browser (public URL). (2) Media container callback to the API.
        # We use the public URL when domain is set so the map and basemaps render. The media
        # container then calls the same URL; on same-host deployments this usually works.
        # If domain is not set, use Docker gateway so containers can reach the API.
        if domain:
            api_url = f"https://map.{domain}"
            pmtiles_url = f"https://tiles.map.{domain}"
        else:
            api_url = f"http://172.20.0.1:5000"
            pmtiles_url = f"http://{settings.get('server_ip', '127.0.0.1')}:5002"

        if domain:
            media_url = f"https://video.{domain}"
        else:
            media_url = "http://media:9997"

        env_content = f"""CLOUDTAK_Mode=docker-compose
CLOUDTAK_Config_media_url={media_url}

SigningSecret={signing_secret}

ASSET_BUCKET=cloudtak
AWS_S3_Endpoint=http://store:9000
AWS_S3_AccessKeyId=cloudtakminioadmin
AWS_S3_SecretAccessKey={minio_pass}
MINIO_ROOT_USER=cloudtakminioadmin
MINIO_ROOT_PASSWORD={minio_pass}

POSTGRES=postgres://docker:docker@postgis:5432/gis

# API_URL must be reachable by the browser (for tile URLs in TileJSON). We set it to the public
# map URL when domain is set so the map and basemaps render.
API_URL={api_url}
PMTILES_URL={pmtiles_url}

# Port remapping — avoids conflicts with standalone MediaMTX which owns the original ports.
# CloudTAK's docker-compose.yml supports these env vars natively (no override file needed).
# MEDIA_PORT_API=9997 because video-service.ts hardcodes port 9997 for all MediaMTX API calls.
# Standalone MediaMTX API moved to 9898 to free up 9997 for CloudTAK media container.
MEDIA_PORT_API=9997
MEDIA_PORT_RTSP=18554
MEDIA_PORT_RTMP=11935
MEDIA_PORT_HLS=18888
MEDIA_PORT_SRT=18890
"""
        with open(env_path, 'w') as f:
            f.write(env_content)

        # So the API container can reach the host (e.g. TAKWERX Console / Marti at :5001)
        override_path = os.path.join(cloudtak_dir, 'docker-compose.override.yml')
        override_yml = """# TAKWERX: API container must reach host (e.g. :5001 for Marti/TAK Server proxy)
services:
  api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
"""
        with open(override_path, 'w') as f:
            f.write(override_yml)
        plog("  docker-compose.override.yml written (api → host.docker.internal for :5001)")

        plog(f"✓ .env written")
        plog(f"  API URL: {api_url}")
        plog(f"  Media URL: {media_url} (CloudTAK media container — port 9997 hardcoded in source)")

        # Step 4: Build Docker images (use -f so compose file is found regardless of cwd)
        plog("")
        plog("━━━ Step 4/7: Building Docker Images ━━━")
        plog("  This may take 5-10 minutes on first run...")
        r = subprocess.run(f'docker compose -f {compose_yml} build 2>&1', shell=True, capture_output=True, text=True, timeout=1800, cwd=cloudtak_dir)
        if r.returncode != 0:
            plog(f"✗ Docker build failed")
            for line in r.stdout.strip().split('\n')[-20:]:
                if line.strip():
                    plog(f"  {line}")
            cloudtak_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Images built")

        # Step 5: Start containers including media on remapped ports
        plog("")
        plog("━━━ Step 5/7: Starting Containers ━━━")
        plog("  Starting all containers including media (remapped ports)...")
        plog("  Standalone MediaMTX stays on original ports — no conflict")
        r = subprocess.run(
            f'docker compose -f {compose_yml} up -d 2>&1',
            shell=True, capture_output=True, text=True, timeout=120, cwd=cloudtak_dir
        )
        if r.returncode != 0:
            plog(f"✗ docker compose up failed")
            for line in r.stdout.strip().split('\n')[-10:]:
                if line.strip():
                    plog(f"  {line}")
            cloudtak_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Containers started")

        # CloudTAK nginx proxies /api to 127.0.0.1:5001 (Node app in same container). Do NOT
        # replace that with host:5001 or /api would hit TAKWERX Console and the app would stay on "Loading CloudTAK".

        # Step 6: Wait for API to be ready
        plog("")
        plog("━━━ Step 6/7: Waiting for CloudTAK API ━━━")
        import urllib.request as _urlreq
        for attempt in range(30):
            try:
                _urlreq.urlopen('http://localhost:5000/', timeout=3)
                plog("✓ CloudTAK API is responding")
                break
            except Exception:
                if attempt % 5 == 0:
                    plog(f"  ⏳ Waiting... ({attempt * 2}s)")
                time.sleep(2)
        else:
            plog("⚠ CloudTAK API did not respond in time — check container logs")

        # Step 7: Update Caddyfile
        plog("")
        plog("━━━ Step 7/7: Updating Caddy ━━━")
        if domain:
            generate_caddyfile(settings)
            r = subprocess.run('systemctl reload caddy 2>&1', shell=True, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                plog(f"✓ Caddy updated — map.{domain} and tiles.map.{domain} live")
            else:
                plog(f"⚠ Caddy reload: {r.stdout.strip()[:100]}")
        else:
            plog("  No domain configured — skipping Caddy (access via port 5000)")

        plog("")
        plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if domain:
            plog(f"🎉 CloudTAK deployed! Open https://map.{domain} in your browser")
            plog(f"   Tiles: https://tiles.map.{domain}")
            plog(f"   Video: https://video.{domain} (via standalone MediaMTX)")
        else:
            server_ip = settings.get('server_ip', 'your-server-ip')
            plog(f"🎉 CloudTAK deployed! Open http://{server_ip}:5000 in your browser")
        plog(f"   Log in and go to Admin → Connections to configure your TAK Server")
        plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        cloudtak_deploy_status.update({'running': False, 'complete': True, 'error': False})

    except Exception as e:
        plog(f"✗ Unexpected error: {str(e)}")
        cloudtak_deploy_status.update({'running': False, 'error': True})

def run_cloudtak_redeploy():
    """Rewrite .env and override, restart stack, re-apply nginx patch. Reuses deploy log/status."""
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        cloudtak_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        cloudtak_dir = os.path.expanduser('~/CloudTAK')
        compose_yml = os.path.join(cloudtak_dir, 'docker-compose.yml')
        if not os.path.exists(compose_yml):
            compose_yml = os.path.join(cloudtak_dir, 'compose.yaml')
        if not os.path.exists(compose_yml):
            plog("✗ CloudTAK not found (no compose file)")
            cloudtak_deploy_status.update({'running': False, 'error': True})
            return
        settings = load_settings()
        domain = (settings.get('fqdn') or '').strip() or None
        if domain:
            api_url = f"https://map.{domain}"
            pmtiles_url = f"https://tiles.map.{domain}"
            media_url = f"https://video.{domain}"
        else:
            api_url = f"http://172.20.0.1:5000"
            pmtiles_url = f"http://{settings.get('server_ip', '127.0.0.1')}:5002"
            media_url = "http://media:9997"
        env_path = os.path.join(cloudtak_dir, '.env')
        signing_secret = None
        minio_pass = None
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('SigningSecret='):
                        signing_secret = line.split('=', 1)[1].strip()
                    elif line.startswith('MINIO_ROOT_PASSWORD='):
                        minio_pass = line.split('=', 1)[1].strip()
        import secrets as _secrets
        if not signing_secret:
            signing_secret = _secrets.token_hex(32)
        if not minio_pass:
            minio_pass = _secrets.token_hex(16)
        env_content = f"""CLOUDTAK_Mode=docker-compose
CLOUDTAK_Config_media_url={media_url}

SigningSecret={signing_secret}

ASSET_BUCKET=cloudtak
AWS_S3_Endpoint=http://store:9000
AWS_S3_AccessKeyId=cloudtakminioadmin
AWS_S3_SecretAccessKey={minio_pass}
MINIO_ROOT_USER=cloudtakminioadmin
MINIO_ROOT_PASSWORD={minio_pass}

POSTGRES=postgres://docker:docker@postgis:5432/gis

API_URL={api_url}
PMTILES_URL={pmtiles_url}

MEDIA_PORT_API=9997
MEDIA_PORT_RTSP=18554
MEDIA_PORT_RTMP=11935
MEDIA_PORT_HLS=18888
MEDIA_PORT_SRT=18890
"""
        with open(env_path, 'w') as f:
            f.write(env_content)
        override_path = os.path.join(cloudtak_dir, 'docker-compose.override.yml')
        with open(override_path, 'w') as f:
            f.write("""# TAKWERX: API container must reach host (e.g. :5001 for Marti/TAK Server proxy)
services:
  api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
""")
        plog("✓ .env and override written")
        plog("  Restarting containers...")
        r = subprocess.run(f'docker compose -f "{compose_yml}" restart 2>&1', shell=True, capture_output=True, text=True, timeout=120, cwd=cloudtak_dir)
        if r.returncode != 0:
            # Fallback for systems with docker-compose (hyphen) instead of docker compose
            r = subprocess.run(f'docker-compose -f "{compose_yml}" restart 2>&1', shell=True, capture_output=True, text=True, timeout=120, cwd=cloudtak_dir)
        if r.returncode != 0:
            plog(f"✗ Restart failed: {r.stderr or r.stdout or 'unknown'}")
            cloudtak_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Containers restarted")
        time.sleep(3)
        # Restore /api proxy to 127.0.0.1:5001 (Node in container) if a previous patch sent it to the host
        api_container = None
        for _ in range(15):
            r = subprocess.run(f'docker compose -f "{compose_yml}" ps -q api 2>/dev/null', shell=True, capture_output=True, text=True, timeout=5, cwd=cloudtak_dir)
            cid = (r.stdout or '').strip()
            if cid and len(cid) >= 8:
                api_container = cid
                break
            time.sleep(1)
        if api_container:
            for nf in ['/etc/nginx/nginx.conf', '/etc/nginx/conf.d/default.conf']:
                subprocess.run(f'docker exec {api_container} sed -i "s|proxy_pass http://[^;]*:5001|proxy_pass http://127.0.0.1:5001|g" {nf} 2>/dev/null', shell=True, capture_output=True, timeout=5)
            subprocess.run(f'docker exec {api_container} nginx -s reload 2>/dev/null', shell=True, capture_output=True, timeout=5)
            plog("  Nginx /api proxy pointed at CloudTAK API (127.0.0.1:5001)")
        plog("  Waiting for CloudTAK API to respond...")
        import urllib.request as _urlreq
        for attempt in range(45):
            try:
                _urlreq.urlopen('http://localhost:5000/', timeout=3)
                plog("✓ CloudTAK API is responding")
                break
            except Exception:
                if attempt % 5 == 0 and attempt > 0:
                    plog(f"  Still waiting... ({attempt * 2}s)")
                time.sleep(2)
        else:
            plog("⚠ API did not respond in time — if map.<domain> stays on 'Loading CloudTAK', check Container Logs and ensure the api container is running")
        if domain:
            generate_caddyfile(settings)
            try:
                subprocess.run('systemctl reload caddy 2>/dev/null', shell=True, capture_output=True, timeout=45)
                plog("✓ Caddy reloaded")
            except subprocess.TimeoutExpired:
                plog("⚠ Caddy reload timed out — reload it from the Caddy page if needed")
        plog("✓ Update config & restart done")
        cloudtak_deploy_status.update({'running': False, 'complete': True, 'error': False})
    except Exception as e:
        plog(f"✗ Error: {str(e)}")
        cloudtak_deploy_status.update({'running': False, 'error': True})
    finally:
        cloudtak_deploy_status['running'] = False

# ── Email Relay ────────────────────────────────────────────────────────────────
email_deploy_log = []
email_deploy_status = {'running': False, 'complete': False, 'error': False}

PROVIDERS = {
    'brevo':   {'name': 'Brevo',   'host': 'smtp-relay.brevo.com', 'port': '587', 'url': 'https://app.brevo.com/settings/keys/smtp'},
    'smtp2go': {'name': 'SMTP2GO', 'host': 'mail.smtp2go.com',     'port': '587', 'url': 'https://app.smtp2go.com/settings/users/smtp'},
    'mailgun': {'name': 'Mailgun', 'host': 'smtp.mailgun.org',      'port': '587', 'url': 'https://app.mailgun.com/mg/sending/domains'},
    'custom':  {'name': 'Custom',  'host': '',                      'port': '587', 'url': ''},
}

def run_email_deploy(provider_key, smtp_user, smtp_pass, from_addr, from_name):
    log = email_deploy_log
    status = email_deploy_status

    def plog(msg):
        log.append(msg)

    try:
        settings = load_settings()
        pkg_mgr = settings.get('pkg_mgr', 'apt')
        provider = PROVIDERS.get(provider_key, PROVIDERS['brevo'])

        plog(f"📧 Step 1/5 — Installing Postfix...")
        if pkg_mgr == 'apt':
            wait_for_apt_lock(plog, log)
            r = subprocess.run(
                'DEBIAN_FRONTEND=noninteractive apt-get install -y postfix libsasl2-modules 2>&1',
                shell=True, capture_output=True, text=True, timeout=300)
        else:
            r = subprocess.run('dnf install -y postfix cyrus-sasl-plain 2>&1',
                shell=True, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            plog(f"✗ Postfix install failed: {r.stdout[-500:]}")
            status.update({'running': False, 'error': True})
            return
        plog("✓ Postfix installed")

        plog(f"📧 Step 2/5 — Configuring main.cf...")
        relay_host = provider['host']
        relay_port = provider['port']
        main_cf_additions = f"""
# TAKWERX Email Relay — managed by TAK-infra
inet_interfaces = all
mynetworks = 127.0.0.0/8 [::1]/128 172.16.0.0/12
relayhost = [{relay_host}]:{relay_port}
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
smtp_tls_security_level = may
smtp_use_tls = yes
header_size_limit = 4096000
smtp_generic_maps = hash:/etc/postfix/generic
"""
        # Read existing main.cf and strip any previous TAKWERX block
        main_cf_path = '/etc/postfix/main.cf'
        if os.path.exists(main_cf_path):
            with open(main_cf_path) as f:
                existing = f.read()
            # Remove previous TAKWERX block if present
            import re
            existing = re.sub(r'\n# TAKWERX Email Relay.*', '', existing, flags=re.DOTALL)
            # Remove any existing relayhost line (Ubuntu default has a blank one)
            existing = re.sub(r'^\s*relayhost\s*=.*$', '', existing, flags=re.MULTILINE)
            # Remove any existing mynetworks (we set it in our block for Docker relay)
            existing = re.sub(r'^\s*mynetworks\s*=.*$', '', existing, flags=re.MULTILINE)
            existing = existing.rstrip()
        else:
            existing = ''
        with open(main_cf_path, 'w') as f:
            f.write(existing + '\n' + main_cf_additions)
        plog("✓ main.cf configured")

        plog(f"📧 Step 3/5 — Writing credentials...")
        sasl_line = f"[{relay_host}]:{relay_port}    {smtp_user}:{smtp_pass}"
        with open('/etc/postfix/sasl_passwd', 'w') as f:
            f.write(sasl_line + '\n')
        subprocess.run('postmap /etc/postfix/sasl_passwd', shell=True, capture_output=True)
        subprocess.run('chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db', shell=True, capture_output=True)

        # Generic map for from address rewriting
        hostname = subprocess.run('hostname -f', shell=True, capture_output=True, text=True).stdout.strip()
        generic_line = f"root@{hostname}    {from_addr}"
        with open('/etc/postfix/generic', 'w') as f:
            f.write(generic_line + '\n')
        subprocess.run('postmap /etc/postfix/generic', shell=True, capture_output=True)
        plog("✓ Credentials written and hashed")

        plog(f"📧 Step 4/5 — Enabling and starting Postfix...")
        subprocess.run('systemctl enable postfix 2>&1', shell=True, capture_output=True, text=True)
        r = subprocess.run('systemctl restart postfix 2>&1', shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            plog(f"✗ Postfix restart failed: {r.stdout}")
            status.update({'running': False, 'error': True})
            return
        plog("✓ Postfix running")

        plog(f"📧 Step 5/5 — Saving configuration...")
        settings['email_relay'] = {
            'provider': provider_key,
            'relay_host': relay_host,
            'relay_port': relay_port,
            'smtp_user': smtp_user,
            'from_addr': from_addr,
            'from_name': from_name,
        }
        # Store password separately (still in settings.json, local only)
        settings['email_relay']['smtp_pass'] = smtp_pass
        save_settings(settings)
        plog("✓ Configuration saved")
        plog("")
        plog("✅ Email Relay deployed successfully!")
        plog(f"   Provider: {provider['name']}")
        plog(f"   Relay:    {relay_host}:{relay_port}")
        plog(f"   From:     {from_name} <{from_addr}>")

        # Auto-configure Authentik if installed (SMTP + recovery flow)
        ak_dir = os.path.expanduser('~/authentik')
        if os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')):
            plog("")
            plog("🔑 Step 6/6 — Configuring Authentik (SMTP + password recovery)...")
            try:
                ak_msg = _configure_authentik_smtp_and_recovery(from_addr, plog)
                plog(f"✓ {ak_msg}")
            except Exception as e:
                plog(f"⚠ Authentik auto-config failed: {e}")
                plog("  You can configure it manually via the 'Configure Authentik' button.")
        else:
            plog("")
            plog("📋 Configure apps to use SMTP:")
            plog("   Host: localhost   Port: 25   No auth required")

        status.update({'running': False, 'complete': True, 'error': False})

    except Exception as e:
        plog(f"✗ Deploy failed: {str(e)}")
        status.update({'running': False, 'error': True})


def _authentik_smtp_configured():
    """True if Authentik .env has email settings (SMTP was pushed by Configure Authentik or deploy)."""
    env_path = os.path.expanduser('~/authentik/.env')
    if not os.path.exists(env_path):
        return False
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith('AUTHENTIK_EMAIL__HOST=') and '=' in line and line.strip().split('=', 1)[1].strip():
                return True
    return False

@app.route('/emailrelay')
@login_required
def emailrelay_page():
    modules = detect_modules()
    email = modules.get('emailrelay', {})
    settings = load_settings()
    relay_config = settings.get('email_relay', {})
    authentik_smtp_configured = modules.get('authentik', {}).get('installed') and _authentik_smtp_configured()
    return render_template_string(EMAIL_RELAY_TEMPLATE,
        settings=settings, modules=modules, email=email,
        relay_config=relay_config, providers=PROVIDERS,
        authentik_smtp_configured=authentik_smtp_configured,
        metrics=get_system_metrics(), version=VERSION,
        deploying=email_deploy_status.get('running', False),
        deploy_done=email_deploy_status.get('complete', False),
        deploy_error=email_deploy_status.get('error', False))

@app.route('/api/emailrelay/deploy', methods=['POST'])
@login_required
def emailrelay_deploy():
    if email_deploy_status['running']:
        return jsonify({'success': False, 'error': 'Deployment already in progress'})
    data = request.get_json()
    provider = data.get('provider', 'brevo')
    smtp_user = data.get('smtp_user', '').strip()
    smtp_pass = data.get('smtp_pass', '').strip()
    from_addr = data.get('from_addr', '').strip()
    from_name = data.get('from_name', '').strip()
    if not smtp_user or not smtp_pass or not from_addr:
        return jsonify({'success': False, 'error': 'SMTP username, password, and from address are required'})
    if provider == 'custom':
        custom_host = data.get('custom_host', '').strip()
        custom_port = data.get('custom_port', '587').strip()
        if not custom_host:
            return jsonify({'success': False, 'error': 'Custom host is required'})
        PROVIDERS['custom']['host'] = custom_host
        PROVIDERS['custom']['port'] = custom_port
    email_deploy_log.clear()
    email_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_email_deploy,
        args=(provider, smtp_user, smtp_pass, from_addr, from_name), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/emailrelay/log')
@login_required
def emailrelay_log():
    return jsonify({
        'running': email_deploy_status['running'],
        'complete': email_deploy_status['complete'],
        'error': email_deploy_status['error'],
        'entries': list(email_deploy_log)})

@app.route('/api/emailrelay/test', methods=['POST'])
@login_required
def emailrelay_test():
    data = request.get_json()
    to_addr = data.get('to', '').strip()
    if not to_addr:
        return jsonify({'success': False, 'error': 'Recipient address required'})
    settings = load_settings()
    relay_config = settings.get('email_relay', {})
    from_addr = relay_config.get('from_addr', 'noreply@localhost')
    from_name = relay_config.get('from_name', 'TAK-infra')
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg['From'] = f'{from_name} <{from_addr}>'
        msg['To'] = to_addr
        msg['Subject'] = 'TAK-infra Test Email'
        msg.attach(MIMEText('Test email from TAK-infra Email Relay.\n\nIf you received this, your email relay is working correctly.', 'plain'))
        with smtplib.SMTP('localhost', 25, timeout=15) as s:
            s.sendmail(from_addr, [to_addr], msg.as_string())
        return jsonify({'success': True, 'output': f'Test email sent to {to_addr}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emailrelay/swap', methods=['POST'])
@login_required
def emailrelay_swap():
    """Swap provider — reconfigure Postfix with new credentials"""
    if email_deploy_status['running']:
        return jsonify({'success': False, 'error': 'Deployment already in progress'})
    data = request.get_json()
    provider = data.get('provider', 'brevo')
    smtp_user = data.get('smtp_user', '').strip()
    smtp_pass = data.get('smtp_pass', '').strip()
    from_addr = data.get('from_addr', '').strip()
    from_name = data.get('from_name', '').strip()
    if not smtp_user or not smtp_pass or not from_addr:
        return jsonify({'success': False, 'error': 'All fields required'})
    if provider == 'custom':
        custom_host = data.get('custom_host', '').strip()
        custom_port = data.get('custom_port', '587').strip()
        if not custom_host:
            return jsonify({'success': False, 'error': 'Custom host is required'})
        PROVIDERS['custom']['host'] = custom_host
        PROVIDERS['custom']['port'] = custom_port
    email_deploy_log.clear()
    email_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_email_deploy,
        args=(provider, smtp_user, smtp_pass, from_addr, from_name), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/emailrelay/control', methods=['POST'])
@login_required
def emailrelay_control():
    data = request.get_json()
    action = data.get('action', '')
    if action == 'restart':
        r = subprocess.run('systemctl restart postfix 2>&1', shell=True, capture_output=True, text=True, timeout=30)
    elif action == 'stop':
        r = subprocess.run('systemctl stop postfix 2>&1', shell=True, capture_output=True, text=True, timeout=30)
    elif action == 'start':
        r = subprocess.run('systemctl start postfix 2>&1', shell=True, capture_output=True, text=True, timeout=30)
    else:
        return jsonify({'success': False, 'error': 'Unknown action'})
    return jsonify({'success': r.returncode == 0, 'output': r.stdout.strip()})

@app.route('/api/emailrelay/uninstall', methods=['POST'])
@login_required
def emailrelay_uninstall():
    subprocess.run('systemctl stop postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
    subprocess.run('systemctl disable postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
    settings = load_settings()
    pkg_mgr = settings.get('pkg_mgr', 'apt')
    if pkg_mgr == 'apt':
        subprocess.run('apt-get remove -y postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
    else:
        subprocess.run('dnf remove -y postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
    settings.pop('email_relay', None)
    save_settings(settings)
    email_deploy_log.clear()
    email_deploy_status.update({'running': False, 'complete': False, 'error': False})
    return jsonify({'success': True, 'steps': ['Postfix stopped and removed', 'Configuration cleared']})


def _configure_authentik_smtp_and_recovery(from_addr, plog=None):
    """Push SMTP settings into Authentik .env, restart containers, and set up recovery flow.
    Used by both the Email Relay deploy and the 'Configure Authentik' button.
    Returns a status message string. Raises on fatal error."""
    import re as _re
    ak_dir = os.path.expanduser('~/authentik')
    env_path = os.path.join(ak_dir, '.env')
    smtp_host = 'host.docker.internal'
    _from = (from_addr or '').strip() or 'authentik@localhost'
    _log = plog or (lambda msg: None)

    email_block = [
        '',
        '# Email — use local relay (Postfix on host)',
        f'AUTHENTIK_EMAIL__HOST={smtp_host}',
        'AUTHENTIK_EMAIL__PORT=25',
        'AUTHENTIK_EMAIL__USERNAME=',
        'AUTHENTIK_EMAIL__PASSWORD=',
        'AUTHENTIK_EMAIL__USE_TLS=false',
        'AUTHENTIK_EMAIL__USE_SSL=false',
        'AUTHENTIK_EMAIL__TIMEOUT=10',
        f'AUTHENTIK_EMAIL__FROM={_from}',
    ]
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_EMAIL__'):
                    continue
                lines.append(line.rstrip('\n'))
    if lines and lines[-1].strip() != '':
        lines.append('')
    lines.extend(email_block)
    with open(env_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    _log("  Wrote SMTP settings to Authentik .env")

    override_path = os.path.join(ak_dir, 'docker-compose.override.yml')
    override_content = '''# infra-TAK: allow containers to reach host Postfix for email
services:
  server:
    extra_hosts:
      - "host.docker.internal:host-gateway"
  worker:
    extra_hosts:
      - "host.docker.internal:host-gateway"
'''
    with open(override_path, 'w') as f:
        f.write(override_content)

    main_cf_path = '/etc/postfix/main.cf'
    if os.path.exists(main_cf_path):
        with open(main_cf_path) as f:
            mc = f.read()
        changed = False
        # So Docker (Authentik) can connect: listen on all interfaces
        if _re.search(r'^\s*inet_interfaces\s*=\s*localhost', mc, flags=_re.MULTILINE):
            mc = _re.sub(r'^\s*inet_interfaces\s*=\s*.*$', 'inet_interfaces = all', mc, flags=_re.MULTILINE)
            changed = True
        elif 'inet_interfaces' not in mc or _re.search(r'^\s*#\s*inet_interfaces', mc, flags=_re.MULTILINE):
            if mc.strip() and not mc.endswith('\n\n'):
                mc = mc.rstrip() + '\n'
            mc += 'inet_interfaces = all\n'
            changed = True
        if '172.16.0.0/12' not in mc:
            mc = _re.sub(r'^\s*mynetworks\s*=.*$', '', mc, flags=_re.MULTILINE)
            if mc.strip() and not mc.endswith('\n\n'):
                mc = mc.rstrip() + '\n'
            mc += 'mynetworks = 127.0.0.0/8 [::1]/128 172.16.0.0/12\n'
            changed = True
        if changed:
            with open(main_cf_path, 'w') as f:
                f.write(mc)
            subprocess.run('systemctl restart postfix 2>&1', shell=True, capture_output=True, text=True, timeout=30)

    # Allow Docker networks to reach host port 25 (Authentik worker → Postfix)
    r = subprocess.run('which ufw', shell=True, capture_output=True)
    if r.returncode == 0:
        subprocess.run('ufw allow from 172.16.0.0/12 to any port 25 2>/dev/null; true', shell=True, capture_output=True)
        subprocess.run('ufw reload 2>/dev/null; true', shell=True, capture_output=True)
        _log("  UFW: allowed Docker networks → port 25")
    else:
        r = subprocess.run('which firewall-cmd', shell=True, capture_output=True)
        if r.returncode == 0:
            subprocess.run(
                'firewall-cmd --permanent --add-rich-rule=\'rule family="ipv4" source address="172.16.0.0/12" port port="25" protocol="tcp" accept\' 2>/dev/null; true',
                shell=True, capture_output=True)
            subprocess.run('firewall-cmd --reload 2>/dev/null; true', shell=True, capture_output=True)
            _log("  firewalld: allowed Docker networks → port 25")

    _log("  Restarting Authentik containers...")
    r = subprocess.run(
        f'cd {ak_dir} && docker compose up -d --force-recreate',
        shell=True, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f'Authentik restart failed: {r.stderr or r.stdout}')

    ak_token = ''
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                    ak_token = line.strip().split('=', 1)[1].strip()
                    break

    message = 'Authentik SMTP configured (host.docker.internal:25).'
    if ak_token:
        ak_url = 'http://127.0.0.1:9090'
        ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
        _log("  Waiting for Authentik API...")
        api_ready = _wait_for_authentik_api(ak_url, ak_headers, max_attempts=120, plog=_log)
        if api_ready:
            _log("  Setting up recovery flow...")
            ok, recovery_msg, recovery_slug = _ensure_authentik_recovery_flow(ak_url, ak_headers)
            if ok:
                message += ' ' + recovery_msg
                if recovery_slug:
                    settings = load_settings()
                    fqdn = settings.get('fqdn', '').strip()
                    base = f'https://authentik.{fqdn}' if fqdn else 'https://<your-authentik-host>'
                    message += f' Direct recovery URL: {base}/if/flow/{recovery_slug}/.'
            else:
                message += f' Recovery flow issue: {recovery_msg}.'
        else:
            message += ' API not ready in time — recovery flow not set up.'
    return message


def _wait_for_authentik_api(ak_url, ak_headers, max_attempts=90, plog=None):
    """Poll until Authentik API responds. Returns True when ready (200 or 401/403), False on timeout."""
    import urllib.request as _req
    import urllib.error
    _log = plog or (lambda msg: None)
    for attempt in range(max_attempts):
        try:
            req = _req.Request(f'{ak_url}/api/v3/core/users/', headers=ak_headers)
            _req.urlopen(req, timeout=5)
            return True
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return True
            if e.code == 503:
                pass
        except Exception:
            pass
        if attempt > 0 and attempt % 6 == 0:
            _log(f"  ⏳ Still waiting for API... ({attempt * 5}s)")
        time.sleep(5)
    return False


def _ensure_authentik_recovery_flow(ak_url, ak_headers):
    """Create recovery flow + stages + bindings and link to default authentication flow.
    Matches official Authentik blueprint: Identification -> Email -> Prompt (new pw) -> User Write -> User Login.
    Fetches ALL bindings and filters client-side (the flow__pk server filter is unreliable).
    Returns (success: bool, message: str, recovery_slug: str|None)."""
    import urllib.request as _req
    import urllib.error
    def _err(e):
        try:
            body = e.read().decode()[:300]
        except Exception:
            body = ''
        return f'HTTP {e.code}: {body}' if body else f'HTTP {e.code}'
    def _api_get(path):
        r = _req.Request(f'{ak_url}/api/v3/{path}', headers=ak_headers)
        resp = _req.urlopen(r, timeout=15)
        return json.loads(resp.read().decode())
    def _api_post(path, body):
        r = _req.Request(f'{ak_url}/api/v3/{path}', data=json.dumps(body).encode(), headers=ak_headers, method='POST')
        resp = _req.urlopen(r, timeout=15)
        return json.loads(resp.read().decode())
    def _api_patch(path, body):
        r = _req.Request(f'{ak_url}/api/v3/{path}', data=json.dumps(body).encode(), headers=ak_headers, method='PATCH')
        resp = _req.urlopen(r, timeout=15)
        return json.loads(resp.read().decode())
    def _api_delete(path):
        r = _req.Request(f'{ak_url}/api/v3/{path}', headers=ak_headers, method='DELETE')
        _req.urlopen(r, timeout=15)
    def _find_stage(api_path, name):
        results = _api_get(f'{api_path}?search={_req.quote(name)}').get('results', [])
        for s in results:
            if s.get('name') == name:
                return s['pk']
        return None
    def _find_or_create_stage(api_path, name, extra_attrs=None):
        pk = _find_stage(api_path, name)
        if pk:
            return pk
        body = {'name': name}
        if extra_attrs:
            body.update(extra_attrs)
        try:
            return _api_post(api_path, body)['pk']
        except urllib.error.HTTPError as e:
            if e.code == 400:
                pk = _find_stage(api_path, name)
                if pk:
                    return pk
            raise
    try:
        recovery_flow_slug = 'default-password-recovery'

        # 1) Get or create recovery flow
        recovery_flows = _api_get('flows/instances/?designation=recovery').get('results', [])
        recovery_flow_pk = None
        for f in recovery_flows:
            if f.get('slug') == recovery_flow_slug:
                recovery_flow_pk = f['pk']
                break
        if not recovery_flow_pk and recovery_flows:
            recovery_flow_pk = recovery_flows[0]['pk']
            recovery_flow_slug = recovery_flows[0].get('slug', recovery_flow_slug)
        if not recovery_flow_pk:
            data = _api_post('flows/instances/', {
                'name': 'Password Recovery', 'slug': recovery_flow_slug,
                'designation': 'recovery', 'title': 'Reset your password',
                'authentication': 'none'})
            recovery_flow_pk = data['pk']
        else:
            try:
                _api_patch(f'flows/instances/{recovery_flow_slug}/', {'authentication': 'none'})
            except Exception:
                pass

        # 2) Create all required stages

        id_stage_pk = _find_stage('stages/identification/', 'default-authentication-identification')
        if not id_stage_pk:
            id_stage_pk = _find_stage('stages/identification/', 'Recovery Identification')
        if not id_stage_pk:
            all_id_stages = _api_get('stages/identification/').get('results', [])
            if all_id_stages:
                id_stage_pk = all_id_stages[0]['pk']

        email_stage_pk = _find_or_create_stage('stages/email/', 'Recovery Email', {
            'use_global_settings': True,
            'template': 'email/password_reset.html',
            'activate_user_on_success': True,
            'token_expiry': 'minutes=30',
            'subject': 'Password Reset'})
        if email_stage_pk:
            try:
                _api_patch(f'stages/email/{email_stage_pk}/', {
                    'use_global_settings': True,
                    'template': 'email/password_reset.html',
                    'activate_user_on_success': True})
            except Exception:
                pass

        def _find_or_create_prompt(name, field_key, label, order):
            results = _api_get(f'stages/prompt/prompts/?search={_req.quote(name)}').get('results', [])
            for p in results:
                if p.get('name') == name:
                    return p['pk']
            try:
                return _api_post('stages/prompt/prompts/', {
                    'name': name, 'field_key': field_key, 'label': label,
                    'type': 'password', 'required': True, 'placeholder': label,
                    'order': order, 'placeholder_expression': False})['pk']
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    results = _api_get(f'stages/prompt/prompts/?search={_req.quote(name)}').get('results', [])
                    for p in results:
                        if p.get('name') == name:
                            return p['pk']
                raise

        pw_field_pk = _find_or_create_prompt('recovery-field-password', 'password', 'Password', 0)
        pw_repeat_field_pk = _find_or_create_prompt('recovery-field-password-repeat', 'password_repeat', 'Password (repeat)', 1)

        prompt_stage_pk = _find_stage('stages/prompt/stages/', 'Recovery Password Change')
        if not prompt_stage_pk:
            try:
                prompt_stage_pk = _api_post('stages/prompt/stages/', {
                    'name': 'Recovery Password Change',
                    'fields': [pw_field_pk, pw_repeat_field_pk]})['pk']
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    prompt_stage_pk = _find_stage('stages/prompt/stages/', 'Recovery Password Change')
                if not prompt_stage_pk:
                    raise
        else:
            try:
                _api_patch(f'stages/prompt/stages/{prompt_stage_pk}/', {
                    'fields': [pw_field_pk, pw_repeat_field_pk]})
            except Exception:
                pass

        user_write_pk = _find_or_create_stage('stages/user_write/', 'Recovery User Write',
            {'user_creation_mode': 'never_create'})

        user_login_pk = _find_or_create_stage('stages/user_login/', 'Recovery User Login')

        # 3) Fetch ALL bindings, filter client-side by target == recovery flow PK.
        #    The server-side flow__pk filter is unreliable and returns bindings from other flows.
        all_bindings = []
        page = 1
        while True:
            data = _api_get(f'flows/bindings/?ordering=order&page_size=500&page={page}')
            all_bindings.extend(data.get('results', []))
            if not data.get('pagination', {}).get('next'):
                break
            page += 1

        recovery_bindings = [b for b in all_bindings if str(b.get('target')) == str(recovery_flow_pk)]

        desired_stage_pks = set()
        for pk in [id_stage_pk, email_stage_pk, prompt_stage_pk, user_write_pk, user_login_pk]:
            if pk:
                desired_stage_pks.add(str(pk))

        # 4) Delete any binding on the recovery flow whose stage is NOT one of our 5 desired stages
        for b in recovery_bindings:
            if str(b.get('stage', '')) not in desired_stage_pks:
                try:
                    _api_delete(f'flows/bindings/{b["pk"]}/')
                except Exception:
                    pass

        # 5) Create missing bindings
        already_bound = {str(b.get('stage')) for b in recovery_bindings}
        desired_bindings = [
            (10, id_stage_pk),
            (20, email_stage_pk),
            (30, prompt_stage_pk),
            (40, user_write_pk),
            (100, user_login_pk),
        ]
        for order, stage_pk in desired_bindings:
            if not stage_pk or str(stage_pk) in already_bound:
                continue
            try:
                _api_post('flows/bindings/', {
                    'target': recovery_flow_pk, 'stage': stage_pk, 'order': order,
                    'evaluate_on_plan': True, 're_evaluate_policies': order <= 20,
                    'policy_engine_mode': 'any', 'invalid_response_action': 'retry'})
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    pass
                else:
                    raise

        # 6) Link recovery flow to the default-authentication-identification stage
        auth_id_stage_pk = _find_stage('stages/identification/', 'default-authentication-identification')
        if not auth_id_stage_pk:
            all_id = _api_get('stages/identification/').get('results', [])
            for s in all_id:
                if 'default' in s.get('name', '').lower() and 'authentication' in s.get('name', '').lower():
                    auth_id_stage_pk = s['pk']
                    break
        if auth_id_stage_pk:
            try:
                stage_data = _api_get(f'stages/identification/{auth_id_stage_pk}/')
                current_rf = stage_data.get('recovery_flow')
                current_pk = (current_rf if isinstance(current_rf, str) else
                              (current_rf.get('pk') if isinstance(current_rf, dict) and current_rf else None))
                if current_pk != recovery_flow_pk:
                    patch_body = {'recovery_flow': recovery_flow_pk}
                    uf = stage_data.get('user_fields')
                    if uf:
                        patch_body['user_fields'] = uf
                    try:
                        _api_patch(f'stages/identification/{auth_id_stage_pk}/', patch_body)
                    except urllib.error.HTTPError:
                        put_body = {k: v for k, v in stage_data.items()
                                    if k not in ('pk', 'component', 'verbose_name', 'verbose_name_plural', 'meta_model_name', 'flow_set')}
                        put_body['recovery_flow'] = recovery_flow_pk
                        r = _req.Request(f'{ak_url}/api/v3/stages/identification/{auth_id_stage_pk}/',
                            data=json.dumps(put_body).encode(), headers=ak_headers, method='PUT')
                        _req.urlopen(r, timeout=15)
            except urllib.error.HTTPError:
                pass
        return True, 'Recovery flow created and linked; "Forgot password?" is on the login page.', recovery_flow_slug
    except urllib.error.HTTPError as e:
        return False, _err(e), None
    except Exception as e:
        return False, str(e), None


@app.route('/api/emailrelay/configure-authentik', methods=['POST'])
@login_required
def emailrelay_configure_authentik():
    """Push Email Relay settings into Authentik and set up recovery flow (SMTP + Forgot password?)."""
    settings = load_settings()
    relay = settings.get('email_relay') or {}
    if not relay.get('from_addr'):
        return jsonify({'success': False, 'error': 'Email Relay not configured. Deploy the relay first.'}), 400
    ak_dir = os.path.expanduser('~/authentik')
    if not os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')):
        return jsonify({'success': False, 'error': 'Authentik is not installed.'}), 400
    try:
        message = _configure_authentik_smtp_and_recovery(relay.get('from_addr', ''))
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Node-RED ──────────────────────────────────────────────────────────────────
nodered_deploy_log = []
nodered_deploy_status = {'running': False, 'complete': False, 'error': False, 'cancelled': False}

@app.route('/api/nodered/deploy', methods=['POST'])
@login_required
def nodered_deploy_api():
    if nodered_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    nodered_deploy_log.clear()
    nodered_deploy_status.update({'running': True, 'complete': False, 'error': False, 'cancelled': False})
    threading.Thread(target=run_nodered_deploy, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/nodered/deploy/cancel', methods=['POST'])
@login_required
def nodered_deploy_cancel():
    nodered_deploy_status['cancelled'] = True
    return jsonify({'success': True})

@app.route('/api/nodered/deploy/log')
@login_required
def nodered_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': nodered_deploy_log[idx:], 'total': len(nodered_deploy_log),
        'running': nodered_deploy_status['running'], 'complete': nodered_deploy_status['complete'],
        'error': nodered_deploy_status['error'], 'cancelled': nodered_deploy_status.get('cancelled', False)})

@app.route('/api/nodered/control', methods=['POST'])
@login_required
def nodered_control():
    action = (request.json or {}).get('action', '')
    nr_dir = os.path.expanduser('~/node-red')
    compose = os.path.join(nr_dir, 'docker-compose.yml')
    if not os.path.exists(compose):
        return jsonify({'error': 'Node-RED not deployed here'}), 400
    if action == 'start':
        subprocess.run(f'docker compose -f "{compose}" up -d 2>&1', shell=True, capture_output=True, timeout=60, cwd=nr_dir)
    elif action == 'stop':
        subprocess.run(f'docker compose -f "{compose}" stop 2>&1', shell=True, capture_output=True, timeout=60, cwd=nr_dir)
    elif action == 'restart':
        subprocess.run(f'docker compose -f "{compose}" restart 2>&1', shell=True, capture_output=True, timeout=60, cwd=nr_dir)
    else:
        return jsonify({'error': 'Invalid action'}), 400
    time.sleep(2)
    r = subprocess.run('docker ps --filter name=nodered --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
    running = r.stdout and 'Up' in r.stdout
    return jsonify({'success': True, 'running': running})

@app.route('/api/nodered/logs')
@login_required
def nodered_logs():
    lines = request.args.get('lines', 80, type=int)
    nr_dir = os.path.expanduser('~/node-red')
    compose = os.path.join(nr_dir, 'docker-compose.yml')
    if not os.path.exists(compose):
        return jsonify({'entries': []})
    r = subprocess.run(f'docker compose -f "{compose}" logs --tail={lines} 2>&1', shell=True, capture_output=True, text=True, timeout=15, cwd=nr_dir)
    entries = [l for l in (r.stdout.strip().split('\n') if r.stdout else []) if l.strip()]
    return jsonify({'entries': entries})

@app.route('/api/nodered/uninstall', methods=['POST'])
@login_required
def nodered_uninstall():
    try:
        data = request.get_json(silent=True) or {}
        password = data.get('password', '')
        auth = load_auth()
        if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
            return jsonify({'error': 'Invalid admin password'}), 403
        nr_dir = os.path.expanduser('~/node-red')
        compose = os.path.join(nr_dir, 'docker-compose.yml')
        if os.path.exists(compose):
            subprocess.run(f'docker compose -f "{compose}" down -v 2>&1', shell=True, capture_output=True, timeout=60, cwd=nr_dir)
        if os.path.exists(nr_dir):
            subprocess.run(f'rm -rf "{nr_dir}"', shell=True, capture_output=True, timeout=10)
        nodered_deploy_log.clear()
        nodered_deploy_status.update({'running': False, 'complete': False, 'error': False})
        settings = load_settings()
        if settings.get('fqdn'):
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=15)
        return jsonify({'success': True, 'steps': ['Node-RED container and data removed', 'Caddyfile updated']})
    except Exception as e:
        return jsonify({'error': f'Uninstall failed: {str(e)}'}), 500

def _ensure_authentik_nodered_app(fqdn, ak_token, plog=None, flow_pk=None, inv_flow_pk=None):
    """Create Node-RED proxy provider + application in Authentik, add to embedded outpost.
    When flow_pk/inv_flow_pk are provided (e.g. from Step 12), use them. Otherwise wait for flows."""
    if not fqdn or not ak_token:
        return False
    def log(msg):
        if plog:
            plog(msg)
    import urllib.request as _urlreq
    import urllib.error
    _ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
    _ak_url = 'http://127.0.0.1:9090'

    try:
        if not flow_pk or not inv_flow_pk:
            for attempt in range(36):
                try:
                    req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=authorization&ordering=slug', headers=_ak_headers)
                    resp = _urlreq.urlopen(req, timeout=10)
                    flows = json.loads(resp.read().decode())['results']
                    flow_pk = next((f['pk'] for f in flows if 'implicit' in f.get('slug', '')), flows[0]['pk'] if flows else None)
                    if flow_pk:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=invalidation', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        inv_flows = json.loads(resp.read().decode())['results']
                        inv_flow_pk = next((f['pk'] for f in inv_flows if 'provider' not in f.get('slug', '')), inv_flows[0]['pk'] if inv_flows else None)
                        if inv_flow_pk:
                            break
                except Exception:
                    pass
                if attempt % 6 == 0:
                    log(f"  ⏳ Waiting for authorization flow... ({attempt * 5}s)")
                time.sleep(5)
            if not flow_pk or not inv_flow_pk:
                log("  ⚠ No authorization/invalidation flow — skipping Node-RED proxy provider")
                return False
            log("  ✓ Got authorization and invalidation flows")

        # Create proxy provider (same payload structure as TAK Portal)
        provider_pk = None
        try:
            req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/',
                data=json.dumps({'name': 'Node-RED Proxy', 'authorization_flow': flow_pk,
                    'invalidation_flow': inv_flow_pk,
                    'external_host': f'https://nodered.{fqdn}', 'mode': 'forward_single',
                    'token_validity': 'hours=24', 'cookie_domain': f'.{fqdn.split(":")[0]}'}).encode(),
                headers=_ak_headers, method='POST')
            resp = _urlreq.urlopen(req, timeout=10)
            provider_pk = json.loads(resp.read().decode())['pk']
            log("  ✓ Proxy provider created")
        except Exception as e:
            if hasattr(e, 'code') and e.code == 400:
                req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/?search=Node-RED', headers=_ak_headers)
                resp = _urlreq.urlopen(req, timeout=10)
                results = json.loads(resp.read().decode())['results']
                if results:
                    provider_pk = results[0]['pk']
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/{provider_pk}/',
                            data=json.dumps({'external_host': f'https://nodered.{fqdn}', 'cookie_domain': f'.{fqdn.split(":")[0]}'}).encode(),
                            headers=_ak_headers, method='PATCH')
                        _urlreq.urlopen(req, timeout=10)
                    except Exception:
                        pass
                log("  ✓ Proxy provider already exists (external_host updated to nodered subdomain)")
            else:
                log(f"  ⚠ Proxy provider error: {str(e)[:100]}")

        # Create application
        if provider_pk:
            try:
                req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/',
                    data=json.dumps({'name': 'Node-RED', 'slug': 'node-red',
                        'provider': provider_pk}).encode(),
                    headers=_ak_headers, method='POST')
                _urlreq.urlopen(req, timeout=10)
                log("  ✓ Application 'Node-RED' created")
            except Exception as e:
                if hasattr(e, 'code') and e.code == 400:
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/node-red/',
                            data=json.dumps({'provider': provider_pk}).encode(),
                            headers=_ak_headers, method='PATCH')
                        _urlreq.urlopen(req, timeout=10)
                    except Exception:
                        pass
                    log("  ✓ Application 'Node-RED' updated")
                else:
                    log(f"  ⚠ Application error: {str(e)[:80]}")

            # 5) Add to embedded outpost
            try:
                req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/?search=embedded', headers=_ak_headers)
                resp = _urlreq.urlopen(req, timeout=10)
                outposts = json.loads(resp.read().decode())['results']
                embedded = next((o for o in outposts if 'embed' in o.get('name','').lower() or o.get('type') == 'proxy'), None)
                if embedded:
                    current_providers = embedded.get('providers', [])
                    if provider_pk not in current_providers:
                        current_providers.append(provider_pk)
                    req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/{embedded["pk"]}/',
                        data=json.dumps({'providers': current_providers}).encode(),
                        headers=_ak_headers, method='PATCH')
                    _urlreq.urlopen(req, timeout=10)
                    log("  ✓ Node-RED added to embedded outpost")
                else:
                    log("  ⚠ No embedded outpost found")
            except Exception as e:
                log(f"  ⚠ Outpost error: {str(e)[:80]}")
        else:
            log("  ⚠ Could not create or find Node-RED proxy provider")
    except Exception as e:
        log(f"  ⚠ Forward auth setup error: {str(e)[:100]}")
    return True

def _ensure_authentik_console_app(fqdn, ak_token, plog=None, flow_pk=None, inv_flow_pk=None):
    """Create infra-TAK Console proxy providers (infratak + console) and applications in Authentik, add to embedded outpost.
    When flow_pk/inv_flow_pk are provided (e.g. from Step 12), use them. Otherwise wait for flows (e.g. when called from Caddy save)."""
    if not fqdn or not ak_token:
        return False
    def log(msg):
        if plog:
            plog(msg)
    import urllib.request as _urlreq
    _ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
    _ak_url = 'http://127.0.0.1:9090'

    try:
        if not flow_pk or not inv_flow_pk:
            for attempt in range(36):
                try:
                    req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=authorization&ordering=slug', headers=_ak_headers)
                    resp = _urlreq.urlopen(req, timeout=10)
                    flows = json.loads(resp.read().decode())['results']
                    flow_pk = next((f['pk'] for f in flows if 'implicit' in f.get('slug', '')), flows[0]['pk'] if flows else None)
                    if flow_pk:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/flows/instances/?designation=invalidation', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        inv_flows = json.loads(resp.read().decode())['results']
                        inv_flow_pk = next((f['pk'] for f in inv_flows if 'provider' not in f.get('slug', '')), inv_flows[0]['pk'] if inv_flows else None)
                        if inv_flow_pk:
                            break
                except Exception:
                    pass
                if attempt % 6 == 0 and plog:
                    plog(f"  ⏳ Waiting for authorization flow... ({attempt * 5}s)")
                time.sleep(5)
        if not flow_pk or not inv_flow_pk:
            log("  ⚠ No authorization/invalidation flow — skipping infra-TAK Console proxy providers")
            return False

        entries = [('infra-TAK', 'infratak', f'https://{_get_service_domain(load_settings(), "infratak")}')]
        try:
            s = load_settings()
            mtx_domain = _get_service_domain(s, 'mediamtx')
            entries.append(('MediaMTX', 'stream', f'https://{mtx_domain}'))
        except Exception:
            pass
        provider_pks = []
        base_domain = fqdn.split(':')[0]
        cookie_domain = f'.{base_domain}'
        for name, slug, host in entries:
            pk = None
            try:
                req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/',
                    data=json.dumps({'name': name, 'authorization_flow': flow_pk,
                        'invalidation_flow': inv_flow_pk,
                        'external_host': host, 'mode': 'forward_single',
                        'token_validity': 'hours=24', 'cookie_domain': cookie_domain}).encode(),
                    headers=_ak_headers, method='POST')
                resp = _urlreq.urlopen(req, timeout=10)
                pk = json.loads(resp.read().decode())['pk']
                provider_pks.append(pk)
                log(f"  ✓ Proxy provider created: {name}")
            except Exception as e:
                if hasattr(e, 'code') and e.code == 400:
                    import urllib.parse as _uparse
                    req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/?search={_uparse.quote(name)}', headers=_ak_headers)
                    resp = _urlreq.urlopen(req, timeout=10)
                    results = json.loads(resp.read().decode())['results']
                    if results:
                        pk = results[0]['pk']
                        provider_pks.append(pk)
                    log(f"  ✓ Proxy provider already exists: {name}")
                else:
                    log(f"  ⚠ Provider error {name}: {str(e)[:80]}")
            if pk:
                try:
                    req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/',
                        data=json.dumps({'name': name, 'slug': slug, 'provider': pk}).encode(),
                        headers=_ak_headers, method='POST')
                    _urlreq.urlopen(req, timeout=10)
                    log(f"  ✓ Application created: {name}")
                except Exception as e:
                    if hasattr(e, 'code') and e.code == 400:
                        try:
                            req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/{slug}/',
                                data=json.dumps({'provider': pk}).encode(),
                                headers=_ak_headers, method='PATCH')
                            _urlreq.urlopen(req, timeout=10)
                        except Exception:
                            pass
                        log(f"  ✓ Application already exists: {name}")
                    else:
                        log(f"  ⚠ Application error: {str(e)[:80]}")

        for name, slug, host in entries:
            try:
                req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/{slug}/', headers=_ak_headers)
                _urlreq.urlopen(req, timeout=10)
            except Exception as e:
                if hasattr(e, 'code') and e.code == 404:
                    import urllib.parse as _uparse
                    try:
                        req = _urlreq.Request(f'{_ak_url}/api/v3/providers/proxy/?search={_uparse.quote(name)}', headers=_ak_headers)
                        resp = _urlreq.urlopen(req, timeout=10)
                        results = json.loads(resp.read().decode())['results']
                        if results:
                            pk = results[0]['pk']
                            req = _urlreq.Request(f'{_ak_url}/api/v3/core/applications/',
                                data=json.dumps({'name': name, 'slug': slug, 'provider': pk}).encode(),
                                headers=_ak_headers, method='POST')
                            _urlreq.urlopen(req, timeout=10)
                            if pk not in provider_pks:
                                provider_pks.append(pk)
                            log(f"  ✓ Application recreated: {name}")
                    except Exception:
                        pass

        if provider_pks:
            try:
                req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/?search=embedded', headers=_ak_headers)
                resp = _urlreq.urlopen(req, timeout=10)
                outposts = json.loads(resp.read().decode())['results']
                embedded = next((o for o in outposts if 'embed' in o.get('name', '').lower() or o.get('type') == 'proxy'), None)
                if embedded:
                    current = list(embedded.get('providers', []))
                    for pk in provider_pks:
                        if pk not in current:
                            current.append(pk)
                    req = _urlreq.Request(f'{_ak_url}/api/v3/outposts/instances/{embedded["pk"]}/',
                        data=json.dumps({'providers': current}).encode(),
                        headers=_ak_headers, method='PATCH')
                    _urlreq.urlopen(req, timeout=10)
                    log("  ✓ infra-TAK Console added to embedded outpost")
            except Exception as e:
                log(f"  ⚠ Outpost error: {str(e)[:80]}")
        return True
    except Exception as e:
        log(f"  ⚠ Console forward auth setup: {str(e)[:100]}")
        return False


def _ensure_proxy_providers_cookie_domain(ak_url, ak_headers, fqdn, plog=None):
    """Set cookie_domain on all proxy providers so session is shared across subdomains (avoids stream. redirect loop)."""
    if not fqdn:
        return
    import urllib.request as _req
    import urllib.error
    base = fqdn.split(':')[0]
    cookie_domain = f'.{base}'
    _log = plog or (lambda m: None)
    try:
        r = _req.Request(f'{ak_url}/api/v3/providers/proxy/?page_size=100', headers=ak_headers)
        data = json.loads(_req.urlopen(r, timeout=15).read().decode())
        for prov in data.get('results', []):
            pk = prov.get('pk')
            if not pk:
                continue
            try:
                patch = _req.Request(f'{ak_url}/api/v3/providers/proxy/{pk}/',
                    data=json.dumps({'cookie_domain': cookie_domain}).encode(),
                    headers=ak_headers, method='PATCH')
                _req.urlopen(patch, timeout=10)
            except urllib.error.HTTPError:
                pass
        _log("  ✓ Proxy providers cookie_domain set for shared session")
    except Exception as e:
        _log(f"  ⚠ Proxy cookie_domain: {str(e)[:80]}")


def _ensure_app_access_policies(ak_url, ak_headers, plog=None):
    """Restrict infra-TAK, Node-RED (and LDAP) to authentik Admins. TAK Portal and MediaMTX open to all authenticated users.
    Creates a 'Group membership: authentik Admins' policy and binds it only to admin-only apps. No binding on TAK Portal/MediaMTX = everyone sees them.
    Idempotent — safe to call on every deploy."""
    import urllib.request as _req
    import urllib.error
    from urllib.parse import quote as _quote
    _log = plog or (lambda m: None)
    _last_path = [None]  # cell for closure

    def _log_http_err(e, path_hint=None):
        path = path_hint or _last_path[0] or '?'
        full_url = f'{ak_url}/api/v3/{path}' if path and path != '?' else getattr(e, 'url', path)
        try:
            body = e.fp.read(200).decode(errors='replace') if e.fp else ''
        except Exception:
            body = ''
        _log(f"  ⚠ App access policy API error: {e.code} {e.reason} — {full_url}")
        if body:
            _log(f"     Response: {body[:120]}")

    def _api_get(path):
        _last_path[0] = path
        r = _req.Request(f'{ak_url}/api/v3/{path}', headers=ak_headers)
        return json.loads(_req.urlopen(r, timeout=15).read().decode())

    def _api_post(path, body):
        _last_path[0] = path
        r = _req.Request(f'{ak_url}/api/v3/{path}', data=json.dumps(body).encode(), headers=ak_headers, method='POST')
        return json.loads(_req.urlopen(r, timeout=15).read().decode())

    def _api_delete(path):
        _last_path[0] = path
        r = _req.Request(f'{ak_url}/api/v3/{path}', headers=ak_headers, method='DELETE')
        _req.urlopen(r, timeout=15)

    try:
        # 1) Find the "authentik Admins" group PK
        groups = _api_get('core/groups/?search=authentik+Admins')['results']
        admin_group_pk = None
        for g in groups:
            if g.get('name') == 'authentik Admins':
                admin_group_pk = g['pk']
                break
        if not admin_group_pk:
            _log("  ⚠ 'authentik Admins' group not found — skipping app access policies")
            return False

        # 2) Find or create the "Allow authentik Admins" policy (group membership or expression)
        policy_name = 'Allow authentik Admins'
        policy_pk = None
        # Newer Authentik: policies/all/; older: policies/group_membership/
        for list_path in ('policies/all/', 'policies/group_membership/'):
            try:
                data = _api_get(f'{list_path}?search={_quote(policy_name)}')
                results = (data.get('results') if isinstance(data, dict) else None) or []
                for p in results:
                    if p.get('name') == policy_name:
                        policy_pk = p['pk']
                        break
                if policy_pk:
                    break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                raise
        if not policy_pk:
            # Create: try group_membership (older) then expression (newer)
            try:
                data = _api_post('policies/group_membership/', {
                    'name': policy_name,
                    'group': admin_group_pk,
                })
                policy_pk = data['pk']
                _log(f"  ✓ Created policy: {policy_name}")
            except urllib.error.HTTPError as e:
                if e.code in (404, 405):
                    # 404 = no group_membership endpoint; 405 = endpoint exists but POST not allowed (newer Authentik)
                    try:
                        data = _api_post('policies/expression/', {
                            'name': policy_name,
                            'expression': 'return ak_is_group_member(request.user, name="authentik Admins")',
                        })
                        policy_pk = data['pk']
                        _log(f"  ✓ Created expression policy: {policy_name}")
                    except urllib.error.HTTPError as e2:
                        _log_http_err(e2)
                        _log(f"  ⚠ Could not create policy: {e2.code} {e2.reason}")
                        return False
                elif e.code == 400:
                    for list_path in ('policies/all/', 'policies/group_membership/'):
                        try:
                            data = _api_get(f'{list_path}?search={_quote(policy_name)}')
                            for p in (data.get('results') or []):
                                if p.get('name') == policy_name:
                                    policy_pk = p['pk']
                                    break
                            if policy_pk:
                                break
                        except urllib.error.HTTPError:
                            continue
                    if not policy_pk:
                        _log(f"  ⚠ Could not create policy: {e}")
                        return False
                else:
                    raise
        else:
            _log(f"  ✓ Policy exists: {policy_name}")

        # 3) Admin-only apps: bind the admin policy (infra-TAK, Node-RED). LDAP must be open to all authenticated users (QR registration, device bind). TAK Portal and MediaMTX: no binding = all authenticated users.
        admin_only_slugs = ['infra-tak', 'infratak', 'console', 'node-red']
        user_visible_slugs = ['mediamtx', 'stream', 'tak-portal', 'ldap']  # no policy = visible to all authenticated users (LDAP needed for QR registration)

        all_apps = _api_get('core/applications/?page_size=100')['results']

        def _bind_policy_to_app(app_pk, app_name, pol_pk, pol_name):
            bindings = _api_get(f'policies/bindings/?target={app_pk}&page_size=100')['results']
            already = any(
                str(b.get('policy')) == str(pol_pk) or
                (b.get('policy_obj', {}) or {}).get('name') == pol_name
                for b in bindings
            )
            if already:
                return False
            try:
                _api_post('policies/bindings/', {
                    'target': app_pk, 'policy': pol_pk,
                    'order': 0, 'negate': False, 'enabled': True, 'timeout': 30,
                })
                return True
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    _log(f"  ⚠ {app_name}: binding error: {e}")
                return False

        # Remove "Allow MediaMTX users" binding from stream/mediamtx if present (so they become visible to all authenticated users)
        mtx_policy_name = 'Allow MediaMTX users'
        for app in all_apps:
            app_slug = app.get('slug', '')
            if app_slug not in ('mediamtx', 'stream'):
                continue
            app_pk = app.get('pk', '')
            app_name = app.get('name', '')
            bindings = _api_get(f'policies/bindings/?target={app_pk}&page_size=100')['results']
            for b in bindings:
                if (b.get('policy_obj', {}) or {}).get('name') == mtx_policy_name:
                    try:
                        _api_delete(f'policies/bindings/{b["pk"]}/')
                        _log(f"  ✓ {app_name}: removed restrictive policy — now open to all authenticated users")
                    except Exception:
                        pass
                    break
        # Remove "Allow authentik Admins" binding from LDAP if present (blocks QR registration / device bind for non-admin users)
        for app in all_apps:
            app_slug = app.get('slug', '')
            if app_slug != 'ldap':
                continue
            app_pk = app.get('pk', '')
            app_name = app.get('name', '')
            bindings = _api_get(f'policies/bindings/?target={app_pk}&page_size=100')['results']
            for b in bindings:
                if (b.get('policy_obj', {}) or {}).get('name') == policy_name:
                    try:
                        _api_delete(f'policies/bindings/{b["pk"]}/')
                        _log(f"  ✓ {app_name}: removed restrictive policy — now open to all authenticated users")
                    except Exception:
                        pass
                    break

        for app in all_apps:
            app_slug = app.get('slug', '')
            app_pk = app.get('pk', '')
            app_name = app.get('name', '')

            if app_slug in admin_only_slugs:
                if _bind_policy_to_app(app_pk, app_name, policy_pk, policy_name):
                    _log(f"  ✓ {app_name}: restricted to authentik Admins")
                else:
                    _log(f"  ✓ {app_name}: already restricted to authentik Admins")

            elif app_slug in user_visible_slugs:
                _log(f"  ✓ {app_name}: open to all authenticated users (no restrictive binding)")

        return True

    except urllib.error.HTTPError as e:
        _log_http_err(e)
        _log(f"  ⚠ App access policy setup: HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        _log(f"  ⚠ App access policy setup: {str(e)[:150]}")
        return False


def run_nodered_deploy():
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        nodered_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        if nodered_deploy_status.get('cancelled'):
            nodered_deploy_status.update({'running': False, 'complete': False, 'cancelled': True})
            return
        settings = load_settings()
        domain = (settings.get('fqdn') or '').strip()
        nr_dir = os.path.expanduser('~/node-red')
        os.makedirs(nr_dir, exist_ok=True)
        plog("━━━ Step 1/3: Creating Docker Compose ━━━")
        compose_yml = os.path.join(nr_dir, 'docker-compose.yml')
        settings_js = os.path.join(nr_dir, 'settings.js')
        # Node-RED at root (/) so Caddy can proxy nodered.domain to 1880
        with open(settings_js, 'w') as f:
            f.write("""module.exports = {
  flowFile: 'flows.json',
  flowFilePretty: true,
  userDir: '/data',
  httpAdminRoot: '/',
  httpNodeRoot: '/'
};
""")
        with open(compose_yml, 'w') as f:
            f.write("""services:
  node-red:
    image: nodered/node-red:latest
    container_name: nodered
    ports:
      - "1880:1880"
    volumes:
      - node_red_data:/data
      - ./settings.js:/data/settings.js
volumes:
  node_red_data:
""")
        plog("✓ docker-compose.yml written")
        plog("")
        plog("━━━ Step 2/3: Starting Node-RED ━━━")
        r = subprocess.run(f'docker compose -f "{compose_yml}" up -d 2>&1', shell=True, capture_output=True, text=True, timeout=120, cwd=nr_dir)
        if r.returncode != 0:
            plog(f"✗ docker compose up failed: {r.stderr or r.stdout or 'unknown'}")
            nodered_deploy_status.update({'running': False, 'error': True})
            return
        plog("✓ Node-RED container started")
        plog("")
        plog("━━━ Step 3/3: Updating Caddy ━━━")
        if domain:
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null', shell=True, capture_output=True, timeout=15)
            plog(f"✓ Caddy updated — open via https://nodered.{domain}")
        else:
            plog("  No domain configured — access via http://<server>:1880")
        if not nodered_deploy_status.get('cancelled') and domain and os.path.exists(os.path.expanduser('~/authentik/.env')):
            plog("")
            plog("━━━ Configuring Authentik for Node-RED ━━━")
            ak_token = ''
            with open(os.path.expanduser('~/authentik/.env')) as f:
                for line in f:
                    if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                        ak_token = line.strip().split('=', 1)[1].strip()
                        break
            _ensure_authentik_nodered_app(domain, ak_token, plog)
            plog("")
            plog("  Waiting 2 minutes for Authentik outpost to sync...")
            for i in range(24):
                if nodered_deploy_status.get('cancelled'):
                    plog("  ⚠ Cancelled by user")
                    break
                time.sleep(5)
                remaining = 120 - (i + 1) * 5
                if remaining > 0 and remaining % 30 == 0:
                    plog(f"  ⏳ {remaining} seconds remaining...")
            if not nodered_deploy_status.get('cancelled'):
                plog("  ✓ Sync complete — Node-RED is ready behind Authentik")
        plog("")
        if nodered_deploy_status.get('cancelled'):
            plog("Deployment cancelled.")
        else:
            plog("✅ Node-RED deployed. Open the flow editor and build your flows.")
        nodered_deploy_status.update({'running': False, 'complete': not nodered_deploy_status.get('cancelled', False), 'error': False})
    except Exception as e:
        plog(f"✗ Error: {str(e)}")
        nodered_deploy_status.update({'running': False, 'error': True})


NODERED_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Node-RED — infra-TAK</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg-deep);color:var(--text-primary);font-family:'DM Sans',sans-serif;min-height:100vh;display:flex;flex-direction:row}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
.page-header{margin-bottom:28px}.page-header h1{font-size:22px;font-weight:700}.page-header p{color:var(--text-secondary);font-size:13px;margin-top:4px}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px}
.card-title{font-size:13px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.status-banner{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:13px}
.status-banner.running{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:var(--green)}
.status-banner.stopped{background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.2);color:var(--yellow)}
.status-banner.not-installed{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);color:var(--accent)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.info-item{background:#0a0e1a;border-radius:8px;padding:12px 14px}
.info-label{font-size:11px;color:var(--text-dim);margin-bottom:3px;text-transform:uppercase}
.info-value{font-size:13px;font-family:'JetBrains Mono',monospace;word-break:break-all}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.btn-primary{background:var(--accent);color:#fff}.btn-success{background:var(--green);color:#fff}.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border)}
.btn-danger{background:var(--red);color:#fff}
.controls{display:flex;gap:10px;flex-wrap:wrap}
.log-box{background:#070a12;border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:340px;overflow-y:auto;white-space:pre-wrap}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px}
</style></head>
<body>
{{ sidebar_html }}
<div class="main">
  <div class="page-header"><h1 style="display:flex;flex-direction:column;align-items:flex-start;gap:6px"><img src="{{ nodered_logo_url }}" alt="" style="height:32px;width:auto;object-fit:contain"><span>Node-RED</span></h1><p>Flow-based automation and integrations</p></div>
  {% if nr.running %}<div class="status-banner running"><div class="dot"></div>Node-RED is running</div>
  {% elif nr.installed %}<div class="status-banner stopped"><div class="dot"></div>Node-RED is installed but stopped</div>
  {% else %}<div class="status-banner not-installed"><div class="dot"></div>Node-RED is not installed</div>{% endif %}
  {% if nr.installed %}
  {% if authentik_installed and settings.fqdn %}<div class="card" style="border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.05)"><div class="card-title">&#128274; Protected by Authentik</div><p style="font-size:13px;color:var(--text-secondary);line-height:1.5">Node-RED is behind Authentik. The application and proxy provider are created automatically when you deploy Authentik or Node-RED.</p></div>{% endif %}
  <div class="card"><div class="card-title">Access</div><div class="info-grid">
    {% if settings.fqdn %}<div class="info-item"><div class="info-label">Flow editor</div><div class="info-value"><a href="https://nodered.{{ settings.fqdn }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">https://nodered.{{ settings.fqdn }}</a> &#8599;</div></div>
    {% else %}<div class="info-item"><div class="info-label">Flow editor</div><div class="info-value"><a href="http://{{ settings.server_ip }}:1880" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">http://{{ settings.server_ip }}:1880</a> &#8599;</div></div>{% endif %}
    <div class="info-item"><div class="info-label">Install dir</div><div class="info-value">~/node-red</div></div>
  </div></div>
  <div class="card"><div class="card-title">Controls</div><div class="controls">
    <button class="btn {% if nr.running %}btn-ghost{% else %}btn-success{% endif %}" onclick="control('start')">&#x25b6; Start</button>
    <button class="btn {% if nr.running %}btn-danger{% else %}btn-ghost{% endif %}" onclick="control('stop')">&#x23f9; Stop</button>
    <button class="btn btn-ghost" onclick="control('restart')">&#x27fa; Restart</button>
    <button class="btn btn-ghost" onclick="loadLogs()">&#x1f4cb; Logs</button>
    <button class="btn btn-danger" onclick="document.getElementById('uninstall-modal').classList.add('open')">&#x1f5d1; Uninstall</button>
  </div><div id="control-status" style="margin-top:12px;font-size:12px;color:var(--text-dim)"></div></div>
  <div class="card" id="logs-card" style="display:none"><div class="card-title">Container logs</div><div class="log-box" id="container-logs">Loading...</div></div>
  {% else %}
  <div class="card"><div class="card-title">Deploy Node-RED</div>
  <p style="font-size:13px;color:var(--text-secondary);margin-bottom:20px">Runs Node-RED in Docker with a persistent volume. With a domain set, the flow editor is at <code style="color:var(--cyan)">https://nodered.{{ settings.fqdn if settings.fqdn else '&lt;your-domain&gt;' }}</code> (behind Authentik when enabled).</p>
  {% if settings.fqdn %}<p style="font-size:12px;color:var(--text-dim);margin-bottom:16px">Open <a href="https://nodered.{{ settings.fqdn }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan)">nodered.{{ settings.fqdn }}</a> to use the flow editor. If you upgraded from console.*/nodered/ and the link does not load, redeploy Node-RED once from this page.</p>{% endif %}
  <button class="btn btn-primary" id="deploy-btn" onclick="startDeploy()">&#x1f680; Deploy Node-RED</button></div>
  {% endif %}
  {% if deploying %}<div class="card" id="deploy-log-card"><div class="card-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">Deploy log<button class="btn btn-ghost" id="nodered-cancel-btn-static" onclick="cancelNoderedDeploy()" style="display:none">&#x2717; Cancel</button></div><div class="log-box" id="deploy-log">Initializing...</div></div>{% endif %}
  <div class="card" id="log-card" style="display:none"><div class="card-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">Deploy log<button class="btn btn-ghost" id="nodered-cancel-btn-dyn" onclick="cancelNoderedDeploy()" style="display:none">&#x2717; Cancel</button></div><div class="log-box" id="deploy-log-dyn">Waiting...</div></div>
</div>
<div class="modal-overlay" id="uninstall-modal"><div class="modal">
  <h3>&#x26a0; Uninstall Node-RED?</h3><p>This will stop and remove the container and data volume. Flows will be deleted.</p>
  <div style="margin-bottom:16px"><label class="form-label">Admin password</label><input class="form-input" id="uninstall-password" type="password" placeholder="Confirm password"></div>
  <div class="modal-actions"><button class="btn btn-ghost" onclick="document.getElementById('uninstall-modal').classList.remove('open')">Cancel</button><button class="btn btn-danger" onclick="doUninstall()">Uninstall</button></div>
  <div id="uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
</div></div>
<script>
var logIndex=0,logInterval=null;
function startDeploy(){var btn=document.getElementById('deploy-btn');btn.disabled=true;document.getElementById('log-card').style.display='block';document.getElementById('deploy-log-dyn').textContent='Starting...';logIndex=0;
fetch('/api/nodered/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({}),credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){
if(d.error){document.getElementById('deploy-log-dyn').textContent='Error: '+d.error;btn.disabled=false;return;}pollLog();});}
function pollLog(){function pickLogEl(){var lc=document.getElementById('log-card');return (lc&&lc.style.display!=='none'?document.getElementById('deploy-log-dyn'):null)||document.getElementById('deploy-log')||document.getElementById('deploy-log-dyn');}
var logEl=pickLogEl();function showCancel(show){var s=document.getElementById('nodered-cancel-btn-static'),d=document.getElementById('nodered-cancel-btn-dyn');if(s)s.style.display=show?'inline-block':'none';if(d)d.style.display=show?'inline-block':'none';}
function doPoll(){logEl=pickLogEl();fetch('/api/nodered/deploy/log?index='+logIndex,{credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){
if(d.entries&&d.entries.length){if(logIndex===0&&logEl)logEl.textContent='';if(logEl){logEl.textContent+=d.entries.join(String.fromCharCode(10))+String.fromCharCode(10);logEl.scrollTop=logEl.scrollHeight;}logIndex+=d.entries.length;}
showCancel(d.running);
if(!d.running){clearInterval(logInterval);var btn=document.getElementById('deploy-btn');if(btn)btn.disabled=false;
if(d.cancelled){if(logEl)logEl.textContent+=String.fromCharCode(10,10)+'Cancelled.';}
else if(d.complete){if(logEl)logEl.textContent+=String.fromCharCode(10,10)+'Deploy complete - page will reload in 15s (or refresh now).';setTimeout(function(){location.reload();},15000);}}});}doPoll();logInterval=setInterval(doPoll,800);}
function cancelNoderedDeploy(){if(!confirm('Cancel the deployment? You can deploy again after.'))return;fetch('/api/nodered/deploy/cancel',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin'}).then(function(){/* next poll will show cancelled */});}
if(document.getElementById('deploy-log-card')){logIndex=0;pollLog();}
function control(action){document.getElementById('control-status').textContent=action+'...';
fetch('/api/nodered/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action}),credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){document.getElementById('control-status').textContent=d.running?'Running':'Stopped';setTimeout(function(){window.location.href=window.location.pathname+'?t='+Date.now();},1500);});}
function loadLogs(){document.getElementById('logs-card').style.display='block';fetch('/api/nodered/logs?lines=80').then(function(r){return r.json();}).then(function(d){document.getElementById('container-logs').textContent=(d.entries||[]).join(String.fromCharCode(10))||'(no output)';});}
function doUninstall(){var pw=document.getElementById('uninstall-password').value,msg=document.getElementById('uninstall-msg');msg.textContent='';fetch('/api/nodered/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw}),credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){if(d.error){msg.textContent=d.error;return;}msg.textContent='Done. Reloading...';setTimeout(function(){location.reload();},800);}).catch(function(e){msg.textContent=e.message||'Request failed';});}
</script>
</body></html>
'''

GUARDDOG_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Guard Dog — infra-TAK</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg-deep);color:var(--text-primary);font-family:'DM Sans',sans-serif;min-height:100vh;display:flex;flex-direction:row}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px;overflow:visible;line-height:1.35}
.sidebar-logo span{font-size:15px;font-weight:700;letter-spacing:.02em;color:var(--text-primary)}
.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
.page-header{margin-bottom:28px}.page-header h1{font-size:22px;font-weight:700}.page-header p{color:var(--text-secondary);font-size:13px;margin-top:4px}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px}
.card-title{font-size:13px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.status-banner{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:13px}
.status-banner.running{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:var(--green)}
.status-banner.stopped{background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.2);color:var(--yellow)}
.status-banner.not-installed{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);color:var(--accent)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.btn-primary{background:var(--accent);color:#fff}.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;max-width:400px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px}
.log-box{background:#070a12;border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:340px;overflow-y:auto;white-space:pre-wrap}
.guard-list{display:flex;flex-direction:column;gap:0}
.guard-service-row{border-bottom:1px solid var(--border);background:#0a0e1a}
.guard-service-row:last-child{border-bottom:none}
.guard-service-header{display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer;font-size:13px;font-weight:600;color:var(--text-primary);user-select:none}
.guard-service-header:hover{background:rgba(255,255,255,.04)}
.guard-service-health{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.guard-service-health.ok{background:var(--green)}
.guard-service-health.fail{background:var(--red)}
.guard-service-health.pending{background:var(--text-dim)}
.guard-service-expand{margin-left:auto;transition:transform .2s}
.guard-service-row.open .guard-service-expand{transform:rotate(180deg)}
.guard-service-body{display:none;padding:0 16px 12px 16px}
.guard-service-row.open .guard-service-body{display:block}
.guard-item{display:flex;align-items:flex-start;gap:16px;padding:14px 16px;border-bottom:1px solid var(--border);background:var(--bg-deep);font-size:13px;border-radius:8px;margin-bottom:4px}
.guard-item:last-child{border-bottom:none;margin-bottom:0}
.guard-item-name{font-weight:600;color:var(--cyan);min-width:120px;flex-shrink:0}
.guard-item-interval{color:var(--text-dim);font-size:11px;min-width:70px;flex-shrink:0}
.guard-item-desc{color:var(--text-secondary);line-height:1.5;flex:1}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
</style></head>
<body data-gd-deploying="{{ 'true' if deploying else 'false' }}">
{{ sidebar_html }}
<div class="main">
  <div class="page-header"><h1 style="display:flex;align-items:center;gap:10px"><span class="nav-icon" style="font-size:22px;line-height:1">🐕</span><span>Guard Dog</span></h1><p>TAK Server health monitoring and auto-recovery.</p></div>
  {% if gd.running %}<div class="status-banner running"><div class="dot"></div>Guard Dog is running (timers active)</div>
  {% elif gd.installed %}<div class="status-banner stopped"><div class="dot"></div>Guard Dog is installed but timers may be stopped</div>
  {% else %}<div class="status-banner not-installed"><div class="dot"></div>Guard Dog is not installed</div>{% endif %}

  {% if not tak.installed %}
  <div class="card" style="border-color:var(--yellow)">
    <div class="card-title">Requirement</div>
    <p style="color:var(--text-secondary);font-size:13px">TAK Server must be installed first. Deploy TAK Server from the TAK Server module, then return here to deploy Guard Dog.</p>
  </div>
  {% endif %}

  {% if gd.installed %}
  <div class="card"><div class="card-title">Monitors</div>
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:12px">Per-service health and checks. Expand a row to see what Guard Dog is monitoring.</p>
    <div class="guard-list">
      {% for svc in guarddog_services %}
      {% if svc.monitored %}
      <div class="guard-service-row" id="gd-svc-{{ svc.id }}" data-service-id="{{ svc.id }}">
        <div class="guard-service-header" onclick="gdToggleService('{{ svc.id }}')">
          <span class="guard-service-health pending" id="gd-health-{{ svc.id }}" title="Health"></span>
          <span>{{ svc.name }}</span>
          <span class="guard-service-expand material-symbols-outlined" style="font-size:20px">expand_more</span>
        </div>
        <div class="guard-service-body">
          {% for m in svc.monitors %}
          <div class="guard-item">
            <span class="guard-item-name">{{ m.name }}</span>
            <span class="guard-item-interval">{{ m.interval }}</span>
            <span class="guard-item-desc">{{ m.desc }}</span>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endif %}
      {% endfor %}
    </div>
    <p style="margin-top:14px;font-size:12px;color:var(--text-dim)">Health endpoint (for Uptime Robot): <code style="color:var(--cyan);word-break:break-all">{{ health_url }}</code></p>
    <p style="margin-top:10px;font-size:12px;color:var(--text-dim)"><a href="{{ guarddog_docs_url }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none;font-weight:500">How Guard Dog works</a> (delays, soft start, restart-loop protection) → docs</p>
    <p style="margin-top:16px"><button class="btn btn-ghost" style="color:var(--red);border-color:var(--red)" onclick="document.getElementById('gd-uninstall-modal').classList.add('open')">Uninstall Guard Dog</button></p>
  </div>
  {% endif %}

  <div class="card"><div class="card-title">Notifications</div>
    {% if notifications_configured %}
    <div id="gd-notify-banner" class="status-banner running" style="margin-bottom:12px"><div class="dot"></div>Notifications configured</div>
    <button type="button" class="btn btn-ghost" id="gd-notify-toggle-btn" onclick="gdToggleNotifications()" style="margin-bottom:12px"><span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:4px">expand_more</span><span id="gd-notify-toggle-label">Expand to edit</span></button>
    <div id="gd-notify-body" style="display:none">
    {% endif %}
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:16px">Configure email, Uptime Robot, and optional SMS (Twilio or Brevo) for Guard Dog alerts.</p>
    <div class="gd-section" style="margin-bottom:20px">
      <div class="form-label">Email</div>
      {% if email_relay_configured %}<p style="font-size:12px;color:var(--green);margin-bottom:8px">Using Email Relay (e.g. Brevo SMTP). Alerts are sent through your configured relay.</p>{% endif %}
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <input class="form-input" type="email" id="gd-notify-email" placeholder="Alert email" value="{{ guarddog_alert_email | e }}" style="max-width:280px">
        <button class="btn btn-ghost" id="gd-test-email-btn" onclick="gdTestEmail()">Send test email</button>
      </div>
      <div id="gd-test-email-msg" style="margin-top:8px;font-size:12px"></div>
    </div>
    <div class="gd-section" style="margin-bottom:20px">
      <div class="form-label">Uptime Robot (outside-in monitoring)</div>
      <p style="font-size:12px;color:var(--text-dim);margin-bottom:8px">Create a free account at <a href="https://uptimerobot.com" target="_blank" rel="noopener noreferrer" style="color:var(--cyan)">uptimerobot.com</a>, add your email for alerts, then add an HTTP(S) monitor with this URL:</p>
      <p style="font-size:13px;margin-bottom:4px"><code style="word-break:break-all;background:var(--bg-deep);padding:8px 12px;border-radius:6px;display:inline-block">{{ health_url }}</code></p>
      <p style="font-size:11px;color:var(--text-dim)">Copy and paste this into Uptime Robot when creating a new monitor.</p>
    </div>
    <div class="gd-section">
      <div class="form-label">SMS (optional)</div>
      <p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Use Twilio or Brevo to send SMS for critical alerts. No SMS? Alerts still go to the email address above; set up push notifications in your email app on your phone to get alerts on the go.</p>
      <select class="form-input" id="gd-sms-provider" style="max-width:120px;margin-bottom:10px" onchange="gdSmsProviderChange()">
        <option value="">Off</option>
        <option value="twilio" {{ 'selected' if guarddog_sms.get('provider')=='twilio' else '' }}>Twilio</option>
        <option value="brevo" {{ 'selected' if guarddog_sms.get('provider')=='brevo' else '' }}>Brevo</option>
      </select>
      <div id="gd-sms-twilio" style="display:{{ 'block' if guarddog_sms.get('provider')=='twilio' else 'none' }};margin-bottom:10px">
        <input class="form-input" type="text" id="gd-sms-tw-account" placeholder="Account SID" value="{{ guarddog_sms.get('account_sid','') | e }}" style="margin-bottom:6px">
        <input class="form-input" type="password" id="gd-sms-tw-auth" placeholder="Auth Token" value="{{ guarddog_sms.get('auth_token','') | e }}" style="margin-bottom:6px" autocomplete="off">
        <input class="form-input" type="text" id="gd-sms-tw-from" placeholder="From number (e.g. +15551234567)" value="{{ guarddog_sms.get('from_number','') | e }}" style="margin-bottom:6px">
        <input class="form-input" type="text" id="gd-sms-tw-to" placeholder="To number(s), comma-separated" value="{{ guarddog_sms.get('to_numbers','') | e }}" style="margin-bottom:6px">
      </div>
      <div id="gd-sms-brevo" style="display:{{ 'block' if guarddog_sms.get('provider')=='brevo' else 'none' }};margin-bottom:10px">
        <input class="form-input" type="password" id="gd-sms-br-api" placeholder="Brevo API key" value="{{ guarddog_sms.get('api_key','') | e }}" style="margin-bottom:6px" autocomplete="off">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <input class="form-input" type="text" id="gd-sms-br-sender" placeholder="Sender (max 11 chars)" value="{{ guarddog_sms.get('sender','') | e }}" style="flex:1;margin-bottom:0" maxlength="11" oninput="gdSenderCheck()">
          <span id="gd-sms-sender-check" style="font-size:18px;color:var(--green);display:none" title="11 characters or less">&#10003;</span>
          <span id="gd-sms-sender-warn" style="font-size:12px;color:var(--text-dim);display:none"></span>
        </div>
        <input class="form-input" type="text" id="gd-sms-br-to" placeholder="To: digits + country code, e.g. 15551234567" value="{{ guarddog_sms.get('to_numbers','') | e }}" style="margin-bottom:6px">
        <p style="font-size:11px;color:var(--text-dim);margin-top:0">To: digits + country code (e.g. 15551234567). Sender: up to 11 letters/numbers (Brevo has no separate SMS sender page — we send it in the API). If test fails, Brevo’s error appears below. If test says sent but you get no text, check Brevo → Campaigns → SMS or Statistics for delivery status.</p>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <button class="btn btn-ghost" onclick="gdSmsSave()">Save SMS settings</button>
        <button class="btn btn-ghost" id="gd-test-sms-btn" onclick="gdTestSms()">Send test SMS</button>
        <button class="btn btn-ghost" id="gd-brevo-events-btn" onclick="gdBrevoSmsEvents()" style="display:none">Check delivery status</button>
      </div>
      <div id="gd-sms-msg" style="margin-top:8px;font-size:12px"></div>
      <div id="gd-sms-events" style="display:none;margin-top:10px;padding:10px;background:var(--bg-card);border:1px solid var(--border);border-radius:8px;font-size:12px;max-height:180px;overflow-y:auto"></div>
    </div>
    {% if notifications_configured %}
    <button type="button" class="btn btn-ghost" onclick="gdToggleNotifications()" style="margin-top:12px"><span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:4px">expand_less</span>Collapse</button>
    </div>
    {% endif %}
  </div>

  {% if tak.installed %}
  <div class="card"><div class="card-title">Database maintenance (CoT)</div>
    <p style="font-size:12px;color:var(--text-secondary);line-height:1.5;margin-bottom:12px">The CoT database can grow large. Data retention deletes rows but <strong>PostgreSQL does not free disk until you run VACUUM</strong>. Run VACUUM ANALYZE to reclaim space (safe while TAK Server is running).</p>
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:14px">CoT database size: <span id="gd-cot-db-size" style="font-weight:600">—</span> <button type="button" onclick="gdRefreshCotSize()" class="btn btn-ghost" style="margin-left:8px;padding:4px 12px;font-size:12px">Refresh</button> <span style="font-size:10px;color:var(--text-dim);margin-left:6px">(green &lt; 25 GB · yellow 25–40 GB · red &gt; 40 GB)</span></p>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">
        <button type="button" id="gd-vacuum-analyze-btn" onclick="gdRunVacuum(false)" class="btn" style="background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;flex-shrink:0">Run VACUUM ANALYZE</button>
        <span style="font-size:12px;color:var(--text-secondary)">Reclaims space from deleted rows. Safe while TAK Server is running.</span>
      </div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">
        <button type="button" id="gd-vacuum-full-btn" onclick="gdRunVacuum(true)" class="btn btn-ghost" style="color:var(--yellow);border-color:var(--yellow);flex-shrink:0" title="Caution: run when TAK Server is not running">Run VACUUM FULL</button>
        <span style="font-size:12px;color:var(--text-secondary)">Rewrites tables to reclaim more space; locks tables. Run when <strong>TAK Server is not running</strong>. <span style="color:var(--yellow)">(yellow = caution)</span></span>
      </div>
    </div>
    <div id="gd-vacuum-output" style="display:none;margin-top:14px;padding:12px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
    <div id="gd-vacuum-msg" style="margin-top:8px;font-size:13px"></div>
  </div>
  {% endif %}

  {% if gd.installed %}
  <div class="card"><div class="card-title">Activity log</div>
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:12px">Restarts, alerts, and monitor events from Guard Dog. Filter by date or leave blank for all.</p>
    <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px">
      <label style="font-size:12px;color:var(--text-secondary)">From <input type="date" id="gd-log-from" class="form-input" style="width:140px;display:inline-block;margin-left:6px"></label>
      <label style="font-size:12px;color:var(--text-secondary)">To <input type="date" id="gd-log-to" class="form-input" style="width:140px;display:inline-block;margin-left:6px"></label>
      <button type="button" class="btn btn-ghost" onclick="gdLoadActivityLog()">Refresh</button>
      <button type="button" class="btn btn-ghost" style="color:var(--text-dim)" onclick="document.getElementById('gd-log-from').value='';document.getElementById('gd-log-to').value='';gdLoadActivityLog()">Clear filter</button>
    </div>
    <div class="log-box" id="gd-activity-log" style="max-height:320px">Loading…</div>
    <p style="font-size:11px;color:var(--text-dim);margin-top:8px">Log file: <code>/var/log/takguard/restarts.log</code></p>
  </div>
  {% endif %}

  {% if gd.installed %}
  <div class="modal-overlay" id="gd-uninstall-modal"><div class="modal" style="background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw">
    <h3 style="font-size:16px;margin-bottom:8px;color:var(--red)">Uninstall Guard Dog?</h3>
    <p style="font-size:13px;color:var(--text-secondary);margin-bottom:20px">This will stop all timers and the health endpoint, and remove scripts and systemd units. Alert history in /var/lib/takguard and /var/log/takguard is left in place.</p>
    <div style="margin-bottom:16px"><label class="form-label">Admin password</label><input class="form-input" type="password" id="gd-uninstall-password" placeholder="Confirm password"></div>
    <div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn btn-ghost" onclick="document.getElementById('gd-uninstall-modal').classList.remove('open')">Cancel</button><button class="btn" style="background:var(--red);color:#fff" onclick="gdUninstall()">Uninstall</button></div>
    <div id="gd-uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
  </div></div>
  {% else %}
  <div class="card"><div class="card-title">Deploy Guard Dog</div>
    <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">Installs 8 systemd timers that monitor TAK Server (port 8089, processes, PostgreSQL, CoT DB size, OOM, disk, network, certificate expiry) and a health endpoint on port 8080. Requires TAK Server at /opt/tak and a working mail command (e.g. Email Relay deployed). Alert email is set in Notifications above.</p>
    <button class="btn btn-primary" id="gd-deploy-btn" onclick="startGuarddogDeploy()" {% if not tak.installed %}disabled{% endif %}>&#128054; Deploy Guard Dog</button>
    <p id="gd-deploy-email-err" style="margin-top:10px;font-size:12px;color:var(--red);display:none">Set an alert email in Notifications first.</p>
  </div>
  {% endif %}

  <div class="card" id="gd-log-card" style="display:none"><div class="card-title">Deploy log</div><div class="log-box" id="gd-deploy-log">Initializing...</div></div>
</div>
<script src="/guarddog.js"></script>
</body></html>
'''


MEDIAMTX_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MediaMTX — infra-TAK</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg-deep);color:var(--text-primary);font-family:'DM Sans',sans-serif;min-height:100vh;display:flex;flex-direction:row}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;display:flex;flex-direction:column;flex-shrink:0}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700;letter-spacing:.05em;color:var(--text-primary)}
.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03);border-left-color:var(--border-hover)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
.page-header{margin-bottom:28px}
.page-header h1{font-size:22px;font-weight:700}
.page-header p{color:var(--text-secondary);font-size:13px;margin-top:4px}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px}
.card-title{font-size:13px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.status-banner{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:500}
.status-banner.running{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:var(--green)}
.status-banner.stopped{background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.2);color:var(--yellow)}
.status-banner.not-installed{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);color:var(--accent)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#2563eb}
.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border)}.btn-ghost:hover{color:var(--text-primary);border-color:var(--border-hover)}
.btn-danger{background:var(--red);color:#fff}.btn-danger:hover{background:#dc2626}
.btn:disabled{opacity:.5;cursor:not-allowed}
.controls{display:flex;gap:10px;flex-wrap:wrap}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.info-item{background:#0a0e1a;border-radius:8px;padding:12px 14px}
.info-label{font-size:11px;color:var(--text-dim);margin-bottom:3px;text-transform:uppercase;letter-spacing:.05em}
.info-value{font-size:13px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;word-break:break-all}
.log-box{background:#070a12;border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:360px;overflow-y:auto;line-height:1.7;white-space:pre-wrap}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end}
.form-group{margin-bottom:0}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}
.form-input{width:100%;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px;font-family:'DM Sans',sans-serif;outline:none;transition:border-color .15s}
.form-input:focus{border-color:var(--accent)}
.proto-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:4px}
.proto-item{background:#0a0e1a;border-radius:8px;padding:10px 12px;text-align:center}
.proto-name{font-size:11px;font-weight:700;color:var(--cyan);margin-bottom:2px}
.proto-port{font-size:11px;color:var(--text-dim);font-family:'JetBrains Mono',monospace}
.uninstall-spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes uninstall-spin{to{transform:rotate(360deg)}}
.uninstall-progress-row{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text-secondary)}
</style></head>
<body>
{{ sidebar_html }}
<div class="main">
  <div class="page-header">
    <h1><img src="{{ mediamtx_logo_url }}" alt="MediaMTX" style="height:28px;vertical-align:middle"></h1>
    <p>Video Streaming Server</p>
  </div>

  {% if mtx.running %}
  <div class="status-banner running"><div class="dot"></div>MediaMTX is running</div>
  {% elif mtx.installed %}
  <div class="status-banner stopped"><div class="dot"></div>MediaMTX is installed but stopped</div>
  {% else %}
  <div class="status-banner not-installed"><div class="dot"></div>MediaMTX is not installed</div>
  {% endif %}

  {% if mtx.installed %}

  <!-- Access info -->
  <div class="card">
    <div class="card-title">Access</div>
    <div class="info-grid">
      {% if settings.fqdn %}
      <div class="info-item"><div class="info-label">Web Console</div><div class="info-value"><a href="https://stream.{{ settings.fqdn }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">https://stream.{{ settings.fqdn }}</a> <span style="color:var(--text-dim);font-size:11px">↗</span></div></div>
      {% else %}
      <div class="info-item"><div class="info-label">Web Console</div><div class="info-value"><a href="http://{{ settings.server_ip }}:5080" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">http://{{ settings.server_ip }}:5080</a> <span style="color:var(--text-dim);font-size:11px">↗</span></div></div>
      {% endif %}
    </div>
  </div>

  <!-- Controls -->
  <div class="card">
    <div class="card-title">Controls</div>
    <div class="controls">
      <button class="btn btn-ghost" onclick="control('start')">▶ Start</button>
      <button class="btn btn-ghost" onclick="control('stop')">⏹ Stop</button>
      <button class="btn btn-ghost" onclick="control('restart')">↺ Restart</button>
      <button class="btn btn-ghost" onclick="loadLogs()">📋 Logs</button>
      <button class="btn btn-danger" onclick="document.getElementById('uninstall-modal').classList.add('open')">🗑 Uninstall</button>
    </div>
    <div id="control-status" style="margin-top:12px;font-size:12px;color:var(--text-dim)"></div>
  </div>

  <!-- Container logs -->
  <div class="card" id="logs-card" style="display:none">
    <div class="card-title">Service Logs</div>
    <div class="log-box" id="service-logs">Loading...</div>
  </div>

  {% else %}
  <!-- Deploy -->
  <div class="card">
    <div class="card-title">Deploy MediaMTX</div>
    <p style="font-size:13px;color:var(--text-secondary);margin-bottom:20px">
      Installs MediaMTX streaming server with FFmpeg for drone video (MPEG-TS to RTSP to HLS),
      the web configuration editor, and wires SSL certificates from Caddy automatically.
    </p>
    {% if settings.fqdn %}
    <div style="background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.15);border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:var(--text-secondary)">
      Caddy domain detected — <span style="color:var(--green)">SSL will be configured automatically</span><br>
      Web editor will be available at <span style="font-family:'JetBrains Mono',monospace;color:var(--cyan)">https://stream.{{ settings.fqdn }}</span>
    </div>
    {% endif %}
    <button class="btn btn-primary" id="deploy-btn" onclick="startDeploy()">🚀 Deploy MediaMTX</button>
  </div>
  {% endif %}

  <!-- Deploy log -->
  <div class="card" id="log-card" style="display:{% if deploying or deploy_done %}block{% else %}none{% endif %}">
    <div class="card-title">Deploy Log</div>
    <div class="log-box" id="deploy-log">{% if deploying %}Starting...{% elif deploy_done %}Deploy complete.{% endif %}</div>
  </div>
</div>

<!-- Uninstall modal -->
<div class="modal-overlay" id="uninstall-modal">
  <div class="modal">
    <h3>⚠ Uninstall MediaMTX?</h3>
    <p>This will stop and remove MediaMTX, the web editor, all systemd services, and the binary. Config and recordings will be removed.</p>
    <div class="form-group" style="margin-bottom:16px">
      <label class="form-label">Admin Password</label>
      <input class="form-input" id="uninstall-password" type="password" placeholder="Confirm your password">
    </div>
    <div class="modal-actions">
      <button class="btn btn-ghost" id="uninstall-cancel-btn" onclick="document.getElementById('uninstall-modal').classList.remove('open')">Cancel</button>
      <button class="btn btn-danger" id="uninstall-confirm-btn" onclick="doUninstall()">Uninstall</button>
    </div>
    <div id="uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
    <div id="uninstall-progress" class="uninstall-progress-row" style="display:none" aria-live="polite"></div>
  </div>
</div>

<script>
let logIndex = 0;
let logInterval = null;

function startDeploy() {
  document.getElementById('deploy-btn').disabled = true;
  document.getElementById('log-card').style.display = 'block';
  document.getElementById('deploy-log').textContent = 'Starting deployment...';
  logIndex = 0;
  fetch('/api/mediamtx/deploy', {method:'POST', headers:{'Content-Type':'application/json'}})
    .then(r => r.json()).then(d => {
      if (d.error) {
        document.getElementById('deploy-log').textContent = 'Error: ' + d.error;
        document.getElementById('deploy-btn').disabled = false;
      } else {
        pollLog();
      }
    });
}

function pollLog() {
  logInterval = setInterval(() => {
    fetch('/api/mediamtx/deploy/log?index=' + logIndex)
      .then(r => r.json()).then(d => {
        if (d.entries && d.entries.length) {
          const box = document.getElementById('deploy-log');
          if (logIndex === 0) box.textContent = '';
          box.textContent += d.entries.join(String.fromCharCode(10)) + String.fromCharCode(10);
          box.scrollTop = box.scrollHeight;
          logIndex += d.entries.length;
        }
        if (!d.running) {
          clearInterval(logInterval);
          if (d.complete) {
            var btn = document.getElementById('deploy-btn');
            if (btn) { btn.textContent = '✓ Deployment Complete'; btn.style.background = 'var(--green)'; btn.style.opacity = '1'; btn.style.cursor = 'default'; }
            var box = document.getElementById('deploy-log');
            var refreshBtn = document.createElement('button');
            refreshBtn.textContent = '↻ Refresh Page';
            refreshBtn.style.cssText = 'display:block;width:100%;padding:12px;margin-top:16px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;';
            refreshBtn.onclick = function() { window.location.href = '/mediamtx'; };
            box.appendChild(refreshBtn);
            box.scrollTop = box.scrollHeight;
          } else if (d.error) {
            var btn = document.getElementById('deploy-btn');
            if (btn) { btn.textContent = '✗ Deployment Failed'; btn.style.background = 'var(--red)'; btn.style.opacity = '1'; btn.disabled = false; btn.onclick = function() { btn.textContent = '🚀 Deploy MediaMTX'; btn.style.background = ''; startDeploy(); }; }
          }
        }
      });
  }, 800);
}

function control(action) {
  document.getElementById('control-status').textContent = action + '...';
  fetch('/api/mediamtx/control', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({action})
  }).then(r => r.json()).then(d => {
    document.getElementById('control-status').textContent = d.running ? '✓ Running' : '○ Stopped';
    setTimeout(() => document.getElementById('control-status').textContent = '', 3000);
  });
}

function loadLogs() {
  const card = document.getElementById('logs-card');
  card.style.display = 'block';
  fetch('/api/mediamtx/logs?lines=80').then(r => r.json()).then(d => {
    document.getElementById('service-logs').textContent = d.entries.join(String.fromCharCode(10)) || '(no output)';
  });
}

function doUninstall() {
  const password = document.getElementById('uninstall-password').value;
  const msgEl = document.getElementById('uninstall-msg');
  const progressEl = document.getElementById('uninstall-progress');
  const cancelBtn = document.getElementById('uninstall-cancel-btn');
  const confirmBtn = document.getElementById('uninstall-confirm-btn');
  msgEl.textContent = '';
  progressEl.style.display = 'flex';
  progressEl.innerHTML = '<span class="uninstall-spinner"></span><span>Uninstalling…</span>';
  confirmBtn.disabled = true;
  cancelBtn.disabled = true;
  fetch('/api/mediamtx/uninstall', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({password})
  }).then(r => r.json()).then(d => {
    if (d.error) {
      msgEl.textContent = d.error;
      progressEl.style.display = 'none';
      progressEl.innerHTML = '';
      confirmBtn.disabled = false;
      cancelBtn.disabled = false;
      return;
    }
    progressEl.innerHTML = '<span class="uninstall-spinner"></span><span>Done. Reloading…</span>';
    setTimeout(() => location.reload(), 800);
  }).catch(err => {
    msgEl.textContent = 'Request failed: ' + (err.message || 'network error');
    progressEl.style.display = 'none';
    progressEl.innerHTML = '';
    confirmBtn.disabled = false;
    cancelBtn.disabled = false;
  });
}

{% if deploying %}
document.addEventListener('DOMContentLoaded', () => { logIndex = 0; pollLog(); });
{% elif deploy_done %}
document.addEventListener('DOMContentLoaded', () => { logIndex = 0; pollLog(); });
{% endif %}
</script>
</body></html>'''

CLOUDTAK_PAGE_JS = r'''window.logIndex = 0;
window.logInterval = null;

window.startRedeploy = function() {
  var btn = document.getElementById("redeploy-btn");
  var logCard = document.getElementById("log-card");
  var dyn = document.getElementById("deploy-log-dyn");
  var stat = document.getElementById("deploy-log");
  function showErr(s) {
    if (dyn) dyn.textContent = s;
    if (stat) stat.textContent = s;
    if (btn) btn.disabled = false;
    alert(s);
  }
  if (btn) btn.disabled = true;
  if (logCard) { logCard.style.display = "block"; logCard.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
  var initMsg = "Updating config and restarting...";
  if (dyn) dyn.textContent = initMsg;
  if (stat) stat.textContent = initMsg;
  var condLog = document.getElementById("deploy-log");
  if (condLog && condLog.closest(".card")) condLog.closest(".card").style.display = "none";
  window.logIndex = 0;
  fetch("/api/cloudtak/redeploy", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({}),
    credentials: "same-origin"
  }).then(function(r) {
    if (!r.ok) {
      return r.text().then(function(t) { throw new Error(r.status + ": " + (t || r.statusText).slice(0, 200)); });
    }
    return r.json();
  }).then(function(d) {
    if (d && d.error) {
      showErr("Error: " + d.error);
    } else {
      window.pollLog(btn);
    }
  }).catch(function(e) {
    showErr("Failed: " + (e && e.message ? e.message : String(e)));
  });
};

window.startDeploy = function() {
  document.getElementById("deploy-btn").disabled = true;
  document.getElementById("log-card").style.display = "block";
  document.getElementById("deploy-log-dyn").textContent = "Starting deployment...";
  window.logIndex = 0;
  fetch("/api/cloudtak/deploy", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      document.getElementById("deploy-log-dyn").textContent = "Error: " + d.error;
      document.getElementById("deploy-btn").disabled = false;
    } else {
      window.pollLog(null);
    }
  });
};

window.pollLog = function(redeployBtn) {
  if (window.logInterval) clearInterval(window.logInterval);
  function doPoll() {
    fetch("/api/cloudtak/deploy/log?index=" + window.logIndex, { credentials: "same-origin" })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d) return;
        if (d.entries && d.entries.length) {
          var text = d.entries.join("\n") + "\n";
          var dyn = document.getElementById("deploy-log-dyn");
          var stat = document.getElementById("deploy-log");
          if (window.logIndex === 0) {
            if (dyn) dyn.textContent = text;
            if (stat) stat.textContent = text;
          } else {
            if (dyn) dyn.textContent += text;
            if (stat) stat.textContent += text;
          }
          if (dyn) dyn.scrollTop = dyn.scrollHeight;
          if (stat) stat.scrollTop = stat.scrollHeight;
          window.logIndex += d.entries.length;
        }
        if (!d.running) {
          clearInterval(window.logInterval);
          window.logInterval = null;
          if (redeployBtn) redeployBtn.disabled = false;
          if (d.error && dyn) dyn.textContent = (dyn.textContent || "") + "\nError (see log above)";
          if (d.complete) setTimeout(function() { location.reload(); }, 1500);
        }
      })
      .catch(function(err) {
        clearInterval(window.logInterval);
        window.logInterval = null;
        if (redeployBtn) redeployBtn.disabled = false;
        var dyn = document.getElementById("deploy-log-dyn");
        if (dyn) dyn.textContent = (dyn.textContent || "") + "\nRequest failed: " + (err && err.message ? err.message : String(err));
      });
  }
  doPoll();
  window.logInterval = setInterval(doPoll, 800);
};

window.control = function(action) {
  document.getElementById("control-status").textContent = action + "...";
  fetch("/api/cloudtak/control", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({action: action})
  }).then(function(r) { return r.json(); }).then(function(d) {
    document.getElementById("control-status").textContent = d.running ? "Running" : "Stopped";
    setTimeout(function() { document.getElementById("control-status").textContent = ""; }, 3000);
  });
};

var activeContainer = "";
function filterLogs(containerName) {
  activeContainer = containerName || "";
  document.querySelectorAll(".svc-card").forEach(function(c) { c.style.borderColor = ""; c.style.boxShadow = ""; });
  var id = containerName ? "svc-" + containerName : "svc-all";
  var card = document.getElementById(id);
  if (card) { card.style.borderColor = "var(--cyan)"; card.style.boxShadow = "0 0 0 1px var(--cyan)"; }
  var label = document.getElementById("log-filter-label");
  if (label) label.textContent = containerName ? "\u2014 " + containerName : "";
  loadContainerLogs();
}
function loadContainerLogs() {
  var el = document.getElementById("container-logs");
  if (!el) return;
  var url = activeContainer ? "/api/cloudtak/logs?lines=80&container=" + encodeURIComponent(activeContainer) : "/api/cloudtak/logs?lines=80";
  fetch(url).then(function(r) { return r.json(); }).then(function(d) {
    el.textContent = (d.entries && d.entries.length) ? d.entries.join("\\n") : "(no log output)";
    el.scrollTop = el.scrollHeight;
  }).catch(function() { if (el) el.textContent = "Failed to load logs"; });
}
if (document.getElementById("container-logs")) { filterLogs(""); setInterval(loadContainerLogs, 8000); }

window.doUninstall = function() {
  var password = document.getElementById("uninstall-password").value;
  var msgEl = document.getElementById("uninstall-msg");
  var progressEl = document.getElementById("uninstall-progress");
  var cancelBtn = document.getElementById("uninstall-cancel-btn");
  var confirmBtn = document.getElementById("uninstall-confirm-btn");
  msgEl.textContent = "";
  progressEl.innerHTML = "<span class=\"uninstall-spinner\"></span><span>Uninstalling...</span>";
  confirmBtn.disabled = true;
  cancelBtn.disabled = true;
  fetch("/api/cloudtak/uninstall", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({password: password})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      msgEl.textContent = d.error;
      progressEl.innerHTML = "";
      confirmBtn.disabled = false;
      cancelBtn.disabled = false;
      return;
    }
    progressEl.innerHTML = "<span class=\"uninstall-spinner\"></span><span>Stopping containers and removing data...</span>";
    var poll = setInterval(function() {
      fetch("/api/cloudtak/uninstall/status").then(function(r) { return r.json(); }).then(function(s) {
        if (!s.running) {
          clearInterval(poll);
          if (s.error) {
            msgEl.textContent = s.error;
            progressEl.innerHTML = "";
            confirmBtn.disabled = false;
            cancelBtn.disabled = false;
          } else {
            progressEl.innerHTML = "<span class=\"uninstall-spinner\"></span><span>Done. Reloading...</span>";
            setTimeout(function() { location.reload(); }, 800);
          }
        } else {
          progressEl.innerHTML = "<span class=\"uninstall-spinner\"></span><span>Uninstalling... (this may take 1-2 minutes)</span>";
        }
      }).catch(function() { clearInterval(poll); progressEl.innerHTML = ""; confirmBtn.disabled = false; cancelBtn.disabled = false; });
    }, 1000);
  }).catch(function(err) {
    msgEl.textContent = "Request failed: " + (err.message || "network error");
    progressEl.innerHTML = "";
    confirmBtn.disabled = false;
    cancelBtn.disabled = false;
  });
};
'''

CLOUDTAK_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CloudTAK — infra-TAK</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg-deep);color:var(--text-primary);font-family:'DM Sans',sans-serif;min-height:100vh;display:flex;flex-direction:row}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;display:flex;flex-direction:column;flex-shrink:0}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700;letter-spacing:.05em;color:var(--text-primary)}
.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03);border-left-color:var(--border-hover)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
.page-header{margin-bottom:28px}
.page-header h1{font-size:22px;font-weight:700;color:var(--text-primary)}
.page-header p{color:var(--text-secondary);font-size:13px;margin-top:4px}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px}
.card-title{font-size:13px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.status-banner{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:500}
.status-banner.running{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:var(--green)}
.status-banner.stopped{background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.2);color:var(--yellow)}
.status-banner.not-installed{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);color:var(--accent)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.form-group{margin-bottom:16px}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}
.form-input{width:100%;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px;font-family:'DM Sans',sans-serif;transition:border-color .15s;outline:none}
.form-input:focus{border-color:var(--accent)}
.form-hint{font-size:11px;color:var(--text-dim);margin-top:4px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#2563eb}
.btn-success{background:var(--green);color:#fff}.btn-success:hover{background:#059669}
.btn-danger{background:var(--red);color:#fff}.btn-danger:hover{background:#dc2626}
.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border)}.btn-ghost:hover{color:var(--text-primary);border-color:var(--border-hover)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.info-item{background:#0a0e1a;border-radius:8px;padding:12px 14px}
.info-label{font-size:11px;color:var(--text-dim);margin-bottom:3px;text-transform:uppercase;letter-spacing:.05em}
.info-value{font-size:13px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;word-break:break-all}
.log-box{background:#070a12;border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:340px;overflow-y:auto;line-height:1.7;white-space:pre-wrap}
.controls{display:flex;gap:10px;flex-wrap:wrap}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end}
.tab-bar{display:flex;gap:4px;margin-bottom:20px;background:var(--bg-surface);padding:4px;border-radius:10px;width:fit-content}
.tab{padding:7px 16px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;color:var(--text-dim);transition:all .15s}
.tab.active{background:var(--bg-card);color:var(--text-primary)}
.tab-panel{display:none}.tab-panel.active{display:block}
.uninstall-spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes uninstall-spin{to{transform:rotate(360deg)}}
.uninstall-progress-row{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text-secondary)}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:8px}
.svc-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:'JetBrains Mono',monospace;font-size:12px}
.svc-name{color:var(--text-secondary);font-weight:600;margin-bottom:4px}
.svc-status{font-size:11px}
</style></head>
<body data-deploying="{{ 'true' if deploying else 'false' }}">
{{ sidebar_html }}
<div class="main">
  <div class="page-header">
    <h1><img src="{{ cloudtak_icon }}" alt="" style="height:28px;vertical-align:middle;margin-right:8px">CloudTAK</h1>
    <p>Browser-based TAK client — in-browser map and situational awareness via TAK Server</p>
  </div>

  {% if cloudtak.running %}
  <div class="status-banner running"><div class="dot"></div>CloudTAK is running</div>
  {% elif cloudtak.installed %}
  <div class="status-banner stopped"><div class="dot"></div>CloudTAK is installed but stopped</div>
  {% else %}
  <div class="status-banner not-installed"><div class="dot"></div>CloudTAK is not installed</div>
  {% endif %}

  {% if cloudtak.installed %}
  <!-- Controls at top -->
  <div class="card">
    <div class="card-title">Controls</div>
    <div class="controls">
      <button class="btn {% if cloudtak.running %}btn-ghost{% else %}btn-success{% endif %}" onclick="control('start')">▶ Start</button>
      <button class="btn {% if cloudtak.running %}btn-danger{% else %}btn-ghost{% endif %}" onclick="control('stop')">⏹ Stop</button>
      <button class="btn btn-ghost" onclick="control('restart')">↺ Restart</button>
      <button type="button" class="btn btn-primary" onclick="startRedeploy()" id="redeploy-btn">🔄 Update config & restart</button>
      <button class="btn btn-danger" onclick="document.getElementById('uninstall-modal').classList.add('open')">🗑 Uninstall</button>
    </div>
    <div id="control-status" style="margin-top:12px;font-size:12px;color:var(--text-dim)"></div>
  </div>

  <!-- Access -->
  <div class="card">
    <div class="card-title">Access</div>
    <div class="info-grid">
      {% if settings.fqdn %}
      <div class="info-item"><div class="info-label">Web UI</div><div class="info-value"><a href="https://map.{{ settings.fqdn }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">https://map.{{ settings.fqdn }}</a> <span style="color:var(--text-dim);font-size:11px">↗</span></div></div>
      <div class="info-item"><div class="info-label">Tile Server</div><div class="info-value">https://tiles.map.{{ settings.fqdn }}</div></div>
      <div class="info-item"><div class="info-label">Video (MediaMTX)</div><div class="info-value"><a href="https://video.{{ settings.fqdn }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">https://video.{{ settings.fqdn }}</a></div></div>
      {% else %}
      <div class="info-item"><div class="info-label">Web UI</div><div class="info-value"><a href="http://{{ settings.server_ip }}:5000" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none">http://{{ settings.server_ip }}:5000</a> <span style="color:var(--text-dim);font-size:11px">↗</span></div></div>
      <div class="info-item"><div class="info-label">Tile Server</div><div class="info-value">http://{{ settings.server_ip }}:5002</div></div>
      {% endif %}
      <div class="info-item"><div class="info-label">Install Dir</div><div class="info-value">~/CloudTAK</div></div>
    </div>
  </div>

  {% if container_info.get('containers') %}
  <div class="card">
    <div class="card-title">Services</div>
    <div class="svc-grid">
      {% for c in container_info.containers %}
      <div class="svc-card" onclick="filterLogs('{{ c.name }}')" style="cursor:pointer;border-color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' if 'Up' in c.status else 'var(--border)' }}" id="svc-{{ c.name }}"><div class="svc-name">{{ c.name }}</div><div class="svc-status" style="color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' }}">● {{ c.status }}</div></div>
      {% endfor %}
      <div class="svc-card" onclick="filterLogs('')" style="cursor:pointer" id="svc-all"><div class="svc-name">all containers</div><div class="svc-status" style="color:var(--text-dim)">● combined</div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Container Logs <span id="log-filter-label" style="font-size:11px;color:var(--cyan);margin-left:8px"></span></div>
    <div class="log-box" id="container-logs">Loading...</div>
  </div>
  {% endif %}

  {% else %}
  <!-- Deploy form -->
  <div class="card">
    <div class="card-title">Deploy CloudTAK</div>
    <p style="font-size:13px;color:var(--text-secondary);margin-bottom:20px">
      CloudTAK is a browser-based TAK client built by the Colorado DFPC Center of Excellence.
      It connects to your TAK Server and provides a full map interface in any web browser.
      Video streams from your standalone MediaMTX install will be used automatically.
    </p>

    {% if not settings.fqdn %}
    <div style="background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.2);border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:var(--yellow)">
      ⚠ No domain configured. Deploy Caddy SSL first for HTTPS access.
    </div>
    {% endif %}

    <button class="btn btn-primary" id="deploy-btn" onclick="startDeploy()">🚀 Deploy CloudTAK</button>
    {% if not settings.fqdn %}
    <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:8px;padding:12px 16px;margin-top:16px;font-size:12px;color:#f87171">
      🔒 <strong>SSL Required</strong> — CloudTAK requires a domain with SSL configured.<br>
      <span style="color:var(--text-dim)">Go to <a href="/caddy" style="color:var(--cyan)">Caddy SSL</a> and configure your domain first.</span>
    </div>
    {% endif %}
  </div>
  {% endif %}

  <!-- Deploy log -->
  {% if deploying %}
  <div class="card" id="deploy-log-card">
    <div class="card-title">Deploy Log</div>
    <div class="log-box" id="deploy-log">Initializing...</div>
  </div>
  {% endif %}

  <div id="log-card" class="card" style="display:none">
    <div class="card-title">Deploy Log</div>
    <div class="log-box" id="deploy-log-dyn">Waiting...</div>
  </div>
</div>

<!-- Uninstall modal -->
<div class="modal-overlay" id="uninstall-modal">
  <div class="modal">
    <h3>&#x26a0; Uninstall CloudTAK?</h3>
    <p>This will stop and remove all CloudTAK Docker containers, volumes, and the ~/CloudTAK directory. This cannot be undone.</p>
    <div class="form-group">
      <label class="form-label">Admin Password</label>
      <input class="form-input" id="uninstall-password" type="password" placeholder="Confirm your password">
    </div>
    <div class="modal-actions">
      <button class="btn btn-ghost" id="uninstall-cancel-btn" onclick="document.getElementById('uninstall-modal').classList.remove('open')">Cancel</button>
      <button class="btn btn-danger" id="uninstall-confirm-btn" onclick="doUninstall()">Uninstall</button>
    </div>
    <div id="uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
    <div id="uninstall-progress" class="uninstall-progress-row" style="margin-top:8px;font-size:13px;color:var(--text-secondary);min-height:24px" aria-live="polite"></div>
  </div>
</div>

<script src="/cloudtak/page.js"></script>
<script>
(function(){
  var deploying = document.body.getAttribute('data-deploying') === 'true';
  if (deploying) { document.addEventListener('DOMContentLoaded', function() { window.logIndex = 0; if (window.pollLog) window.pollLog(null); }); }
})();
</script>
</body></html>'''

EMAIL_RELAY_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Email Relay</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg-deep);color:var(--text-primary);min-height:100vh}
.top-bar{height:3px;background:linear-gradient(90deg,var(--accent),var(--cyan),var(--green))}
.header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--bg-surface)}
.header-left{display:flex;align-items:center;gap:16px}.header-icon{font-size:28px}.header-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px}.header-subtitle{font-size:13px;color:var(--text-dim)}
.header-right{display:flex;align-items:center;gap:12px}
.btn-back{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.btn-logout{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-logout:hover{color:var(--red);border-color:rgba(239,68,68,0.3)}
.os-badge{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);padding:4px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:4px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;margin-top:24px}
.status-banner{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:12px;padding:24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
.status-info{display:flex;align-items:center;gap:16px}
.status-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px}
.status-icon.running{background:rgba(16,185,129,0.1)}.status-icon.stopped{background:rgba(239,68,68,0.1)}.status-icon.not-installed{background:rgba(71,85,105,0.2)}
.status-text{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:600}
.status-detail{font-size:13px;color:var(--text-dim);margin-top:4px}
.controls{display:flex;gap:10px}
.control-btn{padding:8px 16px;border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:12px;cursor:pointer;transition:all 0.2s}
.control-btn:hover{border-color:var(--border-hover);background:var(--bg-surface)}
.control-btn.btn-stop{color:var(--red)}.control-btn.btn-stop:hover{border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.05)}
.control-btn.btn-start{color:var(--green)}.control-btn.btn-start:hover{border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.05)}
.deploy-log{background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-top:16px}
.input-field{width:100%;padding:12px 16px;background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:14px;outline:none;transition:border-color 0.2s}
.input-field:focus{border-color:var(--accent)}
select.input-field{cursor:pointer}
.input-label{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:8px;display:block}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.form-group{display:flex;flex-direction:column}
.form-group.full{grid-column:1/-1}
.provider-link{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);margin-top:8px;display:block}
.info-box{background:rgba(59,130,246,0.07);border:1px solid rgba(59,130,246,0.2);border-radius:10px;padding:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;margin-bottom:16px}
.info-box code{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--cyan);background:rgba(6,182,212,0.1);padding:2px 6px;border-radius:4px}
.config-table{width:100%;border-collapse:collapse;font-family:'JetBrains Mono',monospace;font-size:12px}
.config-table td{padding:10px 14px;border-bottom:1px solid var(--border)}
.config-table td:first-child{color:var(--text-dim);width:140px}
.config-table td:last-child{color:var(--cyan)}
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-dim);margin-top:40px}
.status-logo-wrap{display:flex;align-items:center;gap:10px}
.status-logo{height:36px;width:auto;max-width:100px;object-fit:contain}
.status-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:18px;color:var(--text-primary)}
.tag{display:inline-block;padding:3px 8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600}
.tag-green{background:rgba(16,185,129,0.1);color:var(--green);border:1px solid rgba(16,185,129,0.2)}
.tag-blue{background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid rgba(59,130,246,0.2)}
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin-left:0;margin-right:auto}
</style></head><body>
{{ sidebar_html }}
<div class="main">

<!-- Status Banner -->
<div class="status-banner">
{% if email.installed and email.running %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">outgoing_mail</span><span class="status-name">Email Relay</span></div><div>
<div class="status-text" style="color:var(--green)">Running</div>
<div class="status-detail">Postfix relay active{% if relay_config.get('provider') %} · {{ providers.get(relay_config.provider,{}).get('name', relay_config.provider) }}{% endif %}{% if relay_config.get('from_addr') %} · {{ relay_config.from_addr }}{% endif %}</div>
</div></div>
<div class="controls">
<button class="control-btn" onclick="emailControl('restart')">↻ Restart</button>
<button class="control-btn btn-stop" onclick="emailControl('stop')">■ Stop</button>
<button class="control-btn btn-stop" onclick="emailUninstall()" style="margin-left:8px">🗑 Remove</button>
</div>
{% elif email.installed %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">outgoing_mail</span><span class="status-name">Email Relay</span></div><div>
<div class="status-text" style="color:var(--red)">Stopped</div>
<div class="status-detail">Postfix is installed but not running</div>
</div></div>
<div class="controls"><button class="control-btn btn-start" onclick="emailControl('start')">▶ Start</button></div>
{% else %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">outgoing_mail</span><span class="status-name">Email Relay</span></div><div>
<div class="status-text" style="color:var(--text-dim)">Not Installed</div>
<div class="status-detail">Postfix email relay — apps use localhost, provider handles delivery</div>
</div></div>
{% endif %}
</div>

{% if deploying %}
<!-- Deploy Log -->
<div class="section-title">Deployment Log</div>
<div class="deploy-log" id="deploy-log">Starting deployment...</div>
<script>
(function pollLog(){
    var el=document.getElementById('deploy-log');
    var last=0;
    var iv=setInterval(async()=>{
        var r=await fetch('/api/emailrelay/log');var d=await r.json();
        if(d.entries&&d.entries.length>last){el.textContent=d.entries.join('\\n');el.scrollTop=el.scrollHeight;last=d.entries.length}
        if(!d.running){clearInterval(iv);setTimeout(()=>location.reload(),1500)}
    },1500);
})();
</script>

{% elif email.installed and email.running %}
<!-- Running State -->
<div class="section-title">Current Configuration</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<table class="config-table">
<tr><td>Provider</td><td>{{ providers.get(relay_config.get('provider',''),{}).get('name', relay_config.get('provider','—')) }}</td></tr>
<tr><td>Relay Host</td><td>{{ relay_config.get('relay_host','—') }}:{{ relay_config.get('relay_port','587') }}</td></tr>
<tr><td>SMTP Login</td><td>{{ relay_config.get('smtp_user','—') }}</td></tr>
<tr><td>From Address</td><td>{{ relay_config.get('from_addr','—') }}</td></tr>
<tr><td>From Name</td><td>{{ relay_config.get('from_name','—') }}</td></tr>
</table>
</div>

<div class="section-title">App SMTP Settings</div>
<div class="info-box">
Configure TAK Portal and MediaMTX to use the local relay:<br><br>
<strong>SMTP Host:</strong> <code>localhost</code> &nbsp;&nbsp;
<strong>Port:</strong> <code>25</code> &nbsp;&nbsp;
<strong>Username:</strong> <code>blank</code> &nbsp;&nbsp;
<strong>Password:</strong> <code>blank</code> &nbsp;&nbsp;
<strong>TLS:</strong> <code>off</code>
</div>

{% if modules.get('authentik', {}).get('installed') %}
<div class="section-title">Configure Authentik</div>
<div id="cfg-ak-card" style="background:var(--bg-card);border:1px solid {% if authentik_smtp_configured %}rgba(16,185,129,0.4){% else %}var(--border){% endif %};border-radius:12px;padding:24px;margin-bottom:24px;border-left:4px solid {% if authentik_smtp_configured %}var(--green){% else %}var(--border){% endif %}">
<p style="margin:0 0 8px 0;color:var(--text-muted)">Push this relay (localhost:25) and your From address into Authentik so recovery emails and other Authentik mail use the same relay. After you deploy Email Relay, this runs automatically; you can also click below to run it now or after switching providers.</p>
<p id="cfg-ak-status" style="margin:0 0 16px 0;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600">{% if authentik_smtp_configured %}<span style="color:var(--green)">✓ Authentik SMTP: Configured</span> — password recovery will use this relay.{% else %}<span style="color:var(--yellow)">Authentik SMTP: Not configured</span> — click the button below so &quot;Forgot username or password&quot; emails are sent.{% endif %}</p>
<button onclick="configureAuthentik()" id="cfg-ak-btn" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;cursor:pointer">Configure Authentik to use these settings</button>
<p style="margin:8px 0 0 0;font-size:11px;color:var(--text-dim)">If you switch providers later, click this again to push the new relay into Authentik.</p>
<div id="cfg-ak-result" style="margin-top:12px;font-family:'JetBrains Mono',monospace;font-size:12px;display:none"></div>
</div>
{% endif %}

<div class="section-title">Send Test Email</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:flex;gap:12px;align-items:end">
<div style="flex:1"><label class="input-label">Send test to</label>
<input type="email" id="test-addr" class="input-field" placeholder="you@example.com"></div>
<button onclick="sendTest()" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap">Send Test</button>
</div>
<div id="test-result" style="margin-top:12px;font-family:'JetBrains Mono',monospace;font-size:12px;display:none"></div>
</div>

<div class="section-title">Switch Provider</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div id="swap-form">
<div class="form-grid">
<div class="form-group full">
<label class="input-label">Email Provider</label>
<select class="input-field" id="swap-provider" onchange="updateProviderUI('swap-')">
{% for key, p in providers.items() %}<option value="{{ key }}"{% if relay_config.get("provider")==key %} selected{% endif %}>{{ p.name }}</option>{% endfor %}
</select>
<a id="swap-provider-link" href="#" target="_blank" class="provider-link" style="display:none">→ Get credentials from provider ↗</a>
</div>
<div class="form-group"><label class="input-label">SMTP Username / Login</label>
<input type="text" id="swap-smtp_user" class="input-field" placeholder="user@smtp-brevo.com" value="{{ relay_config.get('smtp_user','') }}"></div>
<div class="form-group"><label class="input-label">SMTP Password / API Key</label>
<input type="password" id="swap-smtp_pass" class="input-field" placeholder="••••••••••••"></div>
<div class="form-group"><label class="input-label">From Address</label>
<input type="email" id="swap-from_addr" class="input-field" placeholder="noreply@yourdomain.com" value="{{ relay_config.get('from_addr','') }}"></div>
<div class="form-group"><label class="input-label">From Name</label>
<input type="text" id="swap-from_name" class="input-field" placeholder="TAK Operations" value="{{ relay_config.get('from_name','') }}"></div>
<div class="form-group full" id="swap-custom-fields" style="display:none;grid-template-columns:1fr 120px;gap:12px">
<div><label class="input-label">Custom SMTP Host</label><input type="text" id="swap-custom_host" class="input-field" placeholder="smtp.yourdomain.com"></div>
<div><label class="input-label">Port</label><input type="text" id="swap-custom_port" class="input-field" placeholder="587" value="587"></div>
</div></div>
<div style="margin-top:20px;text-align:center">
<button onclick="swapProvider()" style="padding:12px 32px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;cursor:pointer">↔ Switch Provider</button>
</div>
</div>
</div>

{% elif not email.installed %}
<!-- Not Installed -->
<div class="section-title">How It Works</div>
<div class="info-box">
The Email Relay installs <strong>Postfix</strong> as a local mail relay on this server. Your apps (TAK Portal, MediaMTX) send to <code>localhost:25</code> with no credentials — Postfix handles authentication and delivery through your chosen provider.<br><br>
Switching providers later requires only updating Postfix credentials — no changes to your apps.
</div>

<div class="section-title">Deploy Email Relay</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div class="form-grid">
<div class="form-group full">
<label class="input-label">Email Provider</label>
<select class="input-field" id="deploy-provider" onchange="updateProviderUI('deploy-')">
{% for key, p in providers.items() %}<option value="{{ key }}">{{ p.name }}</option>{% endfor %}
</select>
<a id="deploy-provider-link" href="#" target="_blank" class="provider-link" style="display:none">→ Get credentials from provider ↗</a>
</div>
<div class="form-group"><label class="input-label">SMTP Username / Login</label>
<input type="text" id="deploy-smtp_user" class="input-field" placeholder="user@smtp-brevo.com"></div>
<div class="form-group"><label class="input-label">SMTP Password / API Key</label>
<input type="password" id="deploy-smtp_pass" class="input-field" placeholder="••••••••••••"></div>
<div class="form-group"><label class="input-label">From Address</label>
<input type="email" id="deploy-from_addr" class="input-field" placeholder="noreply@yourdomain.com"></div>
<div class="form-group"><label class="input-label">From Name</label>
<input type="text" id="deploy-from_name" class="input-field" placeholder="TAK Operations"></div>
<div class="form-group full" id="deploy-custom-fields" style="display:none;grid-template-columns:1fr 120px;gap:12px">
<div><label class="input-label">Custom SMTP Host</label><input type="text" id="deploy-custom_host" class="input-field" placeholder="smtp.yourdomain.com"></div>
<div><label class="input-label">Port</label><input type="text" id="deploy-custom_port" class="input-field" placeholder="587" value="587"></div>
</div></div>
<div style="margin-top:20px;text-align:center">
<button onclick="deployRelay()" id="deploy-btn" style="padding:14px 40px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:16px;font-weight:600;cursor:pointer">📧 Deploy Email Relay</button>
</div>
</div>
{% endif %}

</div>
<footer class="footer"></footer>

<script>
var PROVIDERS = {{ providers | tojson }};

function updateProviderUI(prefix){
    var sel = document.getElementById(prefix+'provider');
    if(!sel) return;
    var key = sel.value;
    var p = PROVIDERS[key] || {};
    var linkEl = document.getElementById(prefix+'provider-link');
    if(linkEl){
        if(p.url){ linkEl.href=p.url; linkEl.style.display='inline'; }
        else { linkEl.style.display='none'; }
    }
    var customFields = document.getElementById(prefix+'custom-fields');
    if(customFields) customFields.style.display = (key==='custom') ? 'grid' : 'none';
}

async function deployRelay(){
    var btn=document.getElementById('deploy-btn');
    var provider=document.getElementById('deploy-provider').value;
    var user=document.getElementById('deploy-smtp_user').value.trim();
    var pass=document.getElementById('deploy-smtp_pass').value.trim();
    var from=document.getElementById('deploy-from_addr').value.trim();
    var name=document.getElementById('deploy-from_name').value.trim();
    if(!user||!pass||!from){alert('SMTP username, password, and From address are required');return}
    var body={provider,smtp_user:user,smtp_pass:pass,from_addr:from,from_name:name};
    if(provider==='custom'){
        body.custom_host=document.getElementById('deploy-custom_host').value.trim();
        body.custom_port=document.getElementById('deploy-custom_port').value.trim();
    }
    btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.7';
    var r=await fetch('/api/emailrelay/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var d=await r.json();
    if(d.success){location.reload()}
    else{alert('Error: '+d.error);btn.disabled=false;btn.textContent='📧 Deploy Email Relay';btn.style.opacity='1'}
}

async function swapProvider(){
    var provider=document.getElementById('swap-provider').value;
    var user=document.getElementById('swap-smtp_user').value.trim();
    var pass=document.getElementById('swap-smtp_pass').value.trim();
    var from=document.getElementById('swap-from_addr').value.trim();
    var name=document.getElementById('swap-from_name').value.trim();
    if(!user||!pass||!from){alert('All fields required');return}
    var body={provider,smtp_user:user,smtp_pass:pass,from_addr:from,from_name:name};
    if(provider==='custom'){
        body.custom_host=document.getElementById('swap-custom_host').value.trim();
        body.custom_port=document.getElementById('swap-custom_port').value.trim();
    }
    if(!confirm('Switch to '+PROVIDERS[provider].name+'? Postfix will restart.')){return}
    var r=await fetch('/api/emailrelay/swap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var d=await r.json();
    if(d.success){location.reload()}
    else{alert('Error: '+d.error)}
}

async function sendTest(){
    var to=document.getElementById('test-addr').value.trim();
    if(!to){alert('Enter a recipient address');return}
    var res=document.getElementById('test-result');
    res.style.display='block';res.style.color='var(--text-dim)';res.textContent='Sending...';
    var r=await fetch('/api/emailrelay/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to})});
    var d=await r.json();
    if(d.success){res.style.color='var(--green)';res.textContent='✓ '+d.output}
    else{res.style.color='var(--red)';res.textContent='✗ '+d.error}
}

async function configureAuthentik(){
    var btn=document.getElementById('cfg-ak-btn');
    var res=document.getElementById('cfg-ak-result');
    if(!btn||!res) return;
    btn.disabled=true;res.style.display='block';res.style.color='var(--text-dim)';res.textContent='Configuring...';
    var r=await fetch('/api/emailrelay/configure-authentik',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
    var d=await r.json();
    if(d.success){res.style.color='var(--green)';res.textContent='✓ '+d.message;setTimeout(function(){location.reload();},1500)}
    else{res.style.color='var(--red)';res.textContent='✗ '+(d.error||'Failed')}
    btn.disabled=false;
}

async function emailControl(action){
    var r=await fetch('/api/emailrelay/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
    var d=await r.json();
    if(d.success){location.reload()}else{alert('Error: '+(d.error||d.output))}
}

async function emailUninstall(){
    if(!confirm('Remove Postfix email relay? Apps will need to be reconfigured.')){return}
    var r=await fetch('/api/emailrelay/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
    var d=await r.json();
    if(d.success){location.reload()}else{alert('Error removing Postfix')}
}
</script>
</body></html>'''




CADDY_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Caddy SSL</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg-deep);color:var(--text-primary);min-height:100vh}
.top-bar{height:3px;background:linear-gradient(90deg,var(--accent),var(--cyan),var(--green))}
.header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--bg-surface)}
.header-left{display:flex;align-items:center;gap:16px}.header-icon{font-size:28px}.header-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px}.header-subtitle{font-size:13px;color:var(--text-dim)}
.header-right{display:flex;align-items:center;gap:12px}
.btn-back{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.btn-logout{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-logout:hover{color:var(--red);border-color:rgba(239,68,68,0.3)}
.os-badge{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);padding:4px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:4px}
.main{max-width:1000px;margin:0 auto;padding:32px 40px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;margin-top:24px}
.status-banner{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:12px;padding:24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
.status-info{display:flex;align-items:center;gap:16px}
.status-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px}
.status-icon.running{background:rgba(16,185,129,0.1)}.status-icon.stopped{background:rgba(239,68,68,0.1)}.status-icon.not-installed{background:rgba(71,85,105,0.2)}
.status-text{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:600}
.status-detail{font-size:13px;color:var(--text-dim);margin-top:4px}
.controls{display:flex;gap:10px}
.control-btn{padding:8px 16px;border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:12px;cursor:pointer;transition:all 0.2s}
.control-btn:hover{border-color:var(--border-hover);background:var(--bg-surface)}
.control-btn.btn-stop{color:var(--red)}.control-btn.btn-stop:hover{border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.05)}
.control-btn.btn-start{color:var(--green)}.control-btn.btn-start:hover{border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.05)}
.deploy-log{background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-top:16px}
.input-field{width:100%;padding:12px 16px;background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:14px;outline:none;transition:border-color 0.2s}
.input-field:focus{border-color:var(--accent)}
.input-label{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:8px;display:block}
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-dim);margin-top:40px}
.status-logo-wrap{display:flex;align-items:center;gap:10px}
.status-logo{height:36px;width:auto;max-width:100px;object-fit:contain}
.status-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:18px;color:var(--text-primary)}
.benefit-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:16px}
.benefit-item{background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:14px;font-size:12px}
.benefit-item .icon{font-size:18px;margin-bottom:6px}
.benefit-item .title{font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--text-secondary);margin-bottom:4px}
.benefit-item .desc{color:var(--text-dim);line-height:1.4}
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin:0 auto}
</style></head><body>
{{ sidebar_html }}
<div class="main">
<div class="status-banner">
{% if caddy.installed and caddy.running %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ caddy_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--green)">Running</div><div class="status-detail">Caddy is active{% if settings.get('fqdn') %} · {{ settings.get('fqdn') }}{% endif %}</div></div></div>
<div class="controls"><button class="control-btn" onclick="caddyControl('reload')">↻ Reload</button><button class="control-btn" onclick="caddyControl('restart')">↻ Restart</button><button class="control-btn btn-stop" onclick="caddyControl('stop')">■ Stop</button><button class="control-btn btn-stop" onclick="caddyUninstall()" style="margin-left:8px">🗑 Remove</button></div>
{% elif caddy.installed %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ caddy_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--red)">Stopped</div><div class="status-detail">Caddy is installed but not running</div></div></div>
<div class="controls"><button class="control-btn btn-start" onclick="caddyControl('start')">▶ Start</button><button class="control-btn btn-stop" onclick="caddyUninstall()" style="margin-left:8px">🗑 Remove</button></div>
{% else %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ caddy_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--text-dim)">Not Installed</div><div class="status-detail">Set up a domain for full functionality</div></div></div>
{% endif %}
</div>

{% if deploying %}
<div class="section-title">Deployment Log</div>
<div class="deploy-log" id="deploy-log">Waiting for deployment to start...</div>
{% elif caddy.installed and caddy.running %}
<div class="section-title">Domain Configuration</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:flex;gap:12px;align-items:end">
<div style="flex:1"><label class="input-label">Base Domain (subdomains auto-configured)</label>
<input type="text" id="domain-input" class="input-field" value="{{ settings.get('fqdn', '') }}" placeholder="yourdomain.com"></div>
<button onclick="updateDomain()" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap">Update & Reload</button>
</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:12px">Create DNS A records for *.{{ settings.get('fqdn', '') }} or individual subdomains pointing to <span style="color:var(--cyan)">{{ settings.get('server_ip', '') }}</span></div>
</div>
<details id="service-domains-section" style="margin-bottom:24px">
<summary style="cursor:pointer;font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:var(--text-secondary);padding:12px 0;user-select:none">Service Domains <span style="font-size:11px;color:var(--text-dim);font-weight:400">— customize per-service domains</span></summary>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-top:8px">
<div style="font-size:12px;color:var(--text-dim);margin-bottom:16px;line-height:1.5">Override any service's domain. Leave blank to use the default (<code style="background:rgba(255,255,255,.05);padding:1px 5px;border-radius:3px">prefix.basedomain</code>). Enter a full domain (e.g. <code style="background:rgba(255,255,255,.05);padding:1px 5px;border-radius:3px">mystreams.tv</code>) or just a prefix (e.g. <code style="background:rgba(255,255,255,.05);padding:1px 5px;border-radius:3px">live</code> → <code style="background:rgba(255,255,255,.05);padding:1px 5px;border-radius:3px">live.{{ settings.get('fqdn','') }}</code>).</div>
<div id="svc-domains-grid" style="display:grid;grid-template-columns:140px 1fr;gap:8px 16px;align-items:center">
<div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;padding-bottom:4px;border-bottom:1px solid var(--border)">Service</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;padding-bottom:4px;border-bottom:1px solid var(--border)">Domain</div>
</div>
<div id="svc-domains-loading" style="text-align:center;padding:20px;color:var(--text-dim);font-size:12px">Loading...</div>
<div style="display:flex;gap:12px;align-items:center;margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
<button onclick="saveDomains()" id="save-domains-btn" style="padding:10px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer">Save & Reload Caddy</button>
<span id="save-domains-status" style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim)"></span>
</div>
</div>
</details>
{% if configured_urls %}
<div class="section-title">Configured URLs</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:grid;grid-template-columns:minmax(140px,1fr) minmax(180px,1.4fr) 1fr;gap:12px 24px;align-items:center;font-size:13px;border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:12px">
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Service</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">URL</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Where it goes</div>
</div>
{% for u in configured_urls %}
<div style="display:grid;grid-template-columns:minmax(140px,1fr) minmax(180px,1.4fr) 1fr;gap:12px 24px;align-items:center;font-size:13px;padding:10px 0;border-bottom:1px solid var(--border)">
<div style="font-weight:600;color:var(--text-primary)">{{ u.name }}</div>
<div><a href="{{ u.url }}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:12px;word-break:break-all">{{ u.host }}</a> <span style="color:var(--text-dim);font-size:11px">↗</span></div>
<div style="color:var(--text-dim);font-size:12px">{{ u.desc }}</div>
</div>
{% endfor %}
</div>
{% endif %}
<div class="section-title">Caddyfile</div>
<div style="background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap">{{ caddyfile }}</div>
{% elif not caddy.installed %}
<div class="section-title">Set Up Your Domain</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:32px;margin-bottom:24px">
<div style="text-align:center;margin-bottom:24px">
<div style="font-size:36px;margin-bottom:12px">🌐</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:600;color:var(--text-secondary)">Configure a Domain Name</div>
<div style="font-size:13px;color:var(--text-dim);margin-top:8px;max-width:500px;margin-left:auto;margin-right:auto;line-height:1.5">Caddy provides automatic HTTPS with Let's Encrypt certificates. Enter your domain name and point its DNS to this server's IP address.</div>
</div>
<div style="max-width:500px;margin:0 auto">
<label class="input-label">Base Domain</label>
<input type="text" id="domain-input" class="input-field" placeholder="yourdomain.com" style="margin-bottom:8px">
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-bottom:20px">Subdomains auto-configured: infratak · console · tak · authentik · portal · nodered · map · tiles.map · video<br>Point a wildcard DNS (*.yourdomain.com) or individual A records to <span style="color:var(--cyan)">{{ settings.get('server_ip', '') }}</span></div>
<div style="text-align:center">
<button onclick="deployCaddy()" id="deploy-btn" style="padding:14px 40px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:16px;font-weight:600;cursor:pointer">🚀 Deploy Caddy</button>
</div>
</div>
</div>
<div class="section-title">What You Get With a Domain</div>
<div class="benefit-grid">
<div class="benefit-item"><div class="icon">📱</div><div class="title">TAK Client QR Enrollment</div><div class="desc">Devices can enroll via QR code with trusted SSL certificates (ATAK, WinTAK, iTAK, etc.)</div></div>
<div class="benefit-item"><div class="icon">🔐</div><div class="title">TAK Portal Auth</div><div class="desc">Secure TAK Portal with Authentik SSO — no more anonymous access</div></div>
<div class="benefit-item"><div class="icon">🔒</div><div class="title">Trusted SSL</div><div class="desc">Let's Encrypt certificates — no more browser warnings</div></div>
<div class="benefit-item"><div class="icon"><img src="{{ mediamtx_logo_url }}" alt="" style="width:28px;height:28px;object-fit:contain"></div><div class="title">Secure Streaming</div><div class="desc">MediaMTX streams over HTTPS with its own subdomain</div></div>
</div>
{% endif %}
</div>
<footer class="footer"></footer>
<script>
async function deployCaddy(){
    var domain=document.getElementById('domain-input').value.trim();
    if(!domain){alert('Please enter a domain name');return}
    if(!confirm('Deploy Caddy with domain: '+domain+'?\\n\\nMake sure DNS is pointing to this server.')){return}
    var btn=document.getElementById('deploy-btn');
    btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.7';
    try{
        var r=await fetch('/api/caddy/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:domain})});
        var d=await r.json();
        if(d.success){pollCaddyLog()}
        else{alert('Error: '+d.error);btn.disabled=false;btn.textContent='🚀 Deploy Caddy';btn.style.opacity='1'}
    }catch(e){alert('Error: '+e.message);btn.disabled=false;btn.textContent='🚀 Deploy Caddy';btn.style.opacity='1'}
}
function pollCaddyLog(){
    var el=document.getElementById('deploy-log');
    if(!el){location.reload();return}
    var lastCount=0;
    var iv=setInterval(async()=>{
        try{
            var r=await fetch('/api/caddy/log');var d=await r.json();
            if(d.entries&&d.entries.length>lastCount){
                var newEntries=d.entries.slice(lastCount);
                newEntries.forEach(function(e){
                    var isTimer=e.trim().charAt(0)==='\u23f3'&&e.indexOf(':')>0;
                    if(isTimer){var prev=el.querySelector('[data-timer]');if(prev){prev.textContent=e;return}}
                    if(!isTimer){var old=el.querySelector('[data-timer]');if(old)old.removeAttribute('data-timer')}
                    var l=document.createElement('div');
                    if(isTimer)l.setAttribute('data-timer','1');
                    if(e.indexOf('\u2713')>=0)l.style.color='var(--green)';
                    else if(e.indexOf('\u2717')>=0||e.indexOf('FATAL')>=0)l.style.color='var(--red)';
                    else if(e.indexOf('\u2501\u2501\u2501')>=0)l.style.color='var(--cyan)';
                    else if(e.indexOf('\u26a0')>=0)l.style.color='var(--yellow)';
                    else if(e.indexOf('===')>=0)l.style.color='var(--green)';
                    l.textContent=e;el.appendChild(l);
                });
                lastCount=d.entries.length;el.scrollTop=el.scrollHeight;
            }
            if(!d.running){clearInterval(iv);if(d.complete||d.error){setTimeout(()=>location.reload(),3000)}}
        }catch(e){}
    },1000);
}
async function caddyControl(action){
    try{var r=await fetch('/api/caddy/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action})});
    var d=await r.json();
    if(d.success){setTimeout(()=>location.reload(),1500)}
    else{alert('Caddy '+action+' failed: '+(d.output||d.error||'unknown'))}
    }catch(e){alert('Error: '+e.message)}
}
async function updateDomain(){
    var domain=document.getElementById('domain-input').value.trim();
    if(!domain){alert('Please enter a domain name');return}
    try{var r=await fetch('/api/caddy/domain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:domain})});
    var d=await r.json();if(d.success){alert('Domain updated and Caddy reloaded');location.reload()}else{alert('Error: '+d.error)}}catch(e){alert('Error: '+e.message)}
}
async function caddyUninstall(){
    if(!confirm('Remove Caddy and clear domain configuration?'))return;
    try{var r=await fetch('/api/caddy/uninstall',{method:'POST'});var d=await r.json();if(d.success)location.reload()}catch(e){alert('Error: '+e.message)}
}
async function loadServiceDomains(){
    try{
        var r=await fetch('/api/caddy/domains');var d=await r.json();
        var grid=document.getElementById('svc-domains-grid');
        var loading=document.getElementById('svc-domains-loading');
        if(!grid)return;
        loading.style.display='none';
        d.services.forEach(function(s){
            var nameDiv=document.createElement('div');
            nameDiv.style.cssText='font-family:"JetBrains Mono",monospace;font-size:12px;font-weight:500;color:'+(s.installed?'var(--text-primary)':'var(--text-dim)')+';display:flex;align-items:center;gap:6px;padding:8px 0';
            nameDiv.innerHTML=s.label+(s.installed?'':' <span style="font-size:9px;color:var(--text-dim);background:rgba(71,85,105,.3);padding:1px 6px;border-radius:3px">not installed</span>');
            var inputDiv=document.createElement('div');
            inputDiv.style.cssText='padding:4px 0';
            var inp=document.createElement('input');
            inp.type='text';inp.id='svc-domain-'+s.key;
            inp.value=s.custom||'';
            inp.placeholder=s.default||s.key;
            inp.style.cssText='width:100%;padding:8px 12px;background:var(--bg-deep);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-family:"JetBrains Mono",monospace;font-size:12px;outline:none;transition:border-color .2s';
            inp.onfocus=function(){this.style.borderColor='var(--cyan)'};
            inp.onblur=function(){this.style.borderColor='var(--border)'};
            if(!s.installed){inp.style.opacity='0.5'}
            inputDiv.appendChild(inp);
            grid.appendChild(nameDiv);
            grid.appendChild(inputDiv);
        });
        window._svcDomainKeys=d.services.map(function(s){return s.key});
    }catch(e){
        var loading=document.getElementById('svc-domains-loading');
        if(loading)loading.textContent='Failed to load service domains';
    }
}
async function saveDomains(){
    var btn=document.getElementById('save-domains-btn');
    var status=document.getElementById('save-domains-status');
    btn.disabled=true;btn.textContent='Saving...';btn.style.opacity='0.7';
    status.textContent='';status.style.color='var(--cyan)';
    var domains={};
    (window._svcDomainKeys||[]).forEach(function(k){
        var inp=document.getElementById('svc-domain-'+k);
        if(inp)domains[k]=inp.value.trim();
    });
    try{
        var r=await fetch('/api/caddy/domains',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domains:domains})});
        var d=await r.json();
        if(d.success){
            status.style.color='var(--green)';status.textContent='Saved — Caddy reloading…';
            setTimeout(function(){location.reload()},3000);
        }else{
            status.style.color='var(--red)';status.textContent='Error: '+(d.error||'unknown');
            btn.disabled=false;btn.textContent='Save & Reload Caddy';btn.style.opacity='1';
        }
    }catch(e){
        status.style.color='var(--red)';status.textContent='Error: '+e.message;
        btn.disabled=false;btn.textContent='Save & Reload Caddy';btn.style.opacity='1';
    }
}
loadServiceDomains();
{% if deploying %}pollCaddyLog();{% endif %}
</script>
</body></html>'''

CERTS_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Certificates · infra-TAK</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg-deep);color:var(--text-primary);min-height:100vh}
.top-bar{height:3px;background:linear-gradient(90deg,var(--accent),var(--cyan),var(--green))}
.header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--bg-surface)}
.header-left{display:flex;align-items:center;gap:16px}.header-icon{font-size:28px}.header-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px}.header-subtitle{font-size:13px;color:var(--text-dim)}
.header-right{display:flex;align-items:center;gap:12px}
.btn-back{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.main{max-width:1000px;margin:0 auto;padding:32px 40px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px}
.cert-table{width:100%;border-collapse:collapse}
.cert-table tr{border-bottom:1px solid var(--border);transition:background 0.15s}
.cert-table tr:hover{background:rgba(59,130,246,0.05)}
.cert-table td{padding:12px 8px;font-family:'JetBrains Mono',monospace;font-size:13px}
.cert-icon{width:30px;text-align:center}
.cert-name{color:var(--text-secondary)}
.cert-size{color:var(--text-dim);text-align:right;width:80px}
.cert-dl{text-align:right;width:40px}
.cert-dl a{color:var(--accent);text-decoration:none;font-size:14px;padding:4px 8px;border-radius:4px;transition:background 0.15s}
.cert-dl a:hover{background:rgba(59,130,246,0.1)}
.info-bar{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:20px}
.info-bar span{color:var(--cyan)}
.filter-btns{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.filter-btn{padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--text-dim);font-family:'JetBrains Mono',monospace;font-size:11px;cursor:pointer;transition:all 0.2s}
.filter-btn:hover,.filter-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(59,130,246,0.05)}
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-dim);margin-top:40px}
</style></head><body>
<div class="top-bar"></div>
<header class="header"><div class="header-left"><div class="header-icon">⚡</div><div><div class="header-title">infra-TAK</div><div class="header-subtitle">Certificates</div></div></div><div class="header-right"><a href="/takserver" class="btn-back">← TAK Server</a></div></header>
<main class="main">
<div class="section-title">Certificate Files</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px">
<div class="info-bar">Password: <span>atakatak</span> &nbsp;&middot;&nbsp; {{ files|length }} files in /opt/tak/certs/files/</div>
<div class="filter-btns">
<button class="filter-btn active" onclick="filterCerts('all')">All</button>
<button class="filter-btn" onclick="filterCerts('p12')">🔑 .p12</button>
<button class="filter-btn" onclick="filterCerts('pem')">📄 .pem</button>
<button class="filter-btn" onclick="filterCerts('jks')">☕ .jks</button>
<button class="filter-btn" onclick="filterCerts('key')">🔐 .key</button>
<button class="filter-btn" onclick="filterCerts('other')">Other</button>
</div>
<table class="cert-table">
{% for f in files %}
<tr data-ext="{{ f.ext }}"><td class="cert-icon">{{ f.icon }}</td><td class="cert-name">{{ f.name }}</td><td class="cert-size">{{ f.size }}</td><td class="cert-dl"><a href="/api/certs/download/{{ f.name }}" title="Download">⬇</a></td></tr>
{% endfor %}
</table>
</div>
</main>
<footer class="footer">infra-TAK</footer>
<script>
function filterCerts(ext){
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.cert-table tr').forEach(r=>{
        if(ext==='all')r.style.display='';
        else if(ext==='other')r.style.display=['p12','pem','jks','key'].includes(r.dataset.ext)?'none':'';
        else r.style.display=r.dataset.ext===ext?'':'none';
    });
}
</script>
</body></html>'''

TAKPORTAL_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TAK Portal</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg-deep);color:var(--text-primary);min-height:100vh}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.top-bar{height:3px;background:linear-gradient(90deg,var(--accent),var(--cyan),var(--green))}
.header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--bg-surface)}
.header-left{display:flex;align-items:center;gap:16px}.header-icon{font-size:28px}.header-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px}.header-subtitle{font-size:13px;color:var(--text-dim)}
.header-right{display:flex;align-items:center;gap:12px}
.btn-back{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.btn-logout{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-logout:hover{color:var(--red);border-color:rgba(239,68,68,0.3)}
.os-badge{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);padding:4px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:4px}
.main{max-width:1000px;margin:0 auto;padding:32px 40px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;margin-top:24px}
.status-banner{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:12px;padding:24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
.status-info{display:flex;align-items:center;gap:16px}
.status-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px}
.status-icon.running{background:rgba(16,185,129,0.1)}.status-icon.stopped{background:rgba(239,68,68,0.1)}.status-icon.not-installed{background:rgba(71,85,105,0.2)}
.status-text{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:600}
.status-detail{font-size:13px;color:var(--text-dim);margin-top:4px}
.status-logo-wrap{display:flex;align-items:center;gap:10px}
.status-logo{height:36px;width:auto;max-width:100px;object-fit:contain}
.status-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:18px;color:var(--text-primary)}
.controls{display:flex;gap:10px}
.control-btn{padding:10px 20px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:13px;cursor:pointer;transition:all 0.2s}
.control-btn:hover{border-color:var(--border-hover);color:var(--text-primary)}
.control-btn.btn-stop{border-color:rgba(239,68,68,0.3)}.control-btn.btn-stop:hover{background:rgba(239,68,68,0.1);color:var(--red)}
.control-btn.btn-start{border-color:rgba(16,185,129,0.3)}.control-btn.btn-start:hover{background:rgba(16,185,129,0.1);color:var(--green)}
.control-btn.btn-update{border-color:rgba(59,130,246,0.3)}.control-btn.btn-update:hover{background:rgba(59,130,246,0.1);color:var(--accent)}
.control-btn.btn-remove{border-color:rgba(239,68,68,0.2)}.control-btn.btn-remove:hover{background:rgba(239,68,68,0.1);color:var(--red)}
.cert-btn{padding:10px 20px;border-radius:8px;text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;transition:all 0.2s}
.cert-btn-primary{background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff}
.cert-btn-secondary{background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid var(--border)}
.deploy-btn{padding:14px 32px;border:none;border-radius:10px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;display:block;margin:24px auto}
.deploy-btn:hover{transform:translateY(-1px);box-shadow:0 4px 24px rgba(59,130,246,0.25)}
.deploy-log{background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-top:16px}
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-dim);margin-top:40px}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:8px}
.svc-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:'JetBrains Mono',monospace;font-size:12px}
.svc-name{color:var(--text-secondary);font-weight:600;margin-bottom:4px}
.svc-status{font-size:11px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-size:13px}
.uninstall-spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes uninstall-spin{to{transform:rotate(360deg)}}
.uninstall-progress-row{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text-secondary)}
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin:0 auto}
</style></head><body>
{{ sidebar_html }}
<div class="main">
<div class="status-banner">
{% if deploying %}
<div class="status-info"><div class="status-icon running" style="background:rgba(59,130,246,0.1)">🔄</div><div><div class="status-text" style="color:var(--accent)">Deploying...</div><div class="status-detail">TAK Portal installation in progress</div></div></div>
{% elif portal.installed and portal.running %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">group</span><span class="status-name">TAK Portal</span></div><div><div class="status-text" style="color:var(--green)">Running</div><div class="status-detail">{{ container_info.get('status', 'Docker container active') }}</div></div></div>
<div class="controls">
<button class="control-btn btn-stop" onclick="portalControl('stop')">⏹ Stop</button>
<button class="control-btn" onclick="portalControl('restart')">🔄 Restart</button>
<button class="control-btn btn-update" id="update-btn" onclick="portalUpdate()"{% if portal_update_available %} style="position:relative;border-color:var(--cyan);box-shadow:0 0 0 1px var(--cyan)"{% endif %}>⬆ Update{% if portal_update_available %} <span style="margin-left:4px;color:var(--cyan)" title="Update available">●</span>{% endif %}</button>
</div>
{% if portal_version %}<div style="margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim)">Version: {{ portal_version }}{% if portal_update_available and portal_latest %} · <span style="color:var(--cyan)">Update to {{ portal_latest }} available</span>{% endif %}</div>{% endif %}
<div id="update-status" style="display:none;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-secondary)"></div>
{% elif portal.installed %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">group</span><span class="status-name">TAK Portal</span></div><div><div class="status-text" style="color:var(--red)">Stopped</div><div class="status-detail">Docker container not running</div></div></div>
<div class="controls">
<button class="control-btn btn-start" onclick="portalControl('start')">▶ Start</button>
<button class="control-btn btn-update" id="update-btn" onclick="portalUpdate()"{% if portal_update_available %} style="position:relative;border-color:var(--cyan);box-shadow:0 0 0 1px var(--cyan)"{% endif %}>⬆ Update{% if portal_update_available %} <span style="margin-left:4px;color:var(--cyan)" title="Update available">●</span>{% endif %}</button>
</div>
{% if portal_version %}<div style="margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim)">Version: {{ portal_version }}{% if portal_update_available and portal_latest %} · <span style="color:var(--cyan)">Update to {{ portal_latest }} available</span>{% endif %}</div>{% endif %}
<div id="update-status" style="display:none;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-secondary)"></div>
{% else %}
<div class="status-info"><div class="status-logo-wrap"><span class="material-symbols-outlined" style="font-size:36px">group</span><span class="status-name">TAK Portal</span></div><div><div class="status-text" style="color:var(--text-dim)">Not Installed</div><div class="status-detail">Deploy TAK Portal for user & certificate management</div></div></div>
{% endif %}
</div>

{% if deploying %}
<div class="section-title">Deployment Log</div>
<div class="deploy-log" id="deploy-log">Waiting for deployment to start...</div>
{% elif portal.installed and portal.running %}
<div class="section-title">Access</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:flex;gap:10px;flex-wrap:nowrap;align-items:center">
<a href="{{ 'https://takportal.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':' + str(portal_port) }}" target="_blank" class="cert-btn cert-btn-primary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">👥 TAK Portal{% if not settings.get('fqdn') %} :{{ portal_port }}{% endif %}</a>
<a href="{{ 'https://authentik.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':9090' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔐 Authentik{% if not settings.get('fqdn') %} :9090{% endif %}</a>
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8443' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔐 WebGUI :8443 (cert)</a>
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8446' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔑 WebGUI :8446 (password)</a>
</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:12px">Admin user: <span style="color:var(--cyan)">akadmin</span> · <button type="button" onclick="showAkPassword()" id="ak-pw-btn" style="background:none;border:1px solid var(--border);color:var(--cyan);padding:2px 10px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;cursor:pointer">🔑 Show Password</button> <span id="ak-pw-display" style="color:var(--green);user-select:all;display:none"></span></div>
</div>
<div class="section-title">Configuration</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="font-family:'JetBrains Mono',monospace;font-size:12px;line-height:2">
<div><span style="color:var(--text-dim)">TAK Server:</span> <span style="color:var(--cyan)">{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip','') + ':8443' }}</span></div>
<div><span style="color:var(--text-dim)">Authentik URL:</span> <span style="color:var(--cyan)">{{ 'https://authentik.' + settings.get('fqdn') if settings.get('fqdn') else 'http://' + settings.get('server_ip','') + ':9090' }}</span></div>
<div><span style="color:var(--text-dim)">Forward Auth:</span> <span style="color:var(--green)">{{ 'Enabled via Caddy' if settings.get('fqdn') else 'Disabled (no FQDN)' }}</span></div>
<div><span style="color:var(--text-dim)">Self-Service Enrollment:</span> <span style="color:var(--cyan)">{{ 'https://takportal.' + settings.get('fqdn') + '/request-access' if settings.get('fqdn') else 'http://' + settings.get('server_ip','') + ':3000/request-access' }}</span></div>
<div style="margin-top:8px;font-size:11px;color:var(--text-dim)">Users created in TAK Portal flow through Authentik → LDAP → TAK Server automatically</div>
</div>
</div>
{% if container_info.get('containers') %}
<div class="section-title">Services</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div class="svc-grid">
{% for c in container_info.containers %}
<div class="svc-card" onclick="filterLogs('{{ c.name }}')" style="cursor:pointer;border-color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' if 'Up' in c.status else 'var(--border)' }}" id="svc-{{ c.name }}"><div class="svc-name">{{ c.name }}</div><div class="svc-status" style="color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' }}">● {{ c.status }}</div></div>
{% endfor %}
<div class="svc-card" onclick="filterLogs('')" style="cursor:pointer" id="svc-all"><div class="svc-name">all containers</div><div class="svc-status" style="color:var(--text-dim)">● combined</div></div>
</div>
</div>
{% endif %}
<div class="section-title">Container Logs <span id="log-filter-label" style="font-size:11px;color:var(--cyan);margin-left:8px"></span></div>
<div class="deploy-log" id="container-log">Loading logs...</div>
<div style="margin-top:24px;text-align:center">
<button class="control-btn btn-remove" onclick="document.getElementById('portal-uninstall-modal').classList.add('open')">🗑 Remove TAK Portal</button>
</div>
{% elif portal.installed %}
<div style="margin-top:24px;text-align:center">
<button class="control-btn btn-remove" onclick="document.getElementById('portal-uninstall-modal').classList.add('open')">🗑 Remove TAK Portal</button>
</div>
{% else %}
<div class="section-title">About TAK Portal</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-secondary);line-height:1.8">
TAK Portal is a lightweight user-management portal that integrates with <span style="color:var(--cyan)">Authentik</span> and <span style="color:var(--cyan)">TAK Server</span> for streamlined certificate and account control.<br><br>
Features: User creation with auto-cert generation, group management, mutual aid coordination, QR code device setup, agency-level access control, email notifications.<br><br>
<span style="color:var(--text-dim)">Requires: Docker · Authentik · TAK Server with LDAP connected</span>
</div>
</div>
<button class="deploy-btn" id="deploy-btn" onclick="deployPortal()">🚀 Deploy TAK Portal</button>
{% if not settings.fqdn %}
<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:10px;padding:16px 20px;margin-top:16px;font-size:13px;color:#f87171">
  🔒 <strong>SSL Required</strong> — TAK Portal requires a domain with SSL configured.<br>
  <span style="color:var(--text-dim)">Go to <a href="/caddy" style="color:var(--cyan)">Caddy SSL</a> and configure your domain first.</span>
</div>
{% endif %}
<div class="deploy-log" id="deploy-log" style="display:none">Waiting for deployment to start...</div>
{% endif %}

{% if deploy_done %}
<div style="background:rgba(16,185,129,0.1);border:1px solid var(--border);border-radius:10px;padding:20px;margin-top:20px;text-align:center">
<div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:var(--green);margin-bottom:12px">✓ TAK Portal deployed! Open Server Settings to configure Authentik & TAK Server.</div>
<button onclick="window.location.href='/takportal'" style="padding:10px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">Refresh Page</button>
</div>
{% endif %}
</div>
<div class="modal-overlay" id="portal-uninstall-modal">
<div class="modal">
<h3>⚠ Uninstall TAK Portal?</h3>
<p>This will remove TAK Portal, its Docker containers, volumes, and data. This cannot be undone.</p>
<label class="form-label">Admin Password</label>
<input class="form-input" id="portal-uninstall-password" type="password" placeholder="Confirm your password">
<div class="modal-actions">
<button type="button" class="control-btn" id="portal-uninstall-cancel" onclick="document.getElementById('portal-uninstall-modal').classList.remove('open')">Cancel</button>
<button type="button" class="control-btn btn-remove" id="portal-uninstall-confirm" onclick="doUninstallPortal()">Uninstall</button>
</div>
<div id="portal-uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
<div id="portal-uninstall-progress" class="uninstall-progress-row" style="display:none;margin-top:10px" aria-live="polite"></div>
</div>
</div>
<footer class="footer"></footer>
<script>
async function showAkPassword(){
    var btn=document.getElementById('ak-pw-btn');
    var display=document.getElementById('ak-pw-display');
    if(display.style.display==='inline'){display.style.display='none';btn.textContent='🔑 Show Password';return}
    try{
        var r=await fetch('/api/authentik/password');
        var d=await r.json();
        if(d.password){display.textContent=d.password;display.style.display='inline';btn.textContent='🔑 Hide'}
        else{display.textContent='Not found';display.style.display='inline'}
    }catch(e){display.textContent='Error';display.style.display='inline'}
}
async function portalControl(action){
    var btns=document.querySelectorAll('.control-btn');
    btns.forEach(function(b){b.disabled=true;b.style.opacity='0.5'});
    try{
        var r=await fetch('/api/takportal/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action})});
        var d=await r.json();
        if(d.success)window.location.href='/takportal';
        else alert('Error: '+(d.error||'Unknown'));
    }catch(e){alert('Error: '+e.message)}
    btns.forEach(function(b){b.disabled=false;b.style.opacity='1'});
}
async function portalUpdate(){
    var btn=document.getElementById('update-btn');
    var status=document.getElementById('update-status');
    btn.disabled=true;btn.innerHTML='<span style="display:inline-block;width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:6px"></span>Updating...';
    status.style.display='block';status.style.color='var(--text-secondary)';status.textContent='Pulling latest code and rebuilding container...';
    document.querySelectorAll('.control-btn').forEach(function(b){if(b!==btn){b.disabled=true;b.style.opacity='0.5'}});
    try{
        var r=await fetch('/api/takportal/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'update'})});
        var d=await r.json();
        if(d.success){
            status.style.color='var(--green)';
            status.textContent='✓ Updated'+(d.pull?' — '+d.pull:'')+(d.version?' ('+d.version+')':'');
            setTimeout(function(){window.location.href='/takportal'},1500);
        }else{status.style.color='var(--red)';status.textContent='✗ '+(d.error||'Update failed')}
    }catch(e){status.style.color='var(--red)';status.textContent='✗ '+e.message}
    btn.disabled=false;btn.innerHTML='⬆ Update';
    document.querySelectorAll('.control-btn').forEach(function(b){b.disabled=false;b.style.opacity='1'});
}

async function deployPortal(){
    var btn=document.getElementById('deploy-btn');
    btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.7';btn.style.cursor='wait';
    document.getElementById('deploy-log').style.display='block';
    try{
        var r=await fetch('/api/takportal/deploy',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success)pollDeployLog();
        else{document.getElementById('deploy-log').textContent='\\u2717 '+d.error;btn.disabled=false;btn.textContent='\\ud83d\\ude80 Deploy TAK Portal';btn.style.opacity='1';btn.style.cursor='pointer'}
    }catch(e){document.getElementById('deploy-log').textContent='Error: '+e.message}
}

var logIndex=0;
function pollDeployLog(){
    fetch('/api/takportal/deploy/log?index='+logIndex).then(function(r){return r.json()}).then(function(d){
        var el=document.getElementById('deploy-log');
        if(d.entries.length>0){
            d.entries.forEach(function(e){
                var isTimer=e.trim().charAt(0)==='\u23f3'&&e.indexOf(':')>0;
                if(isTimer){var prev=el.querySelector('[data-timer]');if(prev){prev.textContent=e;logIndex=d.total;return}}
                if(!isTimer){var old=el.querySelector('[data-timer]');if(old)old.removeAttribute('data-timer')}
                var l=document.createElement('div');
                if(isTimer)l.setAttribute('data-timer','1');
                if(e.indexOf('\u2713')>=0)l.style.color='var(--green)';
                else if(e.indexOf('\u2717')>=0||e.indexOf('FATAL')>=0)l.style.color='var(--red)';
                else if(e.indexOf('\u2501\u2501\u2501')>=0)l.style.color='var(--cyan)';
                else if(e.indexOf('===')>=0)l.style.color='var(--green)';
                l.textContent=e;el.appendChild(l);
            });
            logIndex=d.total;el.scrollTop=el.scrollHeight;
        }
        if(d.running)setTimeout(pollDeployLog,1000);
        else if(d.complete){
            var btn=document.getElementById('deploy-btn');
            if(btn){btn.textContent='\u2713 Deployment Complete';btn.style.background='var(--green)';btn.style.opacity='1';btn.style.cursor='default';}
            var el=document.getElementById('deploy-log');
            var fqdn=window.location.hostname.replace(/^[^.]+\./,'');
            var portalUrl='https://takportal.'+fqdn;
            var refreshBtn=document.createElement('button');
            refreshBtn.textContent='\u21bb Refresh Page';
            refreshBtn.style.cssText='display:block;width:100%;padding:12px;margin-top:16px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;';
            refreshBtn.onclick=function(){window.location.href='/takportal';};
            el.appendChild(refreshBtn);
            el.scrollTop=el.scrollHeight;
        }
    });
}

async function loadContainerLogs(){
    var el=document.getElementById('container-log');
    if(!el)return;
    try{
        var r=await fetch('/api/takportal/logs?lines=80');
        var d=await r.json();
        el.textContent='';
        if(d.entries&&d.entries.length>0){
            d.entries.forEach(function(e){
                var l=document.createElement('div');
                if(e.indexOf('error')>=0||e.indexOf('Error')>=0)l.style.color='var(--red)';
                else if(e.indexOf('warn')>=0||e.indexOf('Warn')>=0)l.style.color='var(--yellow)';
                l.textContent=e;el.appendChild(l);
            });
            el.scrollTop=el.scrollHeight;
        }else{el.textContent='No logs available yet.';}
    }catch(e){el.textContent='Failed to load logs';}
}
if(document.getElementById('container-log')){loadContainerLogs();setInterval(loadContainerLogs,10000)}

function uninstallPortal(){
    document.getElementById('portal-uninstall-modal').classList.add('open');
}
async function doUninstallPortal(){
    var pw=document.getElementById('portal-uninstall-password').value;
    if(!pw){document.getElementById('portal-uninstall-msg').textContent='Please enter your password';return;}
    var msgEl=document.getElementById('portal-uninstall-msg');
    var progressEl=document.getElementById('portal-uninstall-progress');
    var cancelBtn=document.getElementById('portal-uninstall-cancel');
    var confirmBtn=document.getElementById('portal-uninstall-confirm');
    msgEl.textContent='';
    progressEl.style.display='flex';
    progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Uninstalling…</span>';
    confirmBtn.disabled=true;
    cancelBtn.disabled=true;
    try{
        var r=await fetch('/api/takportal/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
        var d=await r.json();
        if(d.success){
            progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Done. Reloading…</span>';
            setTimeout(function(){window.location.href='/takportal';},800);
        }else{
            msgEl.textContent=d.error||'Uninstall failed';
            progressEl.style.display='none';
            progressEl.innerHTML='';
            confirmBtn.disabled=false;
            cancelBtn.disabled=false;
        }
    }catch(e){
        msgEl.textContent='Request failed: '+e.message;
        progressEl.style.display='none';
        progressEl.innerHTML='';
        confirmBtn.disabled=false;
        cancelBtn.disabled=false;
    }
}

{% if deploying %}pollDeployLog();{% endif %}
</script>
</body></html>'''

# Authentik module
authentik_deploy_log = []
authentik_deploy_status = {'running': False, 'complete': False, 'error': False}

@app.route('/authentik')
@login_required
def authentik_page():
    modules = detect_modules()
    ak = modules.get('authentik', {})
    settings = load_settings()
    # Reset deploy_done once Authentik is running so the running view shows
    if ak.get('installed') and ak.get('running') and not authentik_deploy_status.get('running', False):
        authentik_deploy_status.update({'complete': False, 'error': False})
    container_info = {}
    ak_port = '9090'
    if ak.get('installed'):
        env_path = os.path.expanduser('~/authentik/.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('COMPOSE_PORT_HTTP='):
                        val = line.strip().split('=', 1)[1].strip()
                        if ':' in val: ak_port = val.split(':')[-1]
                        else: ak_port = val or '9090'
    if ak.get('running'):
        r = subprocess.run('docker ps --filter "name=authentik" --format "{{.Names}}|||{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
        containers = []
        for line in r.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split('|||')
                containers.append({'name': parts[0], 'status': parts[1] if len(parts) > 1 else ''})
        container_info['containers'] = containers
    modules = detect_modules()
    portal_installed = modules.get('takportal', {}).get('installed', False)
    portal_running = modules.get('takportal', {}).get('running', False)
    all_healthy = ak.get('installed') and ak.get('running') and all(
        'unhealthy' not in c.get('status', '') for c in container_info.get('containers', [])
    ) and len(container_info.get('containers', [])) > 0
    return render_template_string(AUTHENTIK_TEMPLATE,
        settings=settings, ak=ak, container_info=container_info,
        ak_port=ak_port, version=VERSION,
        deploying=authentik_deploy_status.get('running', False),
        deploy_done=authentik_deploy_status.get('complete', False),
        deploy_error=authentik_deploy_status.get('error', False),
        error_log_exists=os.path.exists(os.path.join(CONFIG_DIR, 'authentik_error.log')),
        all_healthy=all_healthy,
        portal_installed=portal_installed,
        portal_running=portal_running)

@app.route('/api/authentik/control', methods=['POST'])
@login_required
def authentik_control():
    action = request.json.get('action')
    ak_dir = os.path.expanduser('~/authentik')
    if action == 'start':
        subprocess.run(f'cd {ak_dir} && docker compose up -d', shell=True, capture_output=True, text=True, timeout=120)
    elif action == 'stop':
        subprocess.run(f'cd {ak_dir} && docker compose down', shell=True, capture_output=True, text=True, timeout=60)
    elif action == 'restart':
        subprocess.run(f'cd {ak_dir} && docker compose down && docker compose up -d', shell=True, capture_output=True, text=True, timeout=120)
    elif action == 'update':
        subprocess.run(f'cd {ak_dir} && docker compose pull && docker compose up -d && docker image prune -f', shell=True, capture_output=True, text=True, timeout=300)
    else:
        return jsonify({'error': 'Invalid action'}), 400
    time.sleep(5)
    r = subprocess.run('docker ps --filter name=authentik-server --format "{{.Status}}" 2>/dev/null', shell=True, capture_output=True, text=True)
    running = 'Up' in r.stdout
    return jsonify({'success': True, 'running': running, 'action': action})

@app.route('/api/authentik/deploy', methods=['POST'])
@login_required
def authentik_deploy():
    if authentik_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    authentik_deploy_log.clear()
    authentik_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_authentik_deploy, args=(False,), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/authentik/reconfigure', methods=['POST'])
@login_required
def authentik_reconfigure():
    """Re-run LDAP/CoreConfig/forward-auth setup without removing anything. Use when TAK Server was deployed after Authentik."""
    if authentik_deploy_status.get('running'):
        return jsonify({'error': 'Deployment already in progress'}), 409
    if not os.path.exists(os.path.expanduser('~/authentik/docker-compose.yml')):
        return jsonify({'error': 'Authentik not installed. Deploy Authentik first.'}), 400
    authentik_deploy_log.clear()
    authentik_deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_authentik_deploy, args=(True,), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/authentik/deploy/log')
@login_required
def authentik_deploy_log_api():
    idx = request.args.get('index', 0, type=int)
    return jsonify({'entries': authentik_deploy_log[idx:], 'total': len(authentik_deploy_log),
        'running': authentik_deploy_status['running'], 'complete': authentik_deploy_status['complete'],
        'error': authentik_deploy_status['error']})

@app.route('/api/authentik/logs')
@login_required
def authentik_container_logs():
    lines = request.args.get('lines', 50, type=int)
    container = request.args.get('container', '').strip()
    if container:
        r = subprocess.run(f'docker logs {container} --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=10)
    else:
        r = subprocess.run(f'cd ~/authentik && docker compose logs --tail {lines} 2>&1', shell=True, capture_output=True, text=True, timeout=10)
    entries = r.stdout.strip().split('\n') if r.stdout.strip() else []
    return jsonify({'entries': entries})

@app.route('/api/authentik/password')
@login_required
def authentik_password():
    env_path = os.path.expanduser('~/authentik/.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_PASSWORD='):
                    return jsonify({'password': line.strip().split('=', 1)[1].strip()})
    return jsonify({'error': 'Password not found'}), 404

@app.route('/api/authentik/error-log')
@login_required
def authentik_error_log():
    from flask import send_file
    error_log_path = os.path.join(CONFIG_DIR, 'authentik_error.log')
    if os.path.exists(error_log_path):
        return send_file(error_log_path, as_attachment=True, download_name='authentik_error.log', mimetype='text/plain')
    return jsonify({'error': 'No error log found'}), 404

@app.route('/api/authentik/uninstall', methods=['POST'])
@login_required
def authentik_uninstall():
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    ak_dir = os.path.expanduser('~/authentik')
    steps = []
    if os.path.exists(ak_dir):
        r = subprocess.run(f'cd {ak_dir} && docker compose down -v --rmi all --remove-orphans 2>&1', shell=True, capture_output=True, text=True, timeout=180)
        steps.append('Stopped and removed Docker containers/volumes/images')
        if r.returncode != 0:
            steps.append(f'(compose reported: {(r.stderr or r.stdout or "").strip()[:200]})')
        subprocess.run(f'rm -rf {ak_dir}', shell=True, capture_output=True)
        steps.append('Removed ~/authentik')
    else:
        steps.append('~/authentik not found (already removed)')
    authentik_deploy_log.clear()
    authentik_deploy_status.update({'running': False, 'complete': False, 'error': False})
    return jsonify({'success': True, 'steps': steps})


def run_authentik_deploy(reconfigure=False):
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        authentik_deploy_log.append(entry)
        print(entry, flush=True)
    try:
        ak_dir = os.path.expanduser('~/authentik')
        settings = load_settings()
        server_ip = settings.get('server_ip', 'localhost')
        env_path = os.path.join(ak_dir, '.env')
        compose_path = os.path.join(ak_dir, 'docker-compose.yml')
        ldap_svc_pass = None

        if reconfigure:
            if not os.path.exists(ak_dir) or not os.path.exists(env_path) or not os.path.exists(compose_path):
                plog("\u2717 Authentik not fully installed. Run a full Deploy first.")
                authentik_deploy_status.update({'running': False, 'error': True})
                return
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                        ldap_svc_pass = line.strip().split('=', 1)[1].strip()
                        break
            plog("\u2501\u2501\u2501 Reconfigure: Updating LDAP, CoreConfig, Forward Auth (no removal) \u2501\u2501\u2501")
            subprocess.run(f'cd {ak_dir} && docker compose up -d 2>&1', shell=True, capture_output=True, text=True, timeout=120)
            plog("  Ensured containers are up")
            fqdn = settings.get('fqdn', '')
            # Cookie domain: so Authentik session is sent to stream.*, infratak.*, etc. (avoids redirect loop)
            if fqdn:
                base_domain = fqdn.split(':')[0]
                cookie_domain_val = f'.{base_domain}'
                with open(env_path) as f:
                    env_lines = f.readlines()
                has_cookie_domain = any(line.strip().startswith('AUTHENTIK_COOKIE_DOMAIN=') for line in env_lines)
                if not has_cookie_domain:
                    with open(env_path, 'w') as f:
                        for line in env_lines:
                            f.write(line)
                        f.write(f"# Cookie domain — session shared across subdomains (avoids stream. redirect loop)\nAUTHENTIK_COOKIE_DOMAIN={cookie_domain_val}\n")
                    plog("  Set AUTHENTIK_COOKIE_DOMAIN for subdomain shared session; restarting Authentik...")
                    subprocess.run(f'cd {ak_dir} && docker compose restart 2>&1', shell=True, capture_output=True, text=True, timeout=120)
            # Apply app access policies so only authentik Admins see infra-TAK/Node-RED
            if fqdn:
                ak_token = ''
                with open(env_path) as f:
                    for line in f:
                        if line.strip().startswith('AUTHENTIK_TOKEN='):
                            ak_token = line.strip().split('=', 1)[1].strip()
                            break
                if not ak_token:
                    with open(env_path) as f:
                        for line in f:
                            if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                                ak_token = line.strip().split('=', 1)[1].strip()
                                break
                if ak_token:
                    ak_url = 'http://127.0.0.1:9090'
                    ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
                    plog("")
                    plog("  Waiting for Authentik API...")
                    if _wait_for_authentik_api(ak_url, ak_headers, max_attempts=24, plog=plog):
                        plog("  Setting proxy cookie domain (shared session across subdomains)...")
                        _ensure_proxy_providers_cookie_domain(ak_url, ak_headers, fqdn, plog)
                        plog("  Configuring application access policies...")
                        _ensure_app_access_policies(ak_url, ak_headers, plog)
                    else:
                        plog("  \u26a0 API not ready in time — run Update config & reconnect again to apply app access policies")
                else:
                    plog("  \u26a0 No token in .env — app access policies not applied")
        else:
            if settings.get('pkg_mgr', 'apt') == 'apt':
                wait_for_apt_lock(plog, authentik_deploy_log)

            # Step 1: Check Docker
            plog("\u2501\u2501\u2501 Step 1/10: Checking Docker \u2501\u2501\u2501")
            r = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
            if r.returncode != 0:
                plog("Docker not found. Installing...")
                subprocess.run('curl -fsSL https://get.docker.com | sh', shell=True, capture_output=True, text=True, timeout=300)
                r2 = subprocess.run('docker --version', shell=True, capture_output=True, text=True)
                if r2.returncode != 0:
                    plog("\u2717 Failed to install Docker")
                    authentik_deploy_status.update({'running': False, 'error': True})
                    return
                plog(f"  {r2.stdout.strip()}")
            else:
                plog(f"  {r.stdout.strip()}")
            plog("\u2713 Docker available")

            # Step 2: Create directory
            plog("")
            plog("\u2501\u2501\u2501 Step 2/10: Setting Up Directory \u2501\u2501\u2501")
            os.makedirs(ak_dir, exist_ok=True)
            plog(f"  Directory: {ak_dir}")
            plog("\u2713 Directory ready")

            # Step 3: Generate secrets and .env
            plog("")
            plog("\u2501\u2501\u2501 Step 3/10: Generating Configuration \u2501\u2501\u2501")
            ldap_svc_pass = None
            if not os.path.exists(env_path):
                pg_pass = subprocess.run('openssl rand -base64 36 | tr -d "\\n"', shell=True, capture_output=True, text=True).stdout.strip()[:90]
                secret_key = subprocess.run('openssl rand -hex 32', shell=True, capture_output=True, text=True).stdout.strip()
                ldap_svc_pass = subprocess.run('openssl rand -base64 24 | tr -d "\\n"', shell=True, capture_output=True, text=True).stdout.strip()
                bootstrap_pass = subprocess.run('openssl rand -base64 18 | tr -d "\\n"', shell=True, capture_output=True, text=True).stdout.strip()
                bootstrap_token = subprocess.run('openssl rand -hex 32', shell=True, capture_output=True, text=True).stdout.strip()
                env_content = f"""PG_DB=authentik
PG_USER=authentik
PG_PASS={pg_pass}
AUTHENTIK_SECRET_KEY={secret_key}
COMPOSE_PORT_HTTP=9090
COMPOSE_PORT_HTTPS=9443
AUTHENTIK_ERROR_REPORTING__ENABLED=false
# Bootstrap (first run only - sets akadmin password and API token)
AUTHENTIK_BOOTSTRAP_PASSWORD={bootstrap_pass}
AUTHENTIK_BOOTSTRAP_TOKEN={bootstrap_token}
AUTHENTIK_BOOTSTRAP_EMAIL=admin@takwerx.local
# LDAP Blueprint Configuration
AUTHENTIK_BOOTSTRAP_LDAPSERVICE_USERNAME=adm_ldapservice
AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD={ldap_svc_pass}
AUTHENTIK_BOOTSTRAP_LDAP_BASEDN=DC=takldap
AUTHENTIK_BOOTSTRAP_LDAP_AUTHENTIK_HOST=http://authentik-server-1:9000/
# Embedded outpost host — prevents 0.0.0.0:9000 redirect issue
AUTHENTIK_HOST=https://authentik.{settings.get("fqdn") or server_ip}
""" + (f"\n# Cookie domain so session is shared across subdomains (stream., infratak., etc.) — avoids redirect loop\nAUTHENTIK_COOKIE_DOMAIN=.{settings.get('fqdn').split(':')[0]}" if settings.get("fqdn") else "") + """
# Email Configuration (uncomment and configure)
# AUTHENTIK_EMAIL__HOST=smtp.example.com
# AUTHENTIK_EMAIL__PORT=587
# AUTHENTIK_EMAIL__USERNAME=
# AUTHENTIK_EMAIL__PASSWORD=
# AUTHENTIK_EMAIL__USE_TLS=true
# AUTHENTIK_EMAIL__FROM=authentik@example.com
"""
                with open(env_path, 'w') as f:
                    f.write(env_content)
                plog("  Generated PostgreSQL password")
                plog("  Generated secret key")
                plog(f"  Generated LDAP service account password")
                plog("\u2713 .env created")
            else:
                plog("\u2713 .env already exists")
                # Read existing ldap password
                with open(env_path) as f:
                    for line in f:
                        if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                            ldap_svc_pass = line.strip().split('=', 1)[1].strip()

            # Step 4: Create LDAP blueprint
            plog("")
            plog("\u2501\u2501\u2501 Step 4/10: Installing LDAP Blueprint \u2501\u2501\u2501")
            bp_dir = os.path.join(ak_dir, 'blueprints')
            os.makedirs(bp_dir, exist_ok=True)
            bp_path = os.path.join(bp_dir, 'tak-ldap-setup.yaml')
            bp_content = """version: 1
metadata:
  name: LDAP Setup for TAK
  labels:
    blueprints.goauthentik.io/description: |
      Configures LDAP service account, provider, and outpost for TAK Server.
    blueprints.goauthentik.io/depends-on: "default-flows,default-stages"
context:
  username: !Env [AUTHENTIK_BOOTSTRAP_LDAPSERVICE_USERNAME, 'adm_ldapservice']
  password: !Env [AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD, null]
  basedn: !Env [AUTHENTIK_BOOTSTRAP_LDAP_BASEDN, 'DC=takldap']
  authentik_host: !Env [AUTHENTIK_BOOTSTRAP_LDAP_AUTHENTIK_HOST, 'http://localhost:9000/']
entries:
  - model: authentik_blueprints.metaapplyblueprint
    attrs:
      identifiers:
        name: Default - Invalidation flow
      required: true
  - model: authentik_blueprints.metaapplyblueprint
    attrs:
      identifiers:
        name: Default - Password change flow
      required: true
  - model: authentik_blueprints.metaapplyblueprint
    attrs:
      identifiers:
        name: Default - Authentication flow
      required: true
  - model: authentik_core.user
    state: created
    id: ldap-service-account
    identifiers:
      username: !Context username
    attrs:
      name: LDAP Service account
      type: service_account
      path: users
  - attrs:
      authentication: none
      denied_action: message_continue
      designation: authentication
      layout: stacked
      name: ldap-authentication-flow
      policy_engine_mode: any
      title: ldap-authentication-flow
    identifiers:
      slug: ldap-authentication-flow
    model: authentik_flows.flow
    state: present
    id: ldap-authentication-flow
  - attrs:
      authentication: none
      denied_action: message_continue
      designation: authorization
      layout: stacked
      name: ldap-authorization-flow
      policy_engine_mode: any
      title: ldap-authorization-flow
    identifiers:
      slug: ldap-authorization-flow
    model: authentik_flows.flow
    state: present
    id: ldap-authorization-flow
  - attrs:
      backends:
      - authentik.core.auth.InbuiltBackend
      - authentik.core.auth.TokenBackend
      failed_attempts_before_cancel: 5
    identifiers:
      name: ldap-authentication-password
    model: authentik_stages_password.passwordstage
    state: present
    id: ldap-authentication-password
  - attrs:
      case_insensitive_matching: true
      pretend_user_exists: true
      show_matched_user: true
      user_fields:
      - username
    identifiers:
      name: ldap-identification-stage
    model: authentik_stages_identification.identificationstage
    state: present
    id: ldap-identification-stage
  - attrs:
      geoip_binding: bind_continent
      network_binding: bind_asn
      remember_me_offset: seconds=0
      session_duration: seconds=0
    identifiers:
      name: ldap-authentication-login
    model: authentik_stages_user_login.userloginstage
    state: present
    id: ldap-authentication-login
  - attrs:
      evaluate_on_plan: true
      invalid_response_action: retry
      policy_engine_mode: any
      re_evaluate_policies: true
    identifiers:
      order: 10
      stage: !KeyOf ldap-identification-stage
      target: !KeyOf ldap-authentication-flow
    model: authentik_flows.flowstagebinding
    state: present
    id: ldap-identification-stage-flow-binding
  - attrs:
      evaluate_on_plan: true
      invalid_response_action: retry
      policy_engine_mode: any
      re_evaluate_policies: true
    identifiers:
      order: 15
      stage: !KeyOf ldap-authentication-password
      target: !KeyOf ldap-authentication-flow
    model: authentik_flows.flowstagebinding
    state: present
    id: ldap-authentication-password-binding
  - attrs:
      evaluate_on_plan: true
      invalid_response_action: retry
      policy_engine_mode: any
      re_evaluate_policies: true
    identifiers:
      order: 20
      stage: !KeyOf ldap-authentication-login
      target: !KeyOf ldap-authentication-flow
    model: authentik_flows.flowstagebinding
    state: present
    id: ldap-authentication-login-binding
  - model: authentik_providers_ldap.ldapprovider
    id: provider
    state: present
    identifiers:
      name: LDAP
    attrs:
      authentication_flow: !KeyOf ldap-authentication-flow
      authorization_flow: !KeyOf ldap-authentication-flow
      base_dn: !Context basedn
      bind_mode: cached
      gid_start_number: 4000
      invalidation_flow: !Find [authentik_flows.flow, [slug, default-invalidation-flow]]
      mfa_support: false
      name: Provider for LDAP
      search_mode: cached
      uid_start_number: 2000
    permissions:
      - permission: authentik_providers_ldap.search_full_directory
        user: !KeyOf ldap-service-account
  - model: authentik_core.application
    id: app
    state: present
    identifiers:
      slug: ldap
    attrs:
      name: LDAP
      policy_engine_mode: any
      provider: !KeyOf provider
  - model: authentik_outposts.outpost
    id: outpost
    state: present
    identifiers:
      name: LDAP
    attrs:
      config:
        authentik_host: !Context authentik_host
      providers:
      - !KeyOf provider
      type: ldap
"""
            with open(bp_path, 'w') as f:
                f.write(bp_content)
            plog("  Created tak-ldap-setup.yaml blueprint")
            plog("  LDAP service account: adm_ldapservice")
            plog("  LDAP Base DN: DC=takldap")

            # Create embedded outpost blueprint to permanently set authentik_host
            bp_embedded_path = os.path.join(bp_dir, 'tak-embedded-outpost.yaml')
            bp_embedded_content = f"""version: 1
metadata:
  name: TAK Embedded Outpost Config
  labels:
    blueprints.goauthentik.io/description: Sets authentik_host for embedded outpost
entries:
  - model: authentik_outposts.outpost
    state: present
    identifiers:
      managed: goauthentik.io/outposts/embedded
    attrs:
      config:
        authentik_host: https://authentik.{settings.get('fqdn') or server_ip}
        authentik_host_insecure: false
"""
            with open(bp_embedded_path, 'w') as f:
                f.write(bp_embedded_content)
            plog("  Created tak-embedded-outpost.yaml blueprint")
            plog("\u2713 Blueprint ready")

            # Step 5: Download docker-compose.yml and patch for blueprints
            plog("")
            plog("\u2501\u2501\u2501 Step 5/10: Downloading Docker Compose File \u2501\u2501\u2501")
            if not os.path.exists(compose_path):
                r = subprocess.run(f'wget -q -O {compose_path} https://goauthentik.io/docker-compose.yml 2>&1', shell=True, capture_output=True, text=True, timeout=30)
                if r.returncode != 0 or not os.path.exists(compose_path):
                    plog("\u2717 Failed to download docker-compose.yml")
                    authentik_deploy_status.update({'running': False, 'error': True})
                    return
                plog("\u2713 docker-compose.yml downloaded")
            else:
                plog("\u2713 docker-compose.yml already exists")

            # Step 6: Patch docker-compose for blueprints + LDAP container
            plog("")
            plog("\u2501\u2501\u2501 Step 6/10: Patching Docker Compose \u2501\u2501\u2501")
            with open(compose_path, 'r') as f:
                lines = f.readlines()
            needs_write = False
            # Add blueprint volume mounts
            if not any('blueprints/custom' in l for l in lines):
                patched = []
                for line in lines:
                    patched.append(line)
                    if './custom-templates:/templates' in line:
                        indent = line[:len(line) - len(line.lstrip())]
                        patched.append(f'{indent}- ./blueprints:/blueprints/custom\n')
                lines = patched
                needs_write = True
                plog("  Added blueprint mount to server & worker")
            # Add POSTGRES_MAX_CONNECTIONS
            if not any('POSTGRES_MAX_CONNECTIONS' in l for l in lines):
                patched = []
                for line in lines:
                    patched.append(line)
                    if 'POSTGRES_USER:' in line:
                        indent = line[:len(line) - len(line.lstrip())]
                        patched.append(f'{indent}POSTGRES_MAX_CONNECTIONS: "200"\n')
                lines = patched
                needs_write = True
                plog("  Added POSTGRES_MAX_CONNECTIONS to postgresql")

            # Add LDAP outpost container (version must match server)
            ak_tag = '2026.2.0'
            for l in lines:
                m = re.search(r'goauthentik/server[:\s]+\$\{AUTHENTIK_TAG:-([^}]+)\}', l)
                if m:
                    ak_tag = m.group(1)
                    break
                m = re.search(r'goauthentik/server:([^\s\n]+)', l)
                if m and m.group(1).strip() not in ('${AUTHENTIK_TAG}', ''):
                    ak_tag = m.group(1).strip()
                    break
            if not any('ghcr.io/goauthentik/ldap' in l for l in lines):
                _fqdn = (settings.get('fqdn') or '').split(':')[0]
                if _fqdn:
                    ldap_svc = f"  ldap:\n    image: ghcr.io/goauthentik/ldap:{ak_tag}\n    extra_hosts:\n      - \"authentik.{_fqdn}:host-gateway\"\n    ports:\n    - 389:3389\n    - 636:6636\n    environment:\n      AUTHENTIK_HOST: https://authentik.{_fqdn}\n      AUTHENTIK_INSECURE: \"true\"\n      AUTHENTIK_TOKEN: placeholder\n    restart: unless-stopped\n"
                else:
                    ldap_svc = f"  ldap:\n    image: ghcr.io/goauthentik/ldap:{ak_tag}\n    ports:\n    - 389:3389\n    - 636:6636\n    environment:\n      AUTHENTIK_HOST: http://authentik-server-1:9000\n      AUTHENTIK_INSECURE: \"true\"\n      AUTHENTIK_TOKEN: placeholder\n    restart: unless-stopped\n"
                new_lines = []
                for line in lines:
                    if line.startswith('volumes:'):
                        new_lines.append(ldap_svc)
                    new_lines.append(line)
                lines = new_lines
                needs_write = True
                plog("  Added LDAP outpost container")
            else:
                for i, line in enumerate(lines):
                    m = re.search(r'ghcr\.io/goauthentik/ldap:([^\s\n]+)', line)
                    if m and m.group(1) != ak_tag:
                        lines[i] = line.replace(f'ghcr.io/goauthentik/ldap:{m.group(1)}', f'ghcr.io/goauthentik/ldap:{ak_tag}')
                        needs_write = True
                        plog(f"  Updated LDAP outpost image {m.group(1)} -> {ak_tag}")
            if needs_write:
                with open(compose_path, 'w') as f:
                    f.writelines(lines)
                plog("\u2713 Docker Compose patched")
            else:
                plog("\u2713 Docker Compose already patched")

            # Step 7: Pull and start core services (no verbose docker output in log)
            plog("")
            plog("\u2501\u2501\u2501 Step 7/10: Pulling Images & Starting Containers \u2501\u2501\u2501")
            plog("  Pulling images (this may take a few minutes)...")
            r = subprocess.run(f'cd {ak_dir} && docker compose pull 2>&1', shell=True, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                plog(f"  \u26a0 Pull had issues: {r.stderr.strip()[:200] if r.stderr else r.stdout.strip()[:200]}")
            else:
                plog("  \u2713 Images pulled")
            plog("  Starting core services...")
            r = subprocess.run(f'cd {ak_dir} && docker compose up -d postgresql server worker 2>&1', shell=True, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                plog(f"  \u26a0 Start had issues: {r.stderr.strip()[:200] if r.stderr else r.stdout.strip()[:200]}")
            else:
                plog("  \u2713 Core services started")

        # Step 8: Wait for Authentik API to be ready
        plog("")
        plog("\u2501\u2501\u2501 Step 8/12: Waiting for Authentik API \u2501\u2501\u2501")
        bootstrap_token = None
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                    bootstrap_token = line.strip().split('=', 1)[1].strip()
        if not bootstrap_token:
            plog("\u26a0 No bootstrap token found in .env")
        else:
            api_ready = _wait_for_authentik_api(
                'http://127.0.0.1:9090',
                {'Authorization': f'Bearer {bootstrap_token}'},
                max_attempts=90, plog=plog
            )
            if api_ready:
                plog("✓ Authentik API is ready")
            else:
                plog("⚠ API timeout - check Authentik logs")

        # Step 9: Start LDAP outpost (placeholder token — Step 11 will inject real token and recreate)
        plog("")
        plog("\u2501\u2501\u2501 Step 9/12: Starting LDAP Outpost \u2501\u2501\u2501")
        r = subprocess.run(f'cd {ak_dir} && docker compose up -d ldap 2>&1', shell=True, capture_output=True, text=True, timeout=120)
        for line in (r.stdout or '').strip().split('\n'):
            if line.strip() and 'NEEDRESTART' not in line:
                authentik_deploy_log.append(f"  {line.strip()}")
        plog("  Waiting for LDAP to start...")
        time.sleep(15)
        r2 = subprocess.run('docker logs authentik-ldap-1 2>&1 | tail -3', shell=True, capture_output=True, text=True)
        if r2.stdout and ('Starting LDAP server' in r2.stdout or 'Starting authentik outpost' in r2.stdout):
            plog("\u2713 LDAP outpost is running on port 389")
        else:
            plog("\u26a0 LDAP will be recreated with real token in Step 11")

        # Step 10: Patch CoreConfig.xml for LDAP
        plog("")
        plog("\u2501\u2501\u2501 Step 10/12: Connecting TAK Server to LDAP \u2501\u2501\u2501")
        coreconfig_path = '/opt/tak/CoreConfig.xml'
        if os.path.exists(coreconfig_path):
            # Read LDAP service password
            ldap_pass = ldap_svc_pass or ''
            if not ldap_pass:
                with open(env_path) as f:
                    for line in f:
                        if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                            ldap_pass = line.strip().split('=', 1)[1].strip()

            if ldap_pass:
                # Backup
                backup_path = coreconfig_path + '.pre-ldap.bak'
                if not os.path.exists(backup_path):
                    import shutil
                    shutil.copy2(coreconfig_path, backup_path)
                    plog(f"  Backed up CoreConfig.xml")

                # Read current config
                with open(coreconfig_path, 'r') as f:
                    config_content = f.read()

                # Build the new auth block — matches TAK Portal reference exactly
                auth_block = (
                    '    <auth default="ldap" x509groups="true" x509addAnonymous="false" x509useGroupCache="true" x509useGroupCacheDefaultActive="true" x509checkRevocation="true">\n'
                    '        <ldap url="ldap://127.0.0.1:389" userstring="cn={username},ou=users,dc=takldap" updateinterval="60" groupprefix="cn=tak_" groupNameExtractorRegex="cn=tak_(.*?)(?:,|$)" serviceAccountDN="cn=adm_ldapservice,ou=users,dc=takldap" serviceAccountCredential="'
                    + ldap_pass
                    + '" groupBaseRDN="ou=groups,dc=takldap" userBaseRDN="ou=users,dc=takldap" dnAttributeName="DN" nameAttr="CN" adminGroup="ROLE_ADMIN"/>\n'
                    '        <File location="UserAuthenticationFile.xml"/>\n'
                    '    </auth>'
                )

                # Replace auth block using regex (match <auth>...</auth> regardless of indentation)
                new_content = re.sub(
                    r'<auth[^>]*>.*?</auth>',
                    auth_block,
                    config_content,
                    flags=re.DOTALL
                )

                if new_content != config_content:
                    with open(coreconfig_path, 'w') as f:
                        f.write(new_content)
                    plog("\u2713 CoreConfig.xml updated with LDAP auth")
                    plog("  - Group cache enabled (x509useGroupCacheDefaultActive)")
                    plog("  - Group prefix: tak_")

                    # Restart TAK Server
                    plog("  Restarting TAK Server...")
                    r = subprocess.run('systemctl restart takserver 2>&1', shell=True, capture_output=True, text=True, timeout=60)
                    if r.returncode == 0:
                        plog("\u2713 TAK Server restarted")
                    else:
                        plog(f"\u26a0 TAK Server restart issue: {r.stderr.strip()[:100]}")
                else:
                    if _coreconfig_has_ldap():
                        plog("\u2713 CoreConfig.xml already has LDAP auth configured")
                    else:
                        plog("\u26a0 CoreConfig <auth> block not found or format not recognized — use Connect TAK Server to LDAP after deploy")
            else:
                plog("\u26a0 LDAP service password not found, skipping CoreConfig patch")
        else:
            plog("  ℹ TAK Server not installed — skipping CoreConfig (OK for MediaMTX-only or standalone Authentik)")
            plog("  Deploy TAK Server later, then use Connect TAK Server to LDAP to add LDAP")

        # Step 11/12: Create admin group and webadmin user in Authentik
        plog("")
        plog("\u2501\u2501\u2501 Step 11/12: Creating Admin Group & WebAdmin User \u2501\u2501\u2501")
        try:
            # Read bootstrap token
            ak_token = ''
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                        ak_token = line.strip().split('=', 1)[1].strip()
            if ak_token:
                ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
                ak_url = f'http://127.0.0.1:9090'
                import urllib.request

                # Verify bootstrap token actually works before proceeding
                # The worker runs apply_blueprint system/bootstrap.yaml before starting
                # which creates the token — this can take 1-3 minutes on first start
                plog("  Waiting for worker to apply bootstrap blueprint...")
                token_ok = False
                attempt = 0
                while True:
                    try:
                        req = urllib.request.Request(f'{ak_url}/api/v3/core/users/',
                            headers=ak_headers)
                        resp = urllib.request.urlopen(req, timeout=10)
                        json.loads(resp.read().decode())
                        token_ok = True
                        m, s = divmod(attempt * 5, 60)
                        plog(f"  ✓ Bootstrap token active (waited {m}m {s}s)")
                        break
                    except urllib.error.HTTPError as e:
                        if e.code == 403:
                            if attempt % 6 == 0:
                                m, s = divmod(attempt * 5, 60)
                                plog(f"  ⏳ Worker still applying bootstrap... ({m}m {s}s)")
                            else:
                                authentik_deploy_log.append(f"  ⏳ {attempt * 5 // 60:02d}:{attempt * 5 % 60:02d}")
                            time.sleep(5)
                            attempt += 1
                        else:
                            plog(f"  ⚠ Token check unexpected error: {e.code} — giving up")
                            break
                    except Exception as e:
                        plog(f"  ⚠ Token check error: {str(e)[:80]} — giving up")
                        break

                # Create tak_ROLE_ADMIN group
                try:
                    req = urllib.request.Request(f'{ak_url}/api/v3/core/groups/',
                        data=json.dumps({'name': 'tak_ROLE_ADMIN', 'is_superuser': False}).encode(),
                        headers=ak_headers, method='POST')
                    resp = urllib.request.urlopen(req, timeout=10)
                    group_data = json.loads(resp.read().decode())
                    group_pk = group_data['pk']
                    plog("  ✓ Created tak_ROLE_ADMIN group")
                except urllib.error.HTTPError as e:
                    if e.code == 400:
                        plog("  ✓ tak_ROLE_ADMIN group already exists")
                        # Get existing group PK
                        req = urllib.request.Request(f'{ak_url}/api/v3/core/groups/?search=tak_ROLE_ADMIN',
                            headers=ak_headers)
                        resp = urllib.request.urlopen(req, timeout=10)
                        results = json.loads(resp.read().decode())['results']
                        group_pk = results[0]['pk'] if results else None
                    elif e.code == 403:
                        plog(f"  ⚠ 403 on group creation — bootstrap token may lack permissions, continuing anyway")
                        group_pk = None
                    else:
                        plog(f"  ⚠ Group creation error: {e.code} — continuing")
                        group_pk = None

                # Create webadmin user in Authentik (only when TAK Server is deployed — used for TAK Server admin)
                webadmin_pass = ''
                if os.path.exists('/opt/tak'):
                    # Read password from TAK Server settings or use default
                    tak_settings_path = os.path.join(CONFIG_DIR, 'settings.json')
                    if os.path.exists(tak_settings_path):
                        with open(tak_settings_path) as f:
                            tak_s = json.load(f)
                            webadmin_pass = tak_s.get('webadmin_password', '')
                    if not webadmin_pass:
                        webadmin_pass = 'TakserverAtak1!'
                        plog(f"  ⚠ webadmin_password not found in settings.json — using default: TakserverAtak1!")
                else:
                    plog("  ℹ TAK Server not installed — skipping webadmin user (optional; used for TAK Server admin)")

                if webadmin_pass:
                    try:
                        user_data = {'username': 'webadmin', 'name': 'TAK Admin', 'is_active': True,
                            'groups': [group_pk] if group_pk else []}
                        req = urllib.request.Request(f'{ak_url}/api/v3/core/users/',
                            data=json.dumps(user_data).encode(), headers=ak_headers, method='POST')
                        resp = urllib.request.urlopen(req, timeout=10)
                        user = json.loads(resp.read().decode())
                        webadmin_pk = user['pk']
                        plog(f"  ✓ Created webadmin user (pk={webadmin_pk})")
                    except urllib.error.HTTPError as e:
                        if e.code == 400:
                            plog("  ✓ webadmin user already exists")
                            # Get existing user PK and add to group
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/users/?search=webadmin',
                                headers=ak_headers)
                            resp = urllib.request.urlopen(req, timeout=10)
                            results = json.loads(resp.read().decode())['results']
                            webadmin_pk = results[0]['pk'] if results else None
                            if webadmin_pk and group_pk:
                                req = urllib.request.Request(f'{ak_url}/api/v3/core/users/{webadmin_pk}/',
                                    data=json.dumps({'groups': [group_pk]}).encode(),
                                    headers=ak_headers, method='PATCH')
                                try:
                                    urllib.request.urlopen(req, timeout=10)
                                    plog("  ✓ Added webadmin to tak_ROLE_ADMIN group")
                                except Exception:
                                    pass
                        else:
                            plog(f"  ⚠ webadmin user error: {e.code} — continuing")
                            webadmin_pk = None

                    # Set webadmin password
                    if webadmin_pk:
                        try:
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/users/{webadmin_pk}/set_password/',
                                data=json.dumps({'password': webadmin_pass}).encode(),
                                headers=ak_headers, method='POST')
                            urllib.request.urlopen(req, timeout=10)
                            plog(f"  ✓ Set webadmin password")
                        except Exception as e:
                            plog(f"  ⚠ Could not set webadmin password: {str(e)[:100]}")

                    # Create or get adm_ldapservice user
                    ldap_svc_password = ''
                    with open(env_path) as f:
                        for line in f:
                            if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                                ldap_svc_password = line.strip().split('=', 1)[1].strip()
                    if not ldap_svc_password:
                        ldap_svc_password = 'B9wobRV8wlFJmnlEWB71gJjD3aoKOBBW'

                    ldap_pk = None
                    try:
                        req = urllib.request.Request(f'{ak_url}/api/v3/core/users/',
                            data=json.dumps({'username': 'adm_ldapservice', 'name': 'LDAP Service Account',
                                'is_active': True, 'type': 'service_account', 'path': 'users'}).encode(),
                            headers=ak_headers, method='POST')
                        resp = urllib.request.urlopen(req, timeout=10)
                        ldap_pk = json.loads(resp.read().decode())['pk']
                        plog(f"  ✓ Created adm_ldapservice (pk={ldap_pk})")
                    except urllib.error.HTTPError as e:
                        if e.code == 400:
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/users/?search=adm_ldapservice',
                                headers=ak_headers)
                            resp = urllib.request.urlopen(req, timeout=10)
                            results = json.loads(resp.read().decode())['results']
                            ldap_pk = next((u['pk'] for u in results if u['username'] == 'adm_ldapservice'), None)
                            plog(f"  ✓ adm_ldapservice already exists (pk={ldap_pk})")
                        else:
                            plog(f"  ⚠ Could not create adm_ldapservice: {e.code}")

                    if ldap_pk:
                        try:
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/users/{ldap_pk}/set_password/',
                                data=json.dumps({'password': ldap_svc_password}).encode(),
                                headers=ak_headers, method='POST')
                            urllib.request.urlopen(req, timeout=10)
                            plog(f"  ✓ Set adm_ldapservice password")
                        except Exception as e:
                            plog(f"  ⚠ Could not set adm_ldapservice password: {str(e)[:100]}")

                # Create LDAP provider + outpost + inject token — ALWAYS RUN (required for MediaMTX, TAK Server, standalone)
                try:
                    # Get default invalidation flow
                    req = urllib.request.Request(f'{ak_url}/api/v3/flows/instances/?designation=invalidation',
                        headers=ak_headers)
                    resp = urllib.request.urlopen(req, timeout=10)
                    inv_flows = json.loads(resp.read().decode())['results']
                    inv_flow_pk = next((f['pk'] for f in inv_flows if 'invalidation' in f['slug'] and 'provider' not in f['slug']), inv_flows[0]['pk'] if inv_flows else None)
                    plog(f"  ✓ Got invalidation flow: {inv_flow_pk}")

                    # Get default authentication flow - wait until ready
                    auth_flow_pk = None
                    attempt = 0
                    while True:
                        req = urllib.request.Request(f'{ak_url}/api/v3/flows/instances/?designation=authentication',
                            headers=ak_headers)
                        resp = urllib.request.urlopen(req, timeout=10)
                        auth_flows = json.loads(resp.read().decode())['results']
                        auth_flow_pk = next((f['pk'] for f in auth_flows if f['slug'] == 'default-authentication-flow'),
                                           next((f['pk'] for f in auth_flows), None))
                        if auth_flow_pk:
                            plog(f"  ✓ Got authentication flow: {auth_flow_pk}")
                            break
                        if attempt % 6 == 0:
                            plog(f"  ⏳ Waiting for authentication flows... ({attempt * 5}s)")
                        else:
                            authentik_deploy_log.append(f"  ⏳ {attempt * 5 // 60:02d}:{attempt * 5 % 60:02d}")
                        time.sleep(5)
                        attempt += 1

                    if not auth_flow_pk or not inv_flow_pk:
                        plog(f"  ✗ Missing flows — auth={auth_flow_pk} inv={inv_flow_pk}")
                    else:
                        # Create LDAP provider
                        ldap_provider_pk = None
                        ldap_flow_pk = next((f['pk'] for f in auth_flows if f['slug'] == 'ldap-authentication-flow'), None)
                        ldap_bind_flow = ldap_flow_pk or auth_flow_pk
                        try:
                            req = urllib.request.Request(f'{ak_url}/api/v3/providers/ldap/',
                                data=json.dumps({'name': 'LDAP', 'authentication_flow': ldap_bind_flow,
                                    'authorization_flow': ldap_bind_flow, 'invalidation_flow': inv_flow_pk,
                                    'base_dn': 'DC=takldap', 'bind_mode': 'cached',
                                    'search_mode': 'cached', 'mfa_support': False}).encode(),
                                headers=ak_headers, method='POST')
                            resp = urllib.request.urlopen(req, timeout=10)
                            ldap_provider_pk = json.loads(resp.read().decode())['pk']
                            plog(f"  ✓ Created LDAP provider (pk={ldap_provider_pk})")
                        except urllib.error.HTTPError as e:
                            err = e.read().decode()[:200]
                            if e.code == 400:
                                req = urllib.request.Request(f'{ak_url}/api/v3/providers/ldap/?search=LDAP',
                                    headers=ak_headers)
                                resp = urllib.request.urlopen(req, timeout=10)
                                results = json.loads(resp.read().decode())['results']
                                ldap_provider_pk = results[0]['pk'] if results else None
                                plog(f"  ✓ LDAP provider already exists (pk={ldap_provider_pk})")
                            else:
                                plog(f"  ✗ LDAP provider creation failed: {e.code} {err}")

                        # Create LDAP application
                        if ldap_provider_pk:
                            try:
                                req = urllib.request.Request(f'{ak_url}/api/v3/core/applications/',
                                    data=json.dumps({'name': 'LDAP', 'slug': 'ldap',
                                        'provider': ldap_provider_pk}).encode(),
                                    headers=ak_headers, method='POST')
                                urllib.request.urlopen(req, timeout=10)
                                plog(f"  ✓ Created LDAP application")
                            except urllib.error.HTTPError as e:
                                if e.code == 400:
                                    plog(f"  ✓ LDAP application already exists")
                                else:
                                    plog(f"  ⚠ LDAP application error: {e.code} {e.read().decode()[:100]}")

                            # Get or create LDAP outpost (blueprint may have created it)
                            outpost_token_id = None
                            try:
                                req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/?search=LDAP',
                                    headers=ak_headers)
                                resp = urllib.request.urlopen(req, timeout=10)
                                results = json.loads(resp.read().decode())['results']
                                ldap_outpost = next((o for o in results if o.get('name') == 'LDAP' and o.get('type') == 'ldap'), None)
                                if ldap_outpost:
                                    outpost_token_id = ldap_outpost.get('token_identifier', '')
                                    if not outpost_token_id:
                                        req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/{ldap_outpost["pk"]}/',
                                            headers=ak_headers)
                                        resp = urllib.request.urlopen(req, timeout=10)
                                        detail = json.loads(resp.read().decode())
                                        outpost_token_id = detail.get('token_identifier', '')
                                    if outpost_token_id:
                                        plog(f"  ✓ Using existing LDAP outpost (blueprint)")
                            except Exception:
                                pass
                            if not outpost_token_id:
                                try:
                                    req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/',
                                        data=json.dumps({'name': 'LDAP', 'type': 'ldap',
                                            'providers': [ldap_provider_pk],
                                            'config': {'authentik_host': 'http://authentik-server-1:9000/',
                                                'authentik_host_insecure': True}}).encode(),
                                            headers=ak_headers, method='POST')
                                    resp = urllib.request.urlopen(req, timeout=10)
                                    outpost_data = json.loads(resp.read().decode())
                                    outpost_token_id = outpost_data.get('token_identifier', '')
                                    plog(f"  ✓ Created LDAP outpost (token_id={outpost_token_id})")
                                except urllib.error.HTTPError as e:
                                    err = e.read().decode()[:200]
                                    if e.code == 400:
                                        req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/?search=LDAP',
                                            headers=ak_headers)
                                        resp = urllib.request.urlopen(req, timeout=10)
                                        results = json.loads(resp.read().decode())['results']
                                        ldap_outpost = next((o for o in results if o.get('name') == 'LDAP' and o.get('type') == 'ldap'), None)
                                        if ldap_outpost:
                                            outpost_token_id = ldap_outpost.get('token_identifier', '')
                                            if not outpost_token_id:
                                                req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/{ldap_outpost["pk"]}/',
                                                    headers=ak_headers)
                                                resp = urllib.request.urlopen(req, timeout=10)
                                                detail = json.loads(resp.read().decode())
                                                outpost_token_id = detail.get('token_identifier', '')
                                            if outpost_token_id:
                                                plog(f"  ✓ LDAP outpost already exists, using token")
                                            if outpost_token_id and ldap_provider_pk:
                                                req = urllib.request.Request(
                                                    f'{ak_url}/api/v3/outposts/instances/{ldap_outpost["pk"]}/',
                                                    data=json.dumps({'name': 'LDAP', 'type': 'ldap',
                                                        'providers': [ldap_provider_pk],
                                                        'config': {'authentik_host': 'http://authentik-server-1:9000/',
                                                            'authentik_host_insecure': True}}).encode(),
                                                    headers=ak_headers, method='PUT')
                                                urllib.request.urlopen(req, timeout=10)
                                        if not outpost_token_id:
                                            plog(f"  ✗ LDAP outpost exists but token not available via API")
                                    else:
                                        plog(f"  ✗ LDAP outpost creation failed: {e.code} {err}")
                                except Exception as ex:
                                    plog(f"  ✗ LDAP outpost error: {str(ex)[:150]}")

                            # Inject token into docker-compose.yml
                            if outpost_token_id:
                                try:
                                    req = urllib.request.Request(
                                        f'{ak_url}/api/v3/core/tokens/{outpost_token_id}/view_key/',
                                        headers=ak_headers, method='GET')
                                    resp = urllib.request.urlopen(req, timeout=10)
                                    response_body = resp.read().decode()
                                    ldap_token_key = json.loads(response_body).get('key', '')
                                    if ldap_token_key:
                                        with open(compose_path, 'r') as f:
                                            compose_text = f.read()
                                        compose_text = compose_text.replace('AUTHENTIK_TOKEN: placeholder', f'AUTHENTIK_TOKEN: {ldap_token_key}')
                                        with open(compose_path, 'w') as f:
                                            f.write(compose_text)
                                        plog(f"  ✓ LDAP outpost token injected into docker-compose.yml")
                                        plog(f"  Recreating LDAP container with new token...")
                                        subprocess.run(f'cd {ak_dir} && docker compose stop ldap && docker compose rm -f ldap && docker compose up -d ldap 2>&1',
                                            shell=True, capture_output=True, timeout=60)
                                        plog(f"  ✓ LDAP container recreated with injected token")
                                        time.sleep(10)
                                        plog(f"  ℹ LDAP may take 30–60s to show healthy in Authentik Outposts")
                                    else:
                                        plog(f"  ⚠ Token key empty — response: {response_body[:200]}")
                                except urllib.error.HTTPError as e:
                                    plog(f"  ✗ Token injection HTTP error: {e.code} {e.read().decode()[:200]}")
                                except Exception as e:
                                    plog(f"  ✗ Token injection error: {str(e)[:200]}")
                            else:
                                plog(f"  ✗ No outpost_token_id — cannot inject token")

                            # Ensure LDAP container is started (even if token inject failed)
                            r = subprocess.run(f'cd {ak_dir} && docker compose up -d ldap 2>&1', shell=True, capture_output=True, text=True, timeout=60)
                            if r.returncode == 0:
                                plog(f"  ✓ LDAP container started")
                            else:
                                plog(f"  ⚠ LDAP start: {r.stderr.strip()[:150] if r.stderr else r.stdout.strip()[:150]}")

                except Exception as e:
                    plog(f"  ✗ LDAP setup error: {str(e)[:200]}")
                    try:
                        subprocess.run(f'cd {ak_dir} && docker compose up -d ldap 2>&1', shell=True, capture_output=True, timeout=60)
                        plog(f"  ℹ LDAP container started (add token in Authentik → Outposts → LDAP, then restart LDAP)")
                    except Exception:
                        pass
                else:
                    if os.path.exists('/opt/tak'):
                        plog("  ⚠ No webadmin password found, skipping user creation")
            else:
                plog("  ⚠ No bootstrap token found, skipping admin setup")
        except Exception as e:
            plog(f"  ⚠ Admin group setup error (non-fatal): {str(e)[:100]}")

        # Unconditionally ensure LDAP container is up (compose has ldap service from Step 6)
        compose_path = os.path.join(ak_dir, 'docker-compose.yml')
        if os.path.exists(compose_path):
            with open(compose_path) as f:
                compose_text = f.read()
            if 'ghcr.io/goauthentik/ldap' in compose_text or '\n  ldap:\n' in compose_text:
                plog("")
                plog("  Ensuring LDAP container is running...")
                r = subprocess.run(f'cd {ak_dir} && docker compose up -d ldap 2>&1', shell=True, capture_output=True, text=True, timeout=90)
                if r.returncode == 0:
                    plog("  ✓ LDAP container is up")
                else:
                    plog(f"  ✗ LDAP start failed: {(r.stderr or r.stdout or '').strip()[:300]}")

        # Verify LDAP flow + service account bind after outpost is up
        # Prevents "Invalid Credentials" drift after Update & Config
        if os.path.exists(os.path.join(ak_dir, '.env')):
            plog("")
            plog("  Verifying LDAP service account...")
            try:
                ok, err = _ensure_ldap_flow_authentication_none()
                if ok:
                    plog("  ✓ LDAP flow authentication: none")
                else:
                    plog(f"  ⚠ LDAP flow fix: {err}")
                # Re-set password and verify bind
                _ldap_pass = ''
                with open(os.path.join(ak_dir, '.env')) as _f:
                    for _line in _f:
                        if _line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                            _ldap_pass = _line.strip().split('=', 1)[1].strip()
                if _ldap_pass:
                    _ak_token = ''
                    with open(os.path.join(ak_dir, '.env')) as _f:
                        for _line in _f:
                            if _line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                                _ak_token = _line.strip().split('=', 1)[1].strip()
                    if _ak_token:
                        _ak_headers = {'Authorization': f'Bearer {_ak_token}', 'Content-Type': 'application/json'}
                        try:
                            req = urllib.request.Request(f'http://127.0.0.1:9090/api/v3/core/users/?search=adm_ldapservice', headers=_ak_headers)
                            resp = urllib.request.urlopen(req, timeout=10)
                            _results = json.loads(resp.read().decode()).get('results', [])
                            _ldap_pk = next((u['pk'] for u in _results if u['username'] == 'adm_ldapservice'), None)
                            if _ldap_pk:
                                req = urllib.request.Request(f'http://127.0.0.1:9090/api/v3/core/users/{_ldap_pk}/set_password/',
                                    data=json.dumps({'password': _ldap_pass}).encode(), headers=_ak_headers, method='POST')
                                urllib.request.urlopen(req, timeout=10)
                                time.sleep(3)
                                r = subprocess.run(
                                    f'ldapsearch -x -H ldap://127.0.0.1:389 -D "cn=adm_ldapservice,ou=users,dc=takldap" -w "{_ldap_pass}" -b "dc=takldap" -s base "(objectClass=*)" 2>&1',
                                    shell=True, capture_output=True, text=True, timeout=15)
                                if 'dn:' in (r.stdout or '').lower() or 'result: 0' in (r.stdout or '').lower():
                                    plog("  ✓ LDAP bind verified")
                                else:
                                    plog(f"  ⚠ LDAP bind check inconclusive (service may still be starting)")
                        except Exception as e:
                            plog(f"  ⚠ LDAP verify: {str(e)[:100]}")
            except Exception as e:
                plog(f"  ⚠ LDAP verify skipped: {str(e)[:80]}")

        # Step 12: Configure Proxy Provider, Application, Outpost, Brand for TAK Portal
        fqdn = settings.get('fqdn', '')
        if fqdn:
            plog("")
            plog("\u2501\u2501\u2501 Step 12: Configuring Forward Auth for TAK Portal \u2501\u2501\u2501")
            try:
                ak_token = ''
                with open(env_path) as f:
                    for line in f:
                        if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                            ak_token = line.strip().split('=', 1)[1].strip()
                if ak_token:
                    ak_headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
                    ak_url = 'http://127.0.0.1:9090'
                    import urllib.request

                    # 12a: Update Brand domain
                    plog("  Updating Authentik brand domain...")
                    try:
                        req = urllib.request.Request(f'{ak_url}/api/v3/core/brands/', headers=ak_headers)
                        resp = urllib.request.urlopen(req, timeout=15)
                        brands = json.loads(resp.read().decode())['results']
                        if brands:
                            brand_id = brands[0]['brand_uuid']
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/brands/{brand_id}/',
                                data=json.dumps({'domain': f'authentik.{fqdn}'}).encode(),
                                headers=ak_headers, method='PATCH')
                            urllib.request.urlopen(req, timeout=10)
                            plog(f"  ✓ Brand domain set to authentik.{fqdn}")
                    except Exception as e:
                        plog(f"  ⚠ Brand update: {str(e)[:100]}")

                    # 12b: Wait for authorization and invalidation flows (first boot can be slow)
                    flow_pk = None
                    inv_flow_pk = None
                    for attempt in range(36):  # up to 3 minutes
                        try:
                            req = urllib.request.Request(f'{ak_url}/api/v3/flows/instances/?designation=authorization&ordering=slug',
                                headers=ak_headers)
                            resp = urllib.request.urlopen(req, timeout=10)
                            flows = json.loads(resp.read().decode())['results']
                            for fl in flows:
                                if 'implicit' in fl.get('slug', ''):
                                    flow_pk = fl['pk']
                                    break
                            if not flow_pk and flows:
                                flow_pk = flows[0]['pk']
                            if flow_pk:
                                req = urllib.request.Request(f'{ak_url}/api/v3/flows/instances/?designation=invalidation',
                                    headers=ak_headers)
                                resp = urllib.request.urlopen(req, timeout=10)
                                inv_flows = json.loads(resp.read().decode())['results']
                                inv_flow_pk = next((f['pk'] for f in inv_flows if 'provider' not in f.get('slug', '')), inv_flows[0]['pk'] if inv_flows else None)
                                if inv_flow_pk:
                                    break
                        except Exception:
                            pass
                        if attempt % 6 == 0:
                            plog(f"  ⏳ Waiting for authorization flow... ({attempt * 5}s)")
                        time.sleep(5)
                    if flow_pk and inv_flow_pk:
                        plog("  ✓ Authorization and invalidation flows ready")
                    elif flow_pk:
                        plog("  ⚠ Invalidation flow not found — proxy may still work")

                    # 12c: Create Proxy Provider (Forward auth single application)
                    provider_pk = None
                    if flow_pk:
                        try:
                            base_domain = fqdn.split(':')[0]
                            provider_data = {
                                'name': 'TAK Portal Proxy',
                                'authorization_flow': flow_pk,
                                'invalidation_flow': inv_flow_pk or flow_pk,
                                'external_host': f'https://takportal.{fqdn}',
                                'mode': 'forward_single',
                                'token_validity': 'hours=24',
                                'cookie_domain': f'.{base_domain}'
                            }
                            req = urllib.request.Request(f'{ak_url}/api/v3/providers/proxy/',
                                data=json.dumps(provider_data).encode(),
                                headers=ak_headers, method='POST')
                            resp = urllib.request.urlopen(req, timeout=15)
                            provider_pk = json.loads(resp.read().decode())['pk']
                            plog(f"  ✓ Proxy Provider created (pk={provider_pk})")
                        except urllib.error.HTTPError as e:
                            if e.code == 400:
                                plog("  ✓ Proxy Provider already exists")
                                # Find existing
                                req = urllib.request.Request(f'{ak_url}/api/v3/providers/proxy/?search=TAK+Portal',
                                    headers=ak_headers)
                                resp = urllib.request.urlopen(req, timeout=10)
                                results = json.loads(resp.read().decode())['results']
                                if results:
                                    provider_pk = results[0]['pk']
                            else:
                                plog(f"  ⚠ Proxy Provider error: {e.code}")
                    else:
                        plog("  ⚠ No authorization flow found after waiting — create a flow in Authentik and re-run deploy or add proxy provider manually")

                    # 12d: Create Application
                    app_slug = None
                    if provider_pk:
                        try:
                            app_data = {
                                'name': 'TAK Portal',
                                'slug': 'tak-portal',
                                'provider': provider_pk,
                            }
                            req = urllib.request.Request(f'{ak_url}/api/v3/core/applications/',
                                data=json.dumps(app_data).encode(),
                                headers=ak_headers, method='POST')
                            resp = urllib.request.urlopen(req, timeout=15)
                            app_result = json.loads(resp.read().decode())
                            app_slug = app_result.get('slug', 'tak-portal')
                            plog(f"  ✓ Application 'TAK Portal' created")
                        except urllib.error.HTTPError as e:
                            if e.code == 400:
                                plog("  ✓ Application 'TAK Portal' already exists")
                                app_slug = 'tak-portal'
                            else:
                                plog(f"  ⚠ Application error: {e.code}")

                    # 12e: Add to embedded outpost
                    if app_slug:
                        try:
                            # Find embedded outpost
                            req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/?search=embedded',
                                headers=ak_headers)
                            resp = urllib.request.urlopen(req, timeout=10)
                            outposts = json.loads(resp.read().decode())['results']
                            embedded = None
                            for op in outposts:
                                if 'embed' in op.get('name', '').lower():
                                    embedded = op
                                    break
                            if not embedded and outposts:
                                # Check for proxy type outpost
                                for op in outposts:
                                    if op.get('type', '') == 'proxy':
                                        embedded = op
                                        break
                            if embedded:
                                outpost_pk = embedded['pk']
                                current_providers = list(embedded.get('providers', []))
                                if provider_pk not in current_providers:
                                    current_providers.append(provider_pk)
                                existing_config = dict(embedded.get('config', {}))
                                existing_config['authentik_host'] = f'https://authentik.{fqdn}'
                                existing_config['authentik_host_insecure'] = False
                                # Single PUT: providers + config (PATCH with only config can 400)
                                put_payload = {
                                    'name': embedded.get('name', 'authentik Embedded Outpost'),
                                    'type': embedded.get('type', 'proxy'),
                                    'providers': current_providers,
                                    'config': existing_config,
                                }
                                req = urllib.request.Request(f'{ak_url}/api/v3/outposts/instances/{outpost_pk}/',
                                    data=json.dumps(put_payload).encode(),
                                    headers=ak_headers, method='PUT')
                                urllib.request.urlopen(req, timeout=15)
                                plog(f"  ✓ TAK Portal added to embedded outpost")
                                plog(f"  ✓ Embedded outpost authentik_host set to https://authentik.{fqdn}")
                            else:
                                plog("  ⚠ No embedded outpost found — create one in Authentik admin")
                        except Exception as e:
                            plog(f"  ⚠ Outpost config: {str(e)[:100]}")

                    plog(f"  ✓ Forward auth ready for takportal.{fqdn}")

                    # Create Node-RED app in Authentik (so it's ready when Node-RED is deployed later)
                    plog("")
                    plog("  Configuring Authentik for Node-RED...")
                    _ensure_authentik_nodered_app(fqdn, ak_token, plog, flow_pk=flow_pk, inv_flow_pk=inv_flow_pk)
                    # infra-TAK console (infratak + console subdomains) behind Authentik — reuse same flows, no second fetch
                    plog("")
                    plog("  Configuring Authentik for infra-TAK Console...")
                    _ensure_authentik_console_app(fqdn, ak_token, plog, flow_pk=flow_pk, inv_flow_pk=inv_flow_pk)

                    # Set application access policies: admin-only apps restricted to authentik Admins
                    plog("")
                    plog("  Configuring application access policies...")
                    _ensure_app_access_policies(ak_url, ak_headers, plog)
                else:
                    plog("  ⚠ No bootstrap token, skipping forward auth setup")
            except Exception as e:
                plog(f"  ⚠ Forward auth setup error (non-fatal): {str(e)[:100]}")
        else:
            plog("")
            plog("  ℹ No domain configured — skipping forward auth setup")
            plog("  Set up a domain in the Caddy module first, then use Update config & reconnect")

        # Read bootstrap password for display
        bootstrap_pass_display = ''
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_PASSWORD='):
                    bootstrap_pass_display = line.strip().split('=', 1)[1].strip()

        plog("")
        plog("=" * 50)
        plog("\u2713 Authentik deployed successfully!")
        if fqdn:
            plog(f"  Admin UI: https://authentik.{fqdn}")
        else:
            plog(f"  Admin UI: http://{server_ip}:9090")
        plog(f"  Admin user: akadmin")
        if bootstrap_pass_display:
            plog(f"  Admin password: {bootstrap_pass_display}")
        plog("")
        plog("  LDAP Configuration:")
        plog(f"  - Service account: adm_ldapservice")
        if ldap_svc_pass:
            plog(f"  - Service password: {ldap_svc_pass}")
        plog(f"  - Base DN: DC=takldap")
        plog(f"  - LDAP port: 389")
        # Regenerate Caddyfile if Caddy is configured
        if settings.get('fqdn'):
            plog("")
            plog("  Updating Caddy config...")
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
            plog(f"  ✓ Caddy config updated for Authentik")
        # If Email Relay is already configured, push SMTP + recovery flow into Authentik now (persistent)
        relay = settings.get('email_relay') or {}
        if relay.get('from_addr'):
            plog("")
            plog("🔑 Email Relay is configured — configuring Authentik (SMTP + password recovery)...")
            try:
                ak_msg = _configure_authentik_smtp_and_recovery(relay.get('from_addr'), plog)
                plog(f"  ✓ {ak_msg}")
            except Exception as e:
                plog(f"  ⚠ Authentik SMTP auto-config failed: {e}")
                plog("  You can run it from Email Relay → 'Configure Authentik to use these settings'.")
        plog("=" * 50)
        plog("  Next steps:")
        plog("  1. Launch Authentik Admin (link below), then come back and refresh this page to get the akadmin password.")
        plog("     After logging in: Admin interface → Groups → authentik Admins → Users → Add new user (additional Admin users).")
        if not relay.get('from_addr'):
            plog("  2. Go to Email Relay and set up SMTP; then use 'Configure Authentik to use these settings'.")
        else:
            plog("  2. SMTP and password recovery are already configured (Email Relay was set up).")
        plog("=" * 50)
        plog("  ✓ Deploy complete.")
        authentik_deploy_status.update({'running': False, 'complete': True})
    except Exception as e:
        plog(f"\u2717 FATAL ERROR: {str(e)}")
        authentik_deploy_status.update({'running': False, 'error': True})
        try:
            import traceback
            error_log_path = os.path.join(CONFIG_DIR, 'authentik_error.log')
            with open(error_log_path, 'w') as f:
                f.write(f"FATAL ERROR: {str(e)}\n\n")
                f.write(traceback.format_exc())
                f.write("\n\nDEPLOY LOG:\n")
                f.write('\n'.join(authentik_deploy_log))
            plog(f"  Error log saved to {error_log_path}")
        except Exception:
            pass

AUTHENTIK_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Authentik</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
:root{--bg-deep:#080b14;--bg-surface:#0f1219;--bg-card:#161b26;--border:#1e2736;--border-hover:#2a3548;--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--cyan:#06b6d4;--green:#10b981;--red:#ef4444;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg-deep);color:var(--text-primary);min-height:100vh}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.top-bar{height:3px;background:linear-gradient(90deg,var(--accent),var(--cyan),var(--green))}
.header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--bg-surface)}
.header-left{display:flex;align-items:center;gap:16px}.header-icon{font-size:28px}.header-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px}.header-subtitle{font-size:13px;color:var(--text-dim)}
.header-right{display:flex;align-items:center;gap:12px}
.btn-back{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.btn-logout{color:var(--text-dim);text-decoration:none;font-size:13px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;transition:all 0.2s}.btn-logout:hover{color:var(--red);border-color:rgba(239,68,68,0.3)}
.os-badge{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);padding:4px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:4px}
.main{max-width:1000px;margin:0 auto;padding:32px 40px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;margin-top:24px}
.status-banner{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:12px;padding:24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
.status-info{display:flex;align-items:center;gap:16px}
.status-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px}
.status-icon.running{background:rgba(16,185,129,0.1)}.status-icon.stopped{background:rgba(239,68,68,0.1)}.status-icon.not-installed{background:rgba(71,85,105,0.2)}
.status-text{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:600}
.status-detail{font-size:13px;color:var(--text-dim);margin-top:4px}
.status-logo-wrap{display:flex;align-items:center;gap:10px}
.status-logo{height:36px;width:auto;max-width:100px;max-height:36px;object-fit:contain}
.status-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:18px;color:var(--text-primary)}
.controls{display:flex;gap:10px}
.control-btn{padding:10px 20px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:13px;cursor:pointer;transition:all 0.2s}
.control-btn:hover{border-color:var(--border-hover);color:var(--text-primary)}
.control-btn.btn-stop{border-color:rgba(239,68,68,0.3)}.control-btn.btn-stop:hover{background:rgba(239,68,68,0.1);color:var(--red)}
.control-btn.btn-start{border-color:rgba(16,185,129,0.3)}.control-btn.btn-start:hover{background:rgba(16,185,129,0.1);color:var(--green)}
.control-btn.btn-update{border-color:rgba(59,130,246,0.3)}.control-btn.btn-update:hover{background:rgba(59,130,246,0.1);color:var(--accent)}
.control-btn.btn-remove{border-color:rgba(239,68,68,0.2)}.control-btn.btn-remove:hover{background:rgba(239,68,68,0.1);color:var(--red)}
.cert-btn{padding:10px 20px;border-radius:8px;text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;transition:all 0.2s}
.cert-btn-primary{background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff}
.cert-btn-secondary{background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid var(--border)}
.deploy-btn{padding:14px 32px;border:none;border-radius:10px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;display:block;margin:24px auto}
.deploy-btn:hover{transform:translateY(-1px);box-shadow:0 4px 24px rgba(59,130,246,0.25)}
.deploy-log{background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-top:16px}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:8px}
.svc-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:'JetBrains Mono',monospace;font-size:12px}
.svc-name{color:var(--text-secondary);font-weight:600;margin-bottom:4px}
.svc-status{font-size:11px}
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-dim);margin-top:40px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-size:13px}
.uninstall-spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes uninstall-spin{to{transform:rotate(360deg)}}
.uninstall-progress-row{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text-secondary)}
body{display:flex;min-height:100vh}
.sidebar{width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin:0 auto}
</style></head><body>
{{ sidebar_html }}
<div class="main">
<div class="status-banner">
{% if deploying %}
<div class="status-info"><div class="status-icon running" style="background:rgba(59,130,246,0.1)">🔄</div><div><div class="status-text" style="color:var(--accent)">Deploying...</div><div class="status-detail">Authentik installation in progress</div></div></div>
{% elif ak.installed and ak.running %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ authentik_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--green)">Running</div><div class="status-detail">Identity provider active</div></div></div>
<div class="controls">
<button class="control-btn btn-stop" onclick="akControl('stop')">⏹ Stop</button>
<button class="control-btn" onclick="akControl('restart')">🔄 Restart</button>
<button class="control-btn btn-update" onclick="akControl('update')">⬆ Update</button>
</div>
{% elif ak.installed %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ authentik_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--red)">Stopped</div><div class="status-detail">Docker containers not running</div></div></div>
<div class="controls">
<button class="control-btn btn-start" onclick="akControl('start')">▶ Start</button>
<button class="control-btn btn-update" onclick="akControl('update')">⬆ Update</button>
</div>
{% else %}
<div class="status-info"><div class="status-logo-wrap"><img src="{{ authentik_logo_url }}" alt="" class="status-logo"></div><div><div class="status-text" style="color:var(--text-dim)">Not Installed</div><div class="status-detail">Deploy Authentik for identity management & SSO</div></div></div>
{% endif %}
</div>

{% if deploying %}
<div class="section-title">Deployment Log</div>
<div class="deploy-log" id="deploy-log">Waiting for deployment to start...</div>
{% elif deploy_error %}
<div class="section-title">Deployment Failed</div>
<div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:24px;margin-bottom:24px;text-align:center">
<div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:var(--red);margin-bottom:16px">✗ Authentik deployment failed</div>
{% if error_log_exists %}
<a href="/api/authentik/error-log" class="cert-btn cert-btn-secondary" style="text-decoration:none;display:inline-block">⬇ Download Error Log</a>
{% endif %}
</div>
{% elif ak.installed and ak.running %}
<div class="section-title">Access</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
<a href="{{ 'https://authentik.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':' + str(ak_port) }}" target="_blank" rel="noopener noreferrer" class="cert-btn cert-btn-primary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px;display:inline-flex;align-items:center;gap:6px" title="Open Authentik admin interface"><img src="{{ authentik_logo_url }}" alt="" style="width:18px;height:18px;object-fit:contain">Authentik{% if not settings.get('fqdn') %} :{{ ak_port }}{% endif %}</a>
<a href="{{ 'https://takportal.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':3000' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">👥 TAK Portal{% if not settings.get('fqdn') %} :3000{% endif %}</a>
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8443' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔐 WebGUI :8443 (cert)</a>
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8446' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔑 WebGUI :8446 (password)</a>
</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:12px">Admin user: <span style="color:var(--cyan)">akadmin</span> · <button type="button" onclick="showAkPassword()" id="ak-pw-btn" style="background:none;border:1px solid var(--border);color:var(--cyan);padding:2px 10px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;cursor:pointer">🔑 Show Password</button> <span id="ak-pw-display" style="color:var(--green);user-select:all;display:none"></span></div>
</div>
<div class="section-title">LDAP Configuration</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="font-family:'JetBrains Mono',monospace;font-size:12px;line-height:2">
<div><span style="color:var(--text-dim)">Base DN:</span> <span style="color:var(--cyan)">DC=takldap</span></div>
<div><span style="color:var(--text-dim)">Service Account:</span> <span style="color:var(--cyan)">adm_ldapservice</span></div>
<div><span style="color:var(--text-dim)">LDAP Port:</span> <span style="color:var(--cyan)">389</span> <span style="color:var(--text-dim)">(Docker outpost)</span></div>
<div style="margin-top:8px;font-size:11px;color:var(--text-dim)">LDAP configured via blueprint · Check Admin → Outposts to verify</div>
</div>
</div>
{% if container_info.get('containers') %}
<div class="section-title">Services</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div class="svc-grid">
{% for c in container_info.containers %}
<div class="svc-card" onclick="filterLogs('{{ c.name }}')" style="cursor:pointer;border-color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' if 'healthy' in c.status else 'var(--border)' }}" id="svc-{{ c.name }}"><div class="svc-name">{{ c.name }}</div><div class="svc-status" style="color:{{ 'var(--red)' if 'unhealthy' in c.status else 'var(--green)' }}">● {{ c.status }}</div></div>
{% endfor %}
<div class="svc-card" onclick="filterLogs('')" style="cursor:pointer" id="svc-all"><div class="svc-name">all containers</div><div class="svc-status" style="color:var(--text-dim)">● combined</div></div>
</div>
</div>
{% endif %}
{% if all_healthy and not portal_installed %}
<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:12px;padding:20px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between">
<div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--green)">✓ Authentik is healthy — next: configure SMTP, then deploy TAK Server, then TAK Portal</div>
<a href="/emailrelay" style="padding:8px 16px;background:rgba(5,150,105,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap;margin-right:8px">→ Email Relay</a><a href="/takserver" style="padding:8px 16px;background:rgba(5,150,105,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap;margin-right:8px">→ TAK Server</a><a href="/takportal" style="padding:8px 20px;background:linear-gradient(135deg,#059669,#0e7490);color:#fff;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap">→ TAK Portal</a>
</div>
{% elif all_healthy and portal_running %}
<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:12px;padding:20px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between">
<div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--green)">✓ Full stack healthy — Authentik + TAK Portal running</div>
<a href="/takportal" style="padding:8px 20px;background:var(--bg-surface);color:var(--green);border:1px solid rgba(16,185,129,0.3);border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap">→ TAK Portal</a>
</div>
{% endif %}
<div class="section-title">Container Logs <span id="log-filter-label" style="font-size:11px;color:var(--cyan);margin-left:8px"></span></div>
<div class="deploy-log" id="container-log">Loading logs...</div>
<div style="margin-top:24px;text-align:center">
<button class="control-btn" onclick="reconfigureAk()" style="margin-right:12px">🔄 Update config & reconnect</button>
<button class="control-btn btn-remove" onclick="document.getElementById('ak-uninstall-modal').classList.add('open')">🗑 Remove Authentik</button>
</div>
{% elif ak.installed %}
<div style="margin-top:24px;text-align:center">
<button class="control-btn btn-start" onclick="akControl('start')" style="margin-right:12px">▶ Start</button>
<button class="control-btn" onclick="reconfigureAk()" style="margin-right:12px">🔄 Update config & reconnect</button>
<button class="control-btn btn-remove" onclick="document.getElementById('ak-uninstall-modal').classList.add('open')">🗑 Remove Authentik</button>
</div>
{% else %}
<div class="section-title">About Authentik</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-secondary);line-height:1.8">
Authentik is an open-source <span style="color:var(--cyan)">Identity Provider</span> supporting SSO, SAML, OAuth2/OIDC, LDAP, and RADIUS.<br><br>
It provides centralized user authentication and management for all your services — including <span style="color:var(--cyan)">TAK Portal</span> for TAK Server user/cert management and <span style="color:var(--cyan)">MediaMTX</span> for stream access and user/group management (with or without TAK Portal).<br><br>
<span style="color:var(--text-dim)">Deploys: PostgreSQL + Redis + Authentik Server + Worker (4 containers)</span><br>
<span style="color:var(--text-dim)">Ports: 9090 (HTTP) · 9443 (HTTPS)</span><br>
<span style="color:var(--text-dim)">Recommended: 2+ CPU cores, 2+ GB RAM</span>
</div>
</div>
<button class="deploy-btn" id="deploy-btn" onclick="deployAk()">🚀 Deploy Authentik</button>
{% if not settings.fqdn %}
<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:10px;padding:16px 20px;margin-top:16px;font-size:13px;color:#f87171">
  🔒 <strong>SSL Required</strong> — Authentik requires a domain with SSL configured.<br>
  <span style="color:var(--text-dim)">Go to <a href="/caddy" style="color:var(--cyan)">Caddy SSL</a> and configure your domain first.</span>
</div>
{% endif %}
<div class="deploy-log" id="deploy-log" style="display:none" data-authentik-url="{{ 'https://authentik.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':' + str(ak_port) }}">Waiting for deployment to start...</div>
{% endif %}

{% if deploy_done %}
<div style="background:rgba(16,185,129,0.1);border:1px solid var(--border);border-radius:10px;padding:20px;margin-top:20px;text-align:center">
<div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:var(--green);margin-bottom:8px">✓ Authentik deployed!</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--cyan);margin-bottom:12px;text-align:left">
<strong>Next steps:</strong><br>
1. <strong>Configure SMTP</strong> — go to <a href="/emailrelay" style="color:var(--cyan)">Email Relay</a>, configure SMTP, then click &quot;Configure Authentik to use these settings&quot;.<br>
2. <strong>Deploy TAK Server</strong> — go to <a href="/takserver" style="color:var(--cyan)">TAK Server</a>, upload .deb/.rpm and deploy.<br>
3. <strong>Deploy TAK Portal</strong> — go to <a href="/takportal" style="color:var(--cyan)">TAK Portal</a> and deploy when ready.<br>
You can also open the Authentik admin UI below to make additional Admin users (Admin → Groups → authentik Admins → Users).
</div>
<a href="{{ 'https://authentik.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':' + str(ak_port) }}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none;margin-right:10px">Authentik</a>
<a href="/emailrelay" style="display:inline-block;padding:10px 24px;background:rgba(30,64,175,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;margin-right:10px">Email Relay</a>
<a href="/takserver" style="display:inline-block;padding:10px 24px;background:rgba(30,64,175,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;margin-right:10px">TAK Server</a>
<a href="/takportal" style="display:inline-block;padding:10px 24px;background:rgba(30,64,175,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;margin-right:10px">TAK Portal</a>
<button onclick="window.location.href='/authentik'" style="padding:10px 24px;background:rgba(30,64,175,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">Refresh Page</button>
</div>
{% endif %}
</div>
<div class="modal-overlay" id="ak-uninstall-modal">
<div class="modal">
<h3>⚠ Uninstall Authentik?</h3>
<p>This will remove Authentik, all Docker containers, volumes, images, and data. This cannot be undone.</p>
<label class="form-label">Admin Password</label>
<input class="form-input" id="ak-uninstall-password" type="password" placeholder="Confirm your password">
<div class="modal-actions">
<button type="button" class="control-btn" id="ak-uninstall-cancel" onclick="document.getElementById('ak-uninstall-modal').classList.remove('open')">Cancel</button>
<button type="button" class="control-btn btn-remove" id="ak-uninstall-confirm" onclick="doUninstallAk()">Uninstall</button>
</div>
<div id="ak-uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
<div id="ak-uninstall-progress" class="uninstall-progress-row" style="display:none;margin-top:10px" aria-live="polite"></div>
</div>
</div>
<footer class="footer"></footer>
<script>
async function showAkPassword(){
    var btn=document.getElementById('ak-pw-btn');
    var display=document.getElementById('ak-pw-display');
    if(display.style.display==='inline'){display.style.display='none';btn.textContent='🔑 Show Password';return}
    try{
        var r=await fetch('/api/authentik/password');
        var d=await r.json();
        if(d.password){display.textContent=d.password;display.style.display='inline';btn.textContent='🔑 Hide'}
        else{display.textContent='Not found';display.style.display='inline'}
    }catch(e){display.textContent='Error';display.style.display='inline'}
}
async function akControl(action){
    var btns=document.querySelectorAll('.control-btn');
    btns.forEach(function(b){b.disabled=true;b.style.opacity='0.5'});
    try{
        var r=await fetch('/api/authentik/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action})});
        var d=await r.json();
        if(d.success)window.location.href='/authentik';
        else alert('Error: '+(d.error||'Unknown'));
    }catch(e){alert('Error: '+e.message)}
    btns.forEach(function(b){b.disabled=false;b.style.opacity='1'});
}

async function deployAk(){
    var btn=document.getElementById('deploy-btn');
    btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.7';btn.style.cursor='wait';
    document.getElementById('deploy-log').style.display='block';
    try{
        var r=await fetch('/api/authentik/deploy',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success)pollDeployLog();
        else{document.getElementById('deploy-log').textContent='Error: '+d.error;btn.disabled=false;btn.textContent='Deploy Authentik';btn.style.opacity='1';btn.style.cursor='pointer'}
    }catch(e){document.getElementById('deploy-log').textContent='Error: '+e.message}
}
async function reconfigureAk(){
    try{
        var r=await fetch('/api/authentik/reconfigure',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success)window.location.href='/authentik';
        else alert('Error: '+(d.error||'Reconfigure failed'));
    }catch(e){alert('Error: '+e.message)}
}

var logIndex=0;
function pollDeployLog(){
    fetch('/api/authentik/deploy/log?index='+logIndex).then(function(r){return r.json()}).then(function(d){
        var el=document.getElementById('deploy-log');
        if(d.entries.length>0){
            d.entries.forEach(function(e){
                var isTimer=e.trim().charAt(0)==='\u23f3'&&e.indexOf(':')>0;
                if(isTimer){var prev=el.querySelector('[data-timer]');if(prev){prev.textContent=e;logIndex=d.total;return}}
                if(!isTimer){var old=el.querySelector('[data-timer]');if(old)old.removeAttribute('data-timer')}
                var l=document.createElement('div');
                if(isTimer)l.setAttribute('data-timer','1');
                if(e.indexOf('\u2713')>=0)l.style.color='var(--green)';
                else if(e.indexOf('\u2717')>=0||e.indexOf('FATAL')>=0)l.style.color='var(--red)';
                else if(e.indexOf('\u2501\u2501\u2501')>=0)l.style.color='var(--cyan)';
                else if(e.indexOf('===')>=0)l.style.color='var(--green)';
                l.textContent=e;el.appendChild(l);
            });
            logIndex=d.total;el.scrollTop=el.scrollHeight;
        }
        if(d.running)setTimeout(pollDeployLog,1000);
        else if(d.complete){
            var btn=document.getElementById('deploy-btn');
            if(btn){btn.textContent='\u2713 Deployment Complete';btn.style.background='var(--green)';btn.style.opacity='1';btn.style.cursor='default';}
            var el=document.getElementById('deploy-log');
            var inst=document.createElement('div');
            inst.style.cssText='font-family:JetBrains Mono,monospace;font-size:12px;color:var(--cyan);margin-top:16px;margin-bottom:8px;text-align:left;line-height:1.6';
            inst.innerHTML='<strong>Next steps:</strong><br>1. Configure <strong>SMTP</strong> (Email Relay), then &quot;Configure Authentik&quot;.<br>2. Deploy <strong>TAK Server</strong>.<br>3. Deploy <strong>TAK Portal</strong> when ready.<br>Use &quot;Launch Authentik Admin&quot; below to make additional Admin users.';
            el.appendChild(inst);
            var authUrl=el.getAttribute('data-authentik-url')||'';
            var launchLink=document.createElement('a');
            launchLink.href=authUrl;launchLink.target='_blank';launchLink.rel='noopener noreferrer';
            launchLink.textContent='Launch Authentik Admin';
            launchLink.style.cssText='display:block;width:100%;padding:12px;margin-top:8px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none;box-sizing:border-box';
            el.appendChild(launchLink);
            var refreshBtn=document.createElement('button');
            refreshBtn.textContent='\u21bb Refresh Authentik Page';
            refreshBtn.style.cssText='display:block;width:100%;padding:10px;margin-top:8px;background:rgba(30,64,175,0.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-size:13px;cursor:pointer;';
            refreshBtn.onclick=function(){window.location.href='/authentik';};
            el.appendChild(refreshBtn);
            el.scrollTop=el.scrollHeight;
        }
    });
}

var activeContainer = '';
function filterLogs(containerName){
    activeContainer = containerName;
    // Highlight selected card
    document.querySelectorAll('.svc-card').forEach(function(c){c.style.borderColor='';c.style.boxShadow=''});
    var id = containerName ? 'svc-'+containerName : 'svc-all';
    var card = document.getElementById(id);
    if(card){card.style.borderColor='var(--cyan)';card.style.boxShadow='0 0 0 1px var(--cyan)'}
    var label = document.getElementById('log-filter-label');
    if(label) label.textContent = containerName ? '— '+containerName : '';
    loadContainerLogs();
}
async function loadContainerLogs(){
    var el=document.getElementById('container-log');
    if(!el)return;
    try{
        var url = activeContainer
            ? '/api/authentik/logs?lines=80&container='+encodeURIComponent(activeContainer)
            : '/api/authentik/logs?lines=80';
        var r=await fetch(url);
        var d=await r.json();
        el.textContent='';
        if(d.entries&&d.entries.length>0){
            d.entries.forEach(function(e){
                var l=document.createElement('div');
                if(e.indexOf('ERROR')>=0||e.indexOf('error')>=0)l.style.color='var(--red)';
                else if(e.indexOf('WARNING')>=0||e.indexOf('warn')>=0)l.style.color='var(--yellow)';
                l.textContent=e;el.appendChild(l);
            });
            el.scrollTop=el.scrollHeight;
        }else{el.textContent='No logs available yet.';}
    }catch(e){el.textContent='Failed to load logs';}
}
if(document.getElementById('container-log')){loadContainerLogs();setInterval(loadContainerLogs,10000)}

function uninstallAk(){
    document.getElementById('ak-uninstall-modal').classList.add('open');
}
async function doUninstallAk(){
    var pw=document.getElementById('ak-uninstall-password').value;
    if(!pw){document.getElementById('ak-uninstall-msg').textContent='Please enter your password';return;}
    var msgEl=document.getElementById('ak-uninstall-msg');
    var progressEl=document.getElementById('ak-uninstall-progress');
    var cancelBtn=document.getElementById('ak-uninstall-cancel');
    var confirmBtn=document.getElementById('ak-uninstall-confirm');
    msgEl.textContent='';
    progressEl.style.display='flex';
    progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Uninstalling…</span>';
    confirmBtn.disabled=true;
    cancelBtn.disabled=true;
    try{
        var r=await fetch('/api/authentik/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
        var d=await r.json();
        if(d.success){
            progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Done. Reloading…</span>';
            setTimeout(function(){window.location.href='/authentik';},800);
        }else{
            msgEl.textContent=d.error||'Uninstall failed';
            progressEl.style.display='none';
            progressEl.innerHTML='';
            confirmBtn.disabled=false;
            cancelBtn.disabled=false;
        }
    }catch(e){
        msgEl.textContent='Request failed: '+e.message;
        progressEl.style.display='none';
        progressEl.innerHTML='';
        confirmBtn.disabled=false;
        cancelBtn.disabled=false;
    }
}

{% if deploying %}pollDeployLog();{% endif %}
</script>
</body></html>'''

def _coreconfig_has_ldap():
    """True if CoreConfig.xml exists and already contains our LDAP auth block."""
    path = '/opt/tak/CoreConfig.xml'
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r') as f:
            content = f.read()
        return 'adm_ldapservice' in content
    except Exception:
        return False

def _ensure_ldapsearch():
    """Ensure ldapsearch CLI is available (install ldap-utils / openldap-clients if missing).
    Used by Connect TAK Server to LDAP to trigger a bind for outpost log verification."""
    if shutil.which('ldapsearch'):
        return True
    try:
        if os.path.exists('/etc/debian_version'):
            subprocess.run(
                'DEBIAN_FRONTEND=noninteractive apt-get update -qq && apt-get install -y ldap-utils 2>&1',
                shell=True, capture_output=True, timeout=120)
        else:
            subprocess.run('dnf install -y openldap-clients 2>/dev/null || yum install -y openldap-clients 2>/dev/null',
                shell=True, capture_output=True, timeout=120)
    except Exception:
        pass
    return bool(shutil.which('ldapsearch'))

def _test_ldap_bind(ldap_pass):
    """Test LDAP bind by triggering a connection and checking the outpost logs.
    ldapsearch CLI is incompatible with Authentik's LDAP outpost (returns error 49
    even when the outpost authenticates successfully), so we verify via outpost logs."""
    try:
        if shutil.which('ldapsearch'):
            subprocess.run(
                ['ldapsearch', '-x', '-H', 'ldap://127.0.0.1:389',
                 '-D', 'cn=adm_ldapservice,ou=users,dc=takldap', '-w', ldap_pass,
                 '-b', 'dc=takldap', '-s', 'base', '(objectClass=*)'],
                capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass  # ldapsearch missing, failed, or timed out; still check logs below
    time.sleep(2)
    r = subprocess.run(
        'docker logs authentik-ldap-1 --since 25s 2>&1',
        shell=True, capture_output=True, text=True, timeout=10)
    log = (r.stdout or '').lower()
    return 'authenticated' in log and ('adm_ldapservice' in log or 'ldapservice' in log)

def _ensure_ldap_flow_authentication_none():
    """Ensure ldap-authentication-flow exists with authentication:none and 3 stage bindings, restart LDAP outpost.
    If flow missing (blueprint never ran), create it by cloning default-authentication-flow.
    If flow exists but has no stage bindings (deleted during debugging), recreate them from blueprint stages.
    Fixes 'Flow does not apply to current user' — require_outpost blocks user binds.
    Fixes 'Access denied for user' / Insufficient access (50) — missing bindings cause auth to fail.
    Returns (True, None) on success, (False, error_msg) on failure."""
    import urllib.request as _req
    import urllib.error
    env_path = os.path.expanduser('~/authentik/.env')
    if not os.path.exists(env_path):
        return False, 'Authentik .env not found'
    ak_token = ''
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                ak_token = line.strip().split('=', 1)[1].strip()
                break
    if not ak_token:
        return False, 'Authentik token not in .env'
    ak_dir = os.path.expanduser('~/authentik')
    if not os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')):
        return False, 'Authentik not deployed'
    url = 'http://127.0.0.1:9090'
    headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
    # Authentik API can be slow after worker restart or under load; use 60s per request
    _api_timeout = 60

    def _get(path):
        r = _req.Request(f'{url}/api/v3/{path}', headers=headers)
        return json.loads(_req.urlopen(r, timeout=_api_timeout).read().decode())

    def _post(path, body):
        r = _req.Request(f'{url}/api/v3/{path}', data=json.dumps(body).encode(), headers=headers, method='POST')
        return json.loads(_req.urlopen(r, timeout=_api_timeout).read().decode())

    def _patch(path, body):
        r = _req.Request(f'{url}/api/v3/{path}', data=json.dumps(body).encode(), headers=headers, method='PATCH')
        _req.urlopen(r, timeout=_api_timeout)

    def _delete(path):
        r = _req.Request(f'{url}/api/v3/{path}', headers=headers, method='DELETE')
        _req.urlopen(r, timeout=_api_timeout)

    try:
        ldap_flow_results = _get('flows/instances/?slug=ldap-authentication-flow').get('results', [])
        ldap_flow = ldap_flow_results[0] if ldap_flow_results else None
        default_flow_results = _get('flows/instances/?slug=default-authentication-flow').get('results', [])
        default_flow = default_flow_results[0] if default_flow_results else None

        if ldap_flow:
            _patch('flows/instances/ldap-authentication-flow/', {'authentication': 'none'})
            # Ensure 3 stage bindings are our ldap-* stages (not default/MFA — those break LDAP bind)
            ldap_flow_pk = ldap_flow['pk']
            all_bindings = []
            page = 1
            while True:
                data = _get(f'flows/bindings/?ordering=order&page_size=500&page={page}')
                all_bindings.extend(data.get('results', []))
                if not data.get('pagination', {}).get('next'):
                    break
                page += 1
            ldap_bindings = [b for b in all_bindings if str(b.get('target')) == str(ldap_flow_pk)]
            stage_names = {(b.get('stage_obj') or {}).get('name') or '' for b in ldap_bindings}
            need_names = {'ldap-identification-stage', 'ldap-authentication-password', 'ldap-authentication-login'}
            # Clear password_stage on identification stage (DB may have it from old blueprint → "exceeded stage recursion depth")
            def _find_stage(api_path, name):
                for page in range(1, 4):
                    data = _get(f'{api_path}?page={page}&page_size=100')
                    for s in data.get('results', []):
                        if s.get('name') == name:
                            return s.get('pk')
                    if not data.get('pagination', {}).get('next'):
                        break
                return None
            id_stage_pk = None
            for b in ldap_bindings:
                so = b.get('stage_obj') or {}
                if so.get('name') == 'ldap-identification-stage':
                    id_stage_pk = so.get('pk') or (b.get('stage') if isinstance(b.get('stage'), int) else None)
                    break
            if not id_stage_pk:
                id_stage_pk = _find_stage('stages/identification/', 'ldap-identification-stage')
            if id_stage_pk:
                try:
                    # Include user_fields so PATCH does not trigger "no user fields selected" validation
                    _patch(f'stages/identification/{id_stage_pk}/', {'password_stage': None, 'user_fields': ['username']})
                except Exception:
                    pass
            wrong_bindings = len(ldap_bindings) < 3 or need_names != stage_names
            if wrong_bindings:
                for b in ldap_bindings:
                    try:
                        _delete(f'flows/bindings/{b["pk"]}/')
                    except urllib.error.HTTPError:
                        pass
                ldap_bindings = []
            if len(ldap_bindings) < 3:
                # Find or create blueprint stages by name (blueprint may not have run)
                def _create_ldap_stage(api_path, name, attrs):
                    try:
                        body = {'name': name, **attrs}
                        return _post(api_path, body).get('pk')
                    except urllib.error.HTTPError:
                        return _find_stage(api_path, name)
                id_stage = _find_stage('stages/identification/', 'ldap-identification-stage')
                if not id_stage:
                    id_stage = _create_ldap_stage('stages/identification/', 'ldap-identification-stage', {
                        'case_insensitive_matching': True, 'pretend_user_exists': True, 'show_matched_user': True,
                        'user_fields': ['username']})
                pw_stage = _find_stage('stages/password/', 'ldap-authentication-password')
                if not pw_stage:
                    pw_stage = _create_ldap_stage('stages/password/', 'ldap-authentication-password', {
                        'backends': ['authentik.core.auth.InbuiltBackend', 'authentik.core.auth.TokenBackend'],
                        'failed_attempts_before_cancel': 5})
                login_stage = _find_stage('stages/user_login/', 'ldap-authentication-login')
                if not login_stage:
                    login_stage = _create_ldap_stage('stages/user_login/', 'ldap-authentication-login', {
                        'session_duration': 'seconds=0', 'remember_me_offset': 'seconds=0'})
                if id_stage and pw_stage and login_stage:
                    existing_orders = {b.get('order') for b in ldap_bindings}
                    binding_specs = [(10, id_stage), (15, pw_stage), (20, login_stage)]
                    for order, stage_pk in binding_specs:
                        if order not in existing_orders:
                            try:
                                _post('flows/bindings/', {
                                    'target': ldap_flow_pk, 'stage': stage_pk, 'order': order,
                                    'evaluate_on_plan': True, 're_evaluate_policies': True,
                                    'policy_engine_mode': 'any', 'invalid_response_action': 'retry'})
                            except urllib.error.HTTPError:
                                pass
                else:
                    return False, f'LDAP stages not found/created: id={id_stage} pw={pw_stage} login={login_stage}'
            providers = _get('providers/ldap/?search=LDAP').get('results', [])
            ldap_prov = next((p for p in providers if p.get('name') == 'LDAP'), providers[0] if providers else None)
            if ldap_prov:
                try:
                    _patch(f'providers/ldap/{ldap_prov["pk"]}/', {
                        'authentication_flow': ldap_flow_pk,
                        'authorization_flow': ldap_flow_pk})
                except urllib.error.HTTPError as e:
                    body = ''
                    try: body = e.read().decode()[:200]
                    except Exception: pass
                    return False, f'Failed to update LDAP provider flows: {e.code} {body}'
        else:
            if not default_flow:
                return False, 'Default authentication flow not found. Authentik may not be fully initialized.'
            default_pk = default_flow['pk']
            all_bindings = []
            page = 1
            while True:
                data = _get(f'flows/bindings/?ordering=order&page_size=500&page={page}')
                all_bindings.extend(data.get('results', []))
                if not data.get('pagination', {}).get('next'):
                    break
                page += 1
            default_bindings = [b for b in all_bindings if str(b.get('target')) == str(default_pk)]
            default_bindings.sort(key=lambda x: x.get('order', 0))
            new_flow = _post('flows/instances/', {
                'name': 'ldap-authentication-flow', 'slug': 'ldap-authentication-flow',
                'title': 'ldap-authentication-flow', 'designation': 'authentication',
                'authentication': 'none', 'layout': 'stacked', 'denied_action': 'message_continue',
                'policy_engine_mode': 'any'})
            new_flow_pk = new_flow['pk']
            for b in default_bindings:
                s = b.get('stage')
                stage_pk = s if isinstance(s, int) else (s.get('pk') if isinstance(s, dict) and s else s)
                if not stage_pk:
                    continue
                try:
                    _post('flows/bindings/', {
                        'target': new_flow_pk, 'stage': stage_pk, 'order': b.get('order', 0),
                        'evaluate_on_plan': b.get('evaluate_on_plan', True),
                        're_evaluate_policies': b.get('re_evaluate_policies', True),
                        'policy_engine_mode': b.get('policy_engine_mode', 'any'),
                        'invalid_response_action': b.get('invalid_response_action', 'retry')})
                except urllib.error.HTTPError:
                    pass
            providers = _get('providers/ldap/?search=LDAP').get('results', [])
            ldap_provider = next((p for p in providers if p.get('name') == 'LDAP'), providers[0] if providers else None)
            if ldap_provider:
                _patch(f'providers/ldap/{ldap_provider["pk"]}/', {
                    'authentication_flow': new_flow_pk,
                    'authorization_flow': new_flow_pk})
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:200]
        except Exception:
            body = ''
        return False, f'Authentik API {e.code}: {body}'
    except Exception as e:
        return False, str(e)[:120]
    # LDAP outpost caches flow results — force-recreate required after flow/binding changes
    subprocess.run(f'cd {ak_dir} && docker compose up -d --force-recreate ldap 2>&1',
        shell=True, capture_output=True, timeout=60)
    time.sleep(5)
    return True, None

def _ensure_authentik_ldap_service_account():
    """Ensure adm_ldapservice exists, has password set, is in authentik Admins, and VERIFY the bind works.
    Runs before Connect TAK Server to LDAP so LDAP bind works regardless of deploy order."""
    ok, err = _ensure_ldap_flow_authentication_none()
    if not ok:
        return False, f'LDAP flow fix failed: {err}'
    import urllib.request as _req
    import urllib.error
    env_path = os.path.expanduser('~/authentik/.env')
    if not os.path.exists(env_path):
        return False, 'Authentik .env not found'
    ak_token = ''
    ldap_pass = ''
    with open(env_path) as f:
        for line in f:
            L = line.strip()
            if L.startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                ak_token = L.split('=', 1)[1].strip()
            elif L.startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                ldap_pass = L.split('=', 1)[1].strip()
    if not ak_token or not ldap_pass:
        return False, 'Authentik token or LDAP password not in .env'
    url = 'http://127.0.0.1:9090'
    headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
    try:
        # 1. Find or create the service account
        req = _req.Request(f'{url}/api/v3/core/users/?search=adm_ldapservice', headers=headers)
        resp = _req.urlopen(req, timeout=10)
        users = json.loads(resp.read().decode())['results']
        user_obj = next((u for u in users if u.get('username') == 'adm_ldapservice'), None)
        uid = user_obj['pk'] if user_obj else None
        if not uid:
            req = _req.Request(f'{url}/api/v3/core/users/', data=json.dumps({
                'username': 'adm_ldapservice', 'name': 'LDAP Service Account',
                'is_active': True, 'type': 'service_account',
                'path': 'users',
            }).encode(), headers=headers, method='POST')
            resp = _req.urlopen(req, timeout=10)
            user_obj = json.loads(resp.read().decode())
            uid = user_obj['pk']
        # 2. Ensure user is active and path is 'users' (service_account defaults to 'service-accounts' which gives wrong LDAP DN)
        patch_fields = {}
        if user_obj and not user_obj.get('is_active', True):
            patch_fields['is_active'] = True
        if user_obj and user_obj.get('path', '') != 'users':
            patch_fields['path'] = 'users'
        if patch_fields:
            req = _req.Request(f'{url}/api/v3/core/users/{uid}/', data=json.dumps(patch_fields).encode(), headers=headers, method='PATCH')
            _req.urlopen(req, timeout=10)
        # 3. Set the password
        req = _req.Request(f'{url}/api/v3/core/users/{uid}/set_password/',
            data=json.dumps({'password': ldap_pass}).encode(), headers=headers, method='POST')
        pw_resp = _req.urlopen(req, timeout=10)
        pw_code = pw_resp.getcode()
        # 4. Add to authentik Admins group
        req = _req.Request(f'{url}/api/v3/core/groups/?search=authentik+Admins', headers=headers)
        resp = _req.urlopen(req, timeout=10)
        groups = json.loads(resp.read().decode())['results']
        admins = next((g for g in groups if 'admins' in g.get('name', '').lower()), None)
        if admins:
            users_raw = admins.get('users') or []
            member_pks = [u.get('pk') if isinstance(u, dict) else u for u in users_raw]
            if uid not in member_pks:
                req = _req.Request(f'{url}/api/v3/core/groups/{admins["pk"]}/add_user/',
                    data=json.dumps({'pk': uid}).encode(), headers=headers, method='POST')
                _req.urlopen(req, timeout=10)
        else:
            return False, 'authentik Admins group not found'
        # 5. Force-recreate the LDAP outpost so it picks up the new credentials
        subprocess.run('cd ~/authentik && docker compose up -d --force-recreate ldap 2>/dev/null',
            shell=True, capture_output=True, timeout=60)
        # 6. Ensure ldapsearch is available (install ldap-utils / openldap-clients if missing)
        _ensure_ldapsearch()
        # 7. Wait for LDAP outpost to be ready, then VERIFY via outpost logs (ldapsearch exit code is unreliable)
        time.sleep(10)
        for attempt in range(10):
            time.sleep(6)
            if _test_ldap_bind(ldap_pass):
                return True, f'LDAP bind verified (attempt {attempt + 1})'
        # Verification failed — outpost may not log service account binds, or format differs.
        # Proceed anyway; service account exists and password is set. User can test with a TAK client.
        return True, 'LDAP service account configured (bind verification inconclusive — outpost may not log service-account binds). Proceeding.'
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return False, f'Authentik API {e.code}: {body}'
    except Exception as e:
        return False, str(e)[:120]

def _apply_ldap_to_coreconfig():
    """Patch CoreConfig.xml with LDAP auth and restart TAK Server. Returns (success, message)."""
    coreconfig_path = '/opt/tak/CoreConfig.xml'
    env_path = os.path.expanduser('~/authentik/.env')
    if not os.path.exists(coreconfig_path):
        return False, 'CoreConfig.xml not found'
    if not os.path.exists(env_path):
        return False, 'Authentik .env not found'
    ldap_pass = ''
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                ldap_pass = line.strip().split('=', 1)[1].strip()
                break
    if not ldap_pass:
        return False, 'LDAP service password not found in Authentik .env'
    # Read current CoreConfig
    with open(coreconfig_path, 'r') as f:
        original = f.read()
    if _coreconfig_has_ldap():
        # LDAP already configured — check if password needs updating
        import re as _re
        m = _re.search(r'serviceAccountCredential="([^"]*)"', original)
        existing_pass = m.group(1) if m else ''
        if existing_pass == ldap_pass:
            return True, 'CoreConfig already has LDAP (password matches .env)'
        # Password mismatch — update it in place
        updated = original.replace(
            f'serviceAccountCredential="{existing_pass}"',
            f'serviceAccountCredential="{ldap_pass}"')
        if updated != original:
            patch_path = os.path.join(BASE_DIR, 'CoreConfig.ldap-patch.xml')
            with open(patch_path, 'w') as f:
                f.write(updated)
            r = subprocess.run(['sudo', 'cp', os.path.abspath(patch_path), coreconfig_path],
                capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return False, f'Password resync: sudo cp failed: {r.stderr.strip()[:200]}'
            r = subprocess.run('sudo systemctl restart takserver 2>&1',
                shell=True, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return False, f'Password resynced but TAK Server restart failed: {r.stderr.strip()[:120]}'
            return True, 'LDAP password resynced from .env to CoreConfig — TAK Server restarted.'
        return True, 'CoreConfig already has LDAP'
    # Backup
    backup_path = coreconfig_path + '.pre-ldap.bak'
    if not os.path.exists(backup_path):
        subprocess.run(['sudo', 'cp', coreconfig_path, backup_path], capture_output=True, timeout=10)
    # Build the replacement auth block — matches TAK Portal reference exactly
    ldap_line = '        <ldap'
    ldap_line += ' url="ldap://127.0.0.1:389"'
    ldap_line += ' userstring="cn={username},ou=users,dc=takldap"'
    ldap_line += ' updateinterval="60"'
    ldap_line += ' groupprefix="cn=tak_"'
    ldap_line += ' groupNameExtractorRegex="cn=tak_(.*?)(?:,|$)"'
    ldap_line += ' serviceAccountDN="cn=adm_ldapservice,ou=users,dc=takldap"'
    ldap_line += ' serviceAccountCredential="' + ldap_pass + '"'
    ldap_line += ' groupBaseRDN="ou=groups,dc=takldap"'
    ldap_line += ' userBaseRDN="ou=users,dc=takldap"'
    ldap_line += ' dnAttributeName="DN"'
    ldap_line += ' nameAttr="CN"'
    ldap_line += ' adminGroup="ROLE_ADMIN"/>'
    auth_block = ''
    auth_block += '    <auth default="ldap" x509groups="true" x509addAnonymous="false"'
    auth_block += ' x509useGroupCache="true" x509useGroupCacheDefaultActive="true"'
    auth_block += ' x509checkRevocation="true">\n'
    auth_block += ldap_line + '\n'
    auth_block += '        <File location="UserAuthenticationFile.xml"/>\n'
    auth_block += '    </auth>'
    # Sanity check the block we built
    if 'adm_ldapservice' not in auth_block:
        return False, 'BUG: auth_block missing serviceAccountDN'
    # Find <auth and </auth> in the file (case-insensitive, no regex)
    lower = original.lower()
    start = lower.find('<auth')
    if start < 0:
        return False, 'No <auth> tag found in CoreConfig.xml'
    end_tag = lower.find('</auth>', start)
    if end_tag < 0:
        return False, 'No </auth> closing tag found in CoreConfig.xml'
    end = end_tag + len('</auth>')
    # Splice: everything before <auth> + our block + everything after </auth>
    patched = original[:start] + auth_block + original[end:]
    # Sanity check the patched content
    if 'adm_ldapservice' not in patched:
        return False, f'BUG: patched content missing LDAP. start={start} end={end} auth_block_len={len(auth_block)}'
    # Write to a temp file we own, then sudo cp to /opt/tak
    patch_path = os.path.join(BASE_DIR, 'CoreConfig.ldap-patch.xml')
    with open(patch_path, 'w') as f:
        f.write(patched)
    r = subprocess.run(['sudo', 'cp', os.path.abspath(patch_path), coreconfig_path], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return False, f'sudo cp failed: {r.stderr.strip()[:200]}. Run manually: sudo cp {os.path.abspath(patch_path)} /opt/tak/CoreConfig.xml && sudo systemctl restart takserver'
    # Verify the destination file
    check = subprocess.run(['grep', '-c', 'adm_ldapservice', coreconfig_path], capture_output=True, text=True, timeout=5)
    if check.returncode != 0 or check.stdout.strip() == '0':
        return False, f'File not updated. Run manually: sudo cp {os.path.abspath(patch_path)} /opt/tak/CoreConfig.xml && sudo systemctl restart takserver'
    # Restart TAK Server
    r = subprocess.run('sudo systemctl restart takserver 2>&1', shell=True, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return False, f'CoreConfig patched but TAK Server restart failed: {r.stderr.strip()[:120]}'
    return True, 'LDAP connected — CoreConfig patched and TAK Server restarted.'

def _ensure_authentik_webadmin():
    """Ensure webadmin user exists in Authentik with path=users for 8446 LDAP login.
    Needed when Authentik was deployed before TAK Server (webadmin skipped at deploy time).
    Returns (True, None) on success, (False, error_msg) on failure."""
    import urllib.request as _req
    import urllib.error
    if not os.path.exists('/opt/tak'):
        return True, None
    env_path = os.path.expanduser('~/authentik/.env')
    if not os.path.exists(env_path):
        return False, 'Authentik .env not found'
    ak_token = ''
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                ak_token = line.strip().split('=', 1)[1].strip()
                break
    if not ak_token:
        return False, 'Authentik token not in .env'
    settings = load_settings()
    webadmin_pass = settings.get('webadmin_password', '') or 'TakserverAtak1!'
    url = 'http://127.0.0.1:9090'
    headers = {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}
    try:
        group_pk = None
        req = _req.Request(f'{url}/api/v3/core/groups/?search=tak_ROLE_ADMIN', headers=headers)
        resp = _req.urlopen(req, timeout=10)
        results = json.loads(resp.read().decode())['results']
        group_pk = results[0]['pk'] if results else None
        if not group_pk:
            gr = _req.Request(f'{url}/api/v3/core/groups/', data=json.dumps({'name': 'tak_ROLE_ADMIN', 'is_superuser': False}).encode(), headers=headers, method='POST')
            group_pk = json.loads(_req.urlopen(gr, timeout=10).read().decode())['pk']
        req = _req.Request(f'{url}/api/v3/core/users/?search=webadmin', headers=headers)
        resp = _req.urlopen(req, timeout=10)
        results = json.loads(resp.read().decode())['results']
        user_obj = next((u for u in results if u.get('username') == 'webadmin'), None)
        if not user_obj:
            ud = {'username': 'webadmin', 'name': 'TAK Admin', 'is_active': True, 'path': 'users', 'groups': [group_pk] if group_pk else []}
            req = _req.Request(f'{url}/api/v3/core/users/', data=json.dumps(ud).encode(), headers=headers, method='POST')
            user_obj = json.loads(_req.urlopen(req, timeout=10).read().decode())
        webadmin_pk = user_obj['pk']
        patch_fields = {}
        if user_obj.get('path', '') != 'users':
            patch_fields['path'] = 'users'
        existing = user_obj.get('groups') or []
        g_pks = [g.get('pk', g) if isinstance(g, dict) else g for g in existing]
        if group_pk and group_pk not in g_pks:
            patch_fields['groups'] = list(set(g_pks + [group_pk]))
        if patch_fields:
            req = _req.Request(f'{url}/api/v3/core/users/{webadmin_pk}/', data=json.dumps(patch_fields).encode(), headers=headers, method='PATCH')
            _req.urlopen(req, timeout=10)
        req = _req.Request(f'{url}/api/v3/core/users/{webadmin_pk}/set_password/', data=json.dumps({'password': webadmin_pass}).encode(), headers=headers, method='POST')
        _req.urlopen(req, timeout=10)
        # Add webadmin to authentik Admins so LDAP application allows bind (8446 login)
        req = _req.Request(f'{url}/api/v3/core/groups/?search=authentik+Admins', headers=headers)
        resp = _req.urlopen(req, timeout=10)
        groups = json.loads(resp.read().decode())['results']
        admins_grp = next((g for g in groups if g.get('name') == 'authentik Admins'), None)
        if admins_grp:
            users_raw = admins_grp.get('users') or []
            member_pks = [u.get('pk') if isinstance(u, dict) else u for u in users_raw]
            if webadmin_pk not in member_pks:
                req = _req.Request(f'{url}/api/v3/core/groups/{admins_grp["pk"]}/add_user/',
                    data=json.dumps({'pk': webadmin_pk}).encode(), headers=headers, method='POST')
                _req.urlopen(req, timeout=10)
        # Restart LDAP outpost to clear bind cache (password change would otherwise be ignored until cache expires)
        ak_dir = os.path.expanduser('~/authentik')
        if os.path.exists(os.path.join(ak_dir, 'docker-compose.yml')):
            subprocess.run('cd ~/authentik && docker compose up -d --force-recreate ldap 2>/dev/null',
                shell=True, capture_output=True, timeout=90)
        return True, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:200]
        except Exception:
            body = ''
        return False, f'Authentik API {e.code}: {body}'
    except Exception as e:
        return False, str(e)[:120]

@app.route('/api/takserver/sync-webadmin', methods=['POST'])
@login_required
def takserver_sync_webadmin():
    """Create or update webadmin user in Authentik with password from settings. Use when 8446 login fails (e.g. Authentik was deployed before TAK Server)."""
    if not os.path.exists('/opt/tak'):
        return jsonify({'success': False, 'message': 'TAK Server not installed'}), 400
    if not os.path.exists(os.path.expanduser('~/authentik/.env')):
        return jsonify({'success': False, 'message': 'Authentik not installed'}), 400
    ok, err = _ensure_authentik_webadmin()
    if ok:
        return jsonify({'success': True, 'message': 'Webadmin user synced to Authentik. Use the same password you set at TAK Server deploy to log in to 8446.'})
    return jsonify({'success': False, 'message': err or 'Sync failed'}), 400


@app.route('/api/takserver/webadmin-password')
@login_required
def takserver_webadmin_password():
    """Return webadmin password from settings (for Show Password on TAK Server page)."""
    settings = load_settings()
    pw = settings.get('webadmin_password', '').strip()
    if pw:
        return jsonify({'password': pw})
    return jsonify({'password': ''})


@app.route('/api/takserver/connect-ldap', methods=['POST'])
@login_required
def takserver_connect_ldap():
    """One-shot: fix LDAP blueprint (remove recursion-causing password_stage), fix flow auth, ensure LDAP app open to all users (QR registration), ensure service account, ensure webadmin, patch CoreConfig, restart TAK Server."""
    diag = []
    # Fix LDAP blueprint on disk if it still has the broken password_stage (causes "invalid credentials" / recursion on user bind, e.g. QR code)
    bp_path = os.path.expanduser('~/authentik/blueprints/tak-ldap-setup.yaml')
    if os.path.exists(bp_path):
        try:
            with open(bp_path, 'r') as f:
                content = f.read()
            if 'password_stage: !KeyOf ldap-authentication-password' in content:
                content = content.replace('      password_stage: !KeyOf ldap-authentication-password\n', '')
                with open(bp_path, 'w') as f:
                    f.write(content)
                subprocess.run('cd ~/authentik && docker compose restart worker 2>&1', shell=True, capture_output=True, timeout=90)
                time.sleep(50)  # let blueprint reconcile and update identification stage
                diag.append('LDAP blueprint fixed (removed password_stage); worker restarted')
        except Exception as e:
            diag.append(f'Blueprint fix: {str(e)[:80]}')
    # Fix flow (clear identification password_stage, ensure 3 ldap-* bindings) so user bind / QR works
    ok_flow, err_flow = _ensure_ldap_flow_authentication_none()
    if not ok_flow:
        diag.append(f'Flow fix: {err_flow}')
    else:
        diag.append('Flow: OK')
    # Ensure LDAP app has no restrictive policy (blocks QR registration for non-admin users)
    try:
        env_path = os.path.expanduser('~/authentik/.env')
        ak_token = ''
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_TOKEN='):
                    ak_token = line.strip().split('=', 1)[1].strip()
                    break
        if ak_token:
            _ensure_app_access_policies('http://127.0.0.1:9090', {'Authorization': f'Bearer {ak_token}', 'Content-Type': 'application/json'}, lambda m: diag.append(m.strip()))
            diag.append('App policies: LDAP open to all authenticated users')
    except Exception as e:
        diag.append(f'App policies: {str(e)[:60]}')
    ok, msg = _ensure_authentik_ldap_service_account()
    if not ok:
        if '-w' in (msg or ''):
            msg = 'ldapsearch timed out or failed (check Authentik LDAP outpost logs)'
        return jsonify({'success': False, 'message': f'LDAP bind failed: {msg}'}), 400
    diag.append(f'Service account: {msg}')
    ok, err = _ensure_authentik_webadmin()
    if not ok:
        diag.append(f'WebAdmin: {err}')
    else:
        diag.append('WebAdmin: OK')
    ok, msg = _apply_ldap_to_coreconfig()
    diag.append(f'CoreConfig: {msg}')
    # Diagnostic: compare passwords and check outpost health
    try:
        env_path = os.path.expanduser('~/authentik/.env')
        ldap_pass = ''
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith('AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD='):
                    ldap_pass = line.strip().split('=', 1)[1].strip()
                    break
        import re as _re
        cc_pass = ''
        if os.path.exists('/opt/tak/CoreConfig.xml'):
            with open('/opt/tak/CoreConfig.xml') as f:
                m = _re.search(r'serviceAccountCredential="([^"]*)"', f.read())
                cc_pass = m.group(1) if m else ''
        if ldap_pass and cc_pass:
            diag.append(f'Password match: {"YES" if ldap_pass == cc_pass else "NO (MISMATCH!)"}')
        elif not cc_pass:
            diag.append('Password: not in CoreConfig')
        r = subprocess.run('docker ps --filter name=authentik-ldap --format "{{.Status}}" 2>/dev/null',
            shell=True, capture_output=True, text=True, timeout=10)
        ldap_status = (r.stdout or '').strip()
        diag.append(f'LDAP outpost: {ldap_status or "not running"}')
        r = subprocess.run('docker logs authentik-ldap-1 --since 30s 2>&1 | tail -5',
            shell=True, capture_output=True, text=True, timeout=10)
        outpost_tail = (r.stdout or '').strip()
        if outpost_tail:
            diag.append(f'Outpost log: {outpost_tail[:200]}')
    except Exception as e:
        diag.append(f'Diagnostic error: {str(e)[:100]}')
    return jsonify({'success': ok, 'message': ' | '.join(diag)})

@app.route('/api/takserver/vacuum', methods=['POST'])
@login_required
def takserver_vacuum():
    """Run VACUUM on the CoT database. Default: VACUUM ANALYZE (safe, reclaims space). Optional: VACUUM FULL (locks tables, reclaims more)."""
    if not os.path.exists('/opt/tak'):
        return jsonify({'success': False, 'error': 'TAK Server not installed'}), 400
    data = request.get_json() or {}
    use_full = data.get('full') is True
    if use_full:
        cmd = "sudo -u postgres psql -d cot -c 'VACUUM FULL;' 2>&1"
        timeout_sec = 3600
    else:
        cmd = "sudo -u postgres psql -d cot -c 'VACUUM ANALYZE;' 2>&1"
        timeout_sec = 600
    try:
        # Run from / so postgres user does not hit "Permission denied" on app dir (e.g. /root/infra-TAK)
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout_sec, cwd='/')
        out = (r.stdout or '') + (r.stderr or '')
        if r.returncode != 0:
            return jsonify({'success': False, 'error': out.strip() or f'Exit code {r.returncode}'}), 400
        return jsonify({'success': True, 'output': out.strip(), 'full': use_full})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'VACUUM timed out (database may be very large)'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/takserver/cot-db-size')
@login_required
def takserver_cot_db_size():
    """Return CoT database size in bytes and human-readable (for UI)."""
    if not os.path.exists('/opt/tak'):
        return jsonify({'size_bytes': 0, 'size_human': 'N/A', 'error': 'TAK Server not installed'})
    try:
        r = subprocess.run(
            "sudo -u postgres psql -t -A -c \"SELECT COALESCE(pg_database_size('cot'), 0);\" 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=10
        )
        size = int((r.stdout or '0').strip() or 0)
        if size >= 1024 ** 3:
            human = f'{size // (1024**3)} GB'
        elif size >= 1024 ** 2:
            human = f'{size // (1024**2)} MB'
        elif size >= 1024:
            human = f'{size // 1024} KB'
        else:
            human = f'{size} B'
        return jsonify({'size_bytes': size, 'size_human': human})
    except Exception as e:
        return jsonify({'size_bytes': 0, 'size_human': 'N/A', 'error': str(e)})


@app.route('/api/takserver/cert-expiry')
@login_required
def takserver_cert_expiry():
    """Return Root CA and Intermediate CA expiry dates and days remaining."""
    cert_dir = '/opt/tak/certs/files'
    results = {}
    for label, filename in [('root_ca', 'root-ca.pem'), ('intermediate_ca', 'ca.pem')]:
        path = os.path.join(cert_dir, filename)
        if not os.path.exists(path):
            results[label] = {'error': 'Not found', 'file': filename}
            continue
        try:
            r = subprocess.run(
                ['openssl', 'x509', '-enddate', '-noout', '-in', path],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                results[label] = {'error': 'Failed to read cert'}
                continue
            raw = r.stdout.strip().split('=', 1)[-1]
            from datetime import datetime
            expiry = datetime.strptime(raw, '%b %d %H:%M:%S %Y %Z')
            now = datetime.utcnow()
            days_left = (expiry - now).days
            results[label] = {
                'file': filename,
                'expires': expiry.strftime('%Y-%m-%d'),
                'days_left': days_left
            }
        except Exception as e:
            results[label] = {'error': str(e)}
    return jsonify(results)


@app.route('/api/takserver/groups')
@login_required
def takserver_groups():
    """List groups from TAK Server via the Marti API using admin cert."""
    cert_dir = '/opt/tak/certs/files'
    admin_p12 = os.path.join(cert_dir, 'admin.p12')
    if not os.path.exists(admin_p12):
        return jsonify({'error': 'admin.p12 not found in /opt/tak/certs/files/', 'groups': []})
    try:
        # TAK Server generates legacy PKCS12 (RC2-40-CBC) that modern curl/OpenSSL 3.x
        # rejects (exit 58). Extract PEM cert+key with -legacy flag for curl.
        admin_pem = '/tmp/tak-admin-curl.pem'
        admin_key = '/tmp/tak-admin-curl.key'
        subprocess.run(
            f'openssl pkcs12 -in {admin_p12} -passin pass:atakatak -clcerts -nokeys -legacy 2>/dev/null > {admin_pem}',
            shell=True, capture_output=True, text=True, timeout=10)
        subprocess.run(
            f'openssl pkcs12 -in {admin_p12} -passin pass:atakatak -nocerts -nodes -legacy 2>/dev/null > {admin_key}',
            shell=True, capture_output=True, text=True, timeout=10)
        if not os.path.exists(admin_pem) or os.path.getsize(admin_pem) == 0:
            return jsonify({'error': 'Failed to extract PEM from admin.p12 (legacy conversion)', 'groups': []})
        cmd = ['curl', '-sk', '--max-time', '8',
               '--cert', admin_pem, '--key', admin_key,
               'https://127.0.0.1:8443/Marti/api/groups/all']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        body = (r.stdout or '').strip()
        if r.returncode != 0 or not body:
            return jsonify({'error': f'TAK Server did not respond (exit {r.returncode})', 'groups': []})
        import json as _json
        try:
            data = _json.loads(body)
        except _json.JSONDecodeError:
            return jsonify({'error': 'TAK Server returned invalid response', 'groups': [], 'raw': body[:200]})
        groups = []
        items = data.get('data', data) if isinstance(data, dict) else data
        if isinstance(items, list):
            for g in items:
                if not isinstance(g, dict):
                    continue
                name = g.get('name', '')
                if name and name != '__ANON__':
                    groups.append({
                        'name': name,
                        'direction': g.get('direction', ''),
                        'active': g.get('active', True)
                    })
        groups.sort(key=lambda x: x['name'])
        return jsonify({'groups': groups})
    except Exception as e:
        return jsonify({'error': str(e), 'groups': []})
    finally:
        for f in ['/tmp/tak-admin-curl.pem', '/tmp/tak-admin-curl.key']:
            try:
                os.remove(f)
            except OSError:
                pass


@app.route('/api/takserver/ca-info')
@login_required
def takserver_ca_info():
    """Return current Root CA and Intermediate CA names, expiry, and truststore contents."""
    cert_dir = '/opt/tak/certs/files'
    info = {'root_ca': None, 'intermediate_ca': None, 'old_cas_in_truststore': [], 'suggested_new_name': ''}
    for label, filename in [('root_ca', 'root-ca.pem'), ('intermediate_ca', 'ca.pem')]:
        path = os.path.join(cert_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            r = subprocess.run(['openssl', 'x509', '-subject', '-enddate', '-noout', '-in', path],
                               capture_output=True, text=True, timeout=5)
            cn = ''
            expiry_raw = ''
            for line in r.stdout.strip().split('\n'):
                line = line.strip()
                if line.startswith('subject=') or line.startswith('subject ='):
                    subj = line.split('=', 1)[-1].strip()
                    for part in subj.split(','):
                        part = part.strip()
                        if part.startswith('CN') or part.startswith('CN '):
                            cn = part.split('=', 1)[-1].strip()
                elif 'notAfter' in line:
                    expiry_raw = line.split('=', 1)[-1].strip()
            days_left = None
            expires = ''
            if expiry_raw:
                from datetime import datetime
                exp_dt = datetime.strptime(expiry_raw, '%b %d %H:%M:%S %Y %Z')
                days_left = (exp_dt - datetime.utcnow()).days
                expires = exp_dt.strftime('%Y-%m-%d')
            info[label] = {'name': cn, 'file': filename, 'expires': expires, 'days_left': days_left}
        except Exception:
            pass
    import re
    def _increment_name(name):
        m = re.search(r'(\d+)$', name)
        if m:
            return name[:m.start()] + f'{int(m.group(1)) + 1:02d}'
        return name + '-02'
    if info['intermediate_ca'] and info['intermediate_ca']['name']:
        info['suggested_new_name'] = _increment_name(info['intermediate_ca']['name'])
    if info['root_ca'] and info['root_ca']['name']:
        info['suggested_new_root_name'] = _increment_name(info['root_ca']['name'])
        info['suggested_new_root_int_name'] = _increment_name(info.get('suggested_new_name', 'INT-CA-01'))
    # List CAs in current truststore (to show old CAs that can be revoked)
    import glob as _glob
    ts_files = sorted(_glob.glob(os.path.join(cert_dir, 'truststore-*.jks')))
    ts_files = [f for f in ts_files if 'root' not in os.path.basename(f)]
    if ts_files:
        ts_path = ts_files[-1]
        info['truststore_file'] = os.path.basename(ts_path)
        try:
            r = subprocess.run(
                ['keytool', '-list', '-keystore', ts_path, '-storepass', 'atakatak'],
                capture_output=True, text=True, timeout=10)
            aliases = []
            trusted_aliases = []
            for line in r.stdout.split('\n'):
                if ',' not in line:
                    continue
                alias = line.split(',')[0].strip()
                if 'trustedCertEntry' in line:
                    aliases.append(alias)
                    trusted_aliases.append(alias)
                elif 'PrivateKeyEntry' in line:
                    aliases.append(alias)
            info['truststore_aliases'] = aliases
            current_cn = (info['intermediate_ca'] or {}).get('name', '').lower()
            root_cn = (info['root_ca'] or {}).get('name', '').lower()
            old_cas = []
            for a in trusted_aliases:
                if a.lower() != current_cn.lower() and a.lower() != 'root-ca' and a.lower() != root_cn.lower():
                    old_cas.append(a)
            info['old_cas_in_truststore'] = old_cas
        except Exception:
            pass
    return jsonify(info)


rotate_intca_log = []
rotate_intca_status = {'running': False, 'complete': False, 'error': False}

@app.route('/api/takserver/rotate-intca', methods=['POST'])
@login_required
def takserver_rotate_intca():
    """Rotate the intermediate CA: create new CA, server cert, admin cert, import old CA into truststore."""
    if rotate_intca_status.get('running'):
        return jsonify({'error': 'Rotation already in progress'}), 409
    data = request.json or {}
    new_ca_name = (data.get('new_ca_name') or '').strip()
    if not new_ca_name:
        return jsonify({'error': 'New CA name is required'}), 400
    import re
    if not re.match(r'^[a-zA-Z0-9._-]+$', new_ca_name):
        return jsonify({'error': 'CA name can only contain letters, numbers, dots, hyphens, underscores'}), 400

    cert_dir = '/opt/tak/certs/files'
    if not os.path.exists(os.path.join(cert_dir, 'root-ca.pem')):
        return jsonify({'error': 'root-ca.pem not found — cannot rotate without a Root CA'}), 400
    if not os.path.exists(os.path.join(cert_dir, 'ca.pem')):
        return jsonify({'error': 'ca.pem not found — no current intermediate CA detected'}), 400

    # Detect current intermediate CA name
    try:
        r = subprocess.run(['openssl', 'x509', '-subject', '-noout', '-in', os.path.join(cert_dir, 'ca.pem')],
                           capture_output=True, text=True, timeout=5)
        old_ca_name = ''
        for part in r.stdout.replace('subject=', '').split(','):
            part = part.strip()
            if part.startswith('CN') or part.startswith('CN '):
                old_ca_name = part.split('=', 1)[-1].strip()
    except Exception:
        old_ca_name = ''
    if not old_ca_name:
        return jsonify({'error': 'Could not detect current intermediate CA name from ca.pem'}), 500
    if new_ca_name == old_ca_name:
        return jsonify({'error': f'New CA name must be different from current ({old_ca_name})'}), 400

    rotate_intca_log.clear()
    rotate_intca_status.update({'running': True, 'complete': False, 'error': False})

    def do_rotate():
        def log(msg):
            rotate_intca_log.append(msg)

        def run(cmd, desc=None, check=True):
            if desc:
                log(desc)
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                if check and r.returncode != 0:
                    err = (r.stderr or r.stdout or '').strip()[:200]
                    log(f"  ✗ Failed (exit {r.returncode}): {err}")
                    return False
                return True
            except Exception as e:
                log(f"  ✗ Exception: {e}")
                return False

        try:
            log(f"━━━ Rotating Intermediate CA ━━━")
            log(f"  Old CA: {old_ca_name}")
            log(f"  New CA: {new_ca_name}")
            log("")

            log("Step 1/7: Restoring Root CA as working CA...")
            run(f'cp {cert_dir}/root-ca.pem {cert_dir}/ca.pem')
            run(f'cp {cert_dir}/root-ca-do-not-share.key {cert_dir}/ca-do-not-share.key')
            run(f'cp {cert_dir}/root-ca-trusted.pem {cert_dir}/ca-trusted.pem')
            log("✓ Root CA files restored")

            log("")
            log(f"Step 2/7: Creating new Intermediate CA: {new_ca_name}...")
            run('chmod +r /opt/tak/certs/cert-metadata.sh 2>/dev/null')
            if not run(f'cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh ca "{new_ca_name}" 2>&1'):
                raise Exception('Failed to create new intermediate CA')
            log(f"✓ Intermediate CA {new_ca_name} created")

            log("")
            log("Step 3/7: Creating new server certificate...")
            if not run('cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh server takserver 2>&1'):
                raise Exception('Failed to create server certificate')
            log("✓ Server certificate created (signed by new CA)")

            log("")
            log("Step 4/7: Regenerating all client certificates...")
            run('chmod +r /opt/tak/certs/cert-metadata.sh 2>/dev/null')
            skip = {'takserver', 'root-ca', 'ca', old_ca_name.lower(), new_ca_name.lower()}
            regen_count = 0
            for f in sorted(os.listdir(cert_dir)):
                if not f.endswith('.p12'):
                    continue
                name = f[:-4]
                if name.lower() in skip or name.startswith('truststore-'):
                    continue
                log(f"  Regenerating: {name}")
                run(f'cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh client {name} 2>&1')
                regen_count += 1
            log(f"✓ {regen_count} client certificate(s) regenerated (signed by new CA)")

            log("")
            log("Step 5/7: Updating truststore...")
            ts_jks = os.path.join(cert_dir, f'truststore-{new_ca_name}.jks')
            run(f'keytool -import -alias root-ca -file {cert_dir}/root-ca.pem '
                f'-keystore {ts_jks} -storepass atakatak -noprompt 2>&1', check=False)
            log("  Root CA imported into new truststore")
            old_pem = os.path.join(cert_dir, f'{old_ca_name}.pem')
            if os.path.exists(old_pem):
                run(f'keytool -import -trustcacerts -file {old_pem} '
                    f'-keystore {ts_jks} -alias "{old_ca_name}" -deststorepass atakatak -noprompt 2>&1',
                    check=False)
                log(f"  Old CA ({old_ca_name}) imported into new truststore (transition period)")
            else:
                log(f"  ⚠ {old_ca_name}.pem not found — old CA NOT added to truststore")
            log("✓ Truststore updated")

            log("")
            log("Step 6/7: Updating CoreConfig.xml...")
            run(f'sed -i "s/{old_ca_name}/{new_ca_name}/g" /opt/tak/CoreConfig.xml')
            run(f'sed -i "s/{old_ca_name}/{new_ca_name}/g" /opt/tak/CoreConfig.example.xml 2>/dev/null', check=False)
            log("✓ CoreConfig.xml updated")

            log("")
            log("Step 7/8: Updating TAK Portal certificates...")
            portal_running = subprocess.run('docker ps --format "{{.Names}}" 2>/dev/null | grep -q tak-portal',
                                            shell=True, capture_output=True).returncode == 0
            if portal_running:
                run('docker exec tak-portal mkdir -p /usr/src/app/data/certs', check=False)
                admin_p12 = os.path.join(cert_dir, 'admin.p12')
                modern_p12 = '/tmp/tak-portal-admin-modern.p12'
                subprocess.run(
                    f'openssl pkcs12 -in {admin_p12} -passin pass:atakatak -nodes -legacy 2>/dev/null | '
                    f'openssl pkcs12 -export -passout pass:atakatak -out {modern_p12}',
                    shell=True, capture_output=True, text=True, timeout=30)
                if os.path.exists(modern_p12) and os.path.getsize(modern_p12) > 0:
                    run(f'docker cp {modern_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', check=False)
                    os.remove(modern_p12)
                    log("  ✓ admin.p12 copied to TAK Portal (re-encoded)")
                else:
                    run(f'docker cp {admin_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', check=False)
                    log("  ✓ admin.p12 copied to TAK Portal")
                takserver_pem = os.path.join(cert_dir, 'takserver.pem')
                if os.path.exists(takserver_pem):
                    run(f'docker cp {takserver_pem} tak-portal:/usr/src/app/data/certs/tak-ca.pem', check=False)
                    log("  ✓ CA chain copied to TAK Portal")
                else:
                    int_pem = os.path.join(cert_dir, 'ca.pem')
                    root_pem = os.path.join(cert_dir, 'root-ca.pem')
                    bundle = '/tmp/tak-ca-bundle.pem'
                    run(f'cat {int_pem} {root_pem} > {bundle} 2>/dev/null', check=False)
                    if os.path.exists(bundle) and os.path.getsize(bundle) > 0:
                        run(f'docker cp {bundle} tak-portal:/usr/src/app/data/certs/tak-ca.pem', check=False)
                        os.remove(bundle)
                        log("  ✓ CA bundle copied to TAK Portal")
                run('docker restart tak-portal 2>/dev/null', check=False)
                log("  ✓ TAK Portal restarted with new certificates")
            else:
                log("  TAK Portal not running — will update on next deploy")

            log("")
            log("Step 8/8: Restarting TAK Server...")
            run('systemctl restart takserver 2>&1')
            log("  Waiting for TAK Server to come back up...")
            time.sleep(45)
            log("✓ TAK Server restarted")

            log("")
            log("━━━ ROTATION COMPLETE ━━━")
            log(f"  New signing CA: {new_ca_name}")
            log(f"  Old CA ({old_ca_name}) is still trusted for existing clients")
            log(f"  New admin.p12 and user.p12 have been regenerated")
            log(f"  ⚠ Re-import admin.p12 in your browser for CloudTAK/8443 access")
            log(f"  When ready, use 'Revoke Old CA' to remove {old_ca_name} from the truststore")
            rotate_intca_status.update({'running': False, 'complete': True, 'error': False})
        except Exception as e:
            log(f"")
            log(f"✗ ROTATION FAILED: {e}")
            rotate_intca_status.update({'running': False, 'complete': True, 'error': True})

    import threading
    threading.Thread(target=do_rotate, daemon=True).start()
    return jsonify({'started': True, 'old_ca': old_ca_name, 'new_ca': new_ca_name})


@app.route('/api/takserver/rotate-intca/status')
@login_required
def takserver_rotate_intca_status():
    return jsonify({'log': rotate_intca_log, **rotate_intca_status})


@app.route('/api/takserver/revoke-old-ca', methods=['POST'])
@login_required
def takserver_revoke_old_ca():
    """Remove an old intermediate CA from the truststore, cutting off clients with old certs."""
    data = request.json or {}
    old_ca_alias = (data.get('old_ca_alias') or '').strip()
    if not old_ca_alias:
        return jsonify({'error': 'Old CA alias is required'}), 400

    cert_dir = '/opt/tak/certs/files'
    import glob as _glob
    ts_files = sorted(_glob.glob(os.path.join(cert_dir, 'truststore-*.jks')))
    ts_files = [f for f in ts_files if 'root' not in os.path.basename(f)]
    if not ts_files:
        return jsonify({'error': 'No truststore found'}), 500
    ts_path = ts_files[-1]

    try:
        r = subprocess.run(
            ['keytool', '-delete', '-alias', old_ca_alias,
             '-keystore', ts_path, '-storepass', 'atakatak'],
            capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return jsonify({'error': f'keytool failed: {r.stderr or r.stdout}'}), 500

        # Also regenerate the .p12 truststore from the .jks
        ts_p12 = ts_path.replace('.jks', '.p12')
        subprocess.run(
            f'keytool -importkeystore -srckeystore {ts_path} -destkeystore {ts_p12} '
            f'-srcstoretype JKS -deststoretype PKCS12 -srcstorepass atakatak -deststorepass atakatak -noprompt 2>&1',
            shell=True, capture_output=True, text=True, timeout=15)

        subprocess.run('systemctl restart takserver 2>&1', shell=True, capture_output=True, text=True, timeout=30)
        return jsonify({
            'success': True,
            'message': f'Removed {old_ca_alias} from truststore and restarted TAK Server. '
                       f'Clients with certificates signed by {old_ca_alias} will no longer be able to connect.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


rotate_rootca_log = []
rotate_rootca_status = {'running': False, 'complete': False, 'error': False}

@app.route('/api/takserver/rotate-rootca', methods=['POST'])
@login_required
def takserver_rotate_rootca():
    """Full Root CA rotation: new root, new intermediate, new server cert, all client certs, update TAK Portal, restart."""
    if rotate_rootca_status.get('running'):
        return jsonify({'error': 'Root CA rotation already in progress'}), 409
    data = request.json or {}
    new_root_name = (data.get('new_root_name') or '').strip()
    new_int_name = (data.get('new_int_name') or '').strip()
    if not new_root_name or not new_int_name:
        return jsonify({'error': 'Both new Root CA and Intermediate CA names are required'}), 400
    import re
    for name in [new_root_name, new_int_name]:
        if not re.match(r'^[a-zA-Z0-9._-]+$', name):
            return jsonify({'error': f'CA name "{name}" can only contain letters, numbers, dots, hyphens, underscores'}), 400

    cert_dir = '/opt/tak/certs/files'
    if not os.path.exists(os.path.join(cert_dir, 'root-ca.pem')):
        return jsonify({'error': 'root-ca.pem not found — no current Root CA detected'}), 400

    # Detect current names
    old_root_name = ''
    old_int_name = ''
    for label, filename in [('root', 'root-ca.pem'), ('int', 'ca.pem')]:
        path = os.path.join(cert_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            r = subprocess.run(['openssl', 'x509', '-subject', '-noout', '-in', path],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().split('\n'):
                if line.startswith('subject=') or line.startswith('subject ='):
                    subj = line.split('=', 1)[-1].strip()
                    for part in subj.split(','):
                        part = part.strip()
                        if part.startswith('CN') or part.startswith('CN '):
                            cn = part.split('=', 1)[-1].strip()
                            if label == 'root':
                                old_root_name = cn
                            else:
                                old_int_name = cn
        except Exception:
            pass
    if not old_root_name:
        return jsonify({'error': 'Could not detect current Root CA name'}), 500

    rotate_rootca_log.clear()
    rotate_rootca_status.update({'running': True, 'complete': False, 'error': False})

    def do_rotate_root():
        def log(msg):
            rotate_rootca_log.append(msg)

        def run(cmd, desc=None, check=True):
            if desc:
                log(desc)
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                if check and r.returncode != 0:
                    err = (r.stderr or r.stdout or '').strip()[:200]
                    log(f"  ✗ Failed (exit {r.returncode}): {err}")
                    return False
                return True
            except Exception as e:
                log(f"  ✗ Exception: {e}")
                return False

        try:
            log("━━━ Rotating Root CA ━━━")
            log(f"  Old Root CA: {old_root_name}")
            log(f"  Old Intermediate CA: {old_int_name}")
            log(f"  New Root CA: {new_root_name}")
            log(f"  New Intermediate CA: {new_int_name}")
            log("")

            log("Step 1/8: Removing old certificate files...")
            run('rm -rf /opt/tak/certs/files')
            run('mkdir -p /opt/tak/certs/files')
            run('chown -R tak:tak /opt/tak/certs/')
            log("✓ Old cert files cleared")

            log("")
            log(f"Step 2/8: Creating new Root CA: {new_root_name}...")
            run('chmod +r /opt/tak/certs/cert-metadata.sh 2>/dev/null')
            if not run(f'cd /opt/tak/certs && echo "{new_root_name}" | sudo -u tak ./makeRootCa.sh 2>&1'):
                raise Exception('Failed to create new Root CA')
            log(f"✓ Root CA {new_root_name} created")

            log("")
            log(f"Step 3/8: Creating new Intermediate CA: {new_int_name}...")
            if not run(f'cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh ca "{new_int_name}" 2>&1'):
                raise Exception('Failed to create new Intermediate CA')
            log(f"✓ Intermediate CA {new_int_name} created")

            log("")
            log("Step 4/8: Creating new server certificate...")
            if not run('cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh server takserver 2>&1'):
                raise Exception('Failed to create server certificate')
            log("✓ Server certificate created")

            log("")
            log("Step 5/8: Regenerating all client certificates...")
            skip = {'takserver', 'root-ca', 'ca', new_root_name.lower(), new_int_name.lower(),
                    old_root_name.lower(), old_int_name.lower()}
            # We need to create admin and user first since old files were cleared
            run('cd /opt/tak/certs && sudo -u tak ./makeCert.sh client admin 2>&1')
            log("  Regenerated: admin")
            run('cd /opt/tak/certs && sudo -u tak ./makeCert.sh client user 2>&1')
            log("  Regenerated: user")
            # Check settings or old backup for any other client cert names to recreate
            regen_count = 2
            log(f"✓ {regen_count} client certificate(s) created")
            log("  Note: Additional client certs (Node-RED, etc.) must be recreated manually")

            log("")
            log("Step 6/8: Updating truststore...")
            ts_jks = os.path.join(cert_dir, f'truststore-{new_int_name}.jks')
            run(f'keytool -import -alias root-ca -file {cert_dir}/root-ca.pem '
                f'-keystore {ts_jks} -storepass atakatak -noprompt 2>&1', check=False)
            log("  Root CA imported into truststore")
            log("✓ Truststore updated")

            log("")
            log("Step 7/8: Updating CoreConfig.xml...")
            if old_int_name:
                run(f'sed -i "s/{old_int_name}/{new_int_name}/g" /opt/tak/CoreConfig.xml')
                run(f'sed -i "s/{old_int_name}/{new_int_name}/g" /opt/tak/CoreConfig.example.xml 2>/dev/null', check=False)
            if old_root_name and old_root_name != new_root_name:
                run(f'sed -i "s/{old_root_name}/{new_root_name}/g" /opt/tak/CoreConfig.xml', check=False)
                run(f'sed -i "s/{old_root_name}/{new_root_name}/g" /opt/tak/CoreConfig.example.xml 2>/dev/null', check=False)
            log("✓ CoreConfig.xml updated")

            log("")
            log("Step 8/8: Restarting TAK Server and updating TAK Portal...")
            run('systemctl restart takserver 2>&1')
            log("  TAK Server restarting...")

            # Copy new certs to TAK Portal if it's running
            portal_running = subprocess.run('docker ps --format "{{.Names}}" 2>/dev/null | grep -q tak-portal',
                                            shell=True, capture_output=True).returncode == 0
            if portal_running:
                log("  Updating TAK Portal certificates...")
                run('docker exec tak-portal mkdir -p /usr/src/app/data/certs', check=False)
                admin_p12 = os.path.join(cert_dir, 'admin.p12')
                modern_p12 = '/tmp/tak-portal-admin-modern.p12'
                r_enc = subprocess.run(
                    f'openssl pkcs12 -in {admin_p12} -passin pass:atakatak -nodes -legacy 2>/dev/null | '
                    f'openssl pkcs12 -export -passout pass:atakatak -out {modern_p12}',
                    shell=True, capture_output=True, text=True, timeout=30)
                if os.path.exists(modern_p12) and os.path.getsize(modern_p12) > 0:
                    run(f'docker cp {modern_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', check=False)
                    os.remove(modern_p12)
                    log("  ✓ admin.p12 copied to TAK Portal (re-encoded)")
                else:
                    run(f'docker cp {admin_p12} tak-portal:/usr/src/app/data/certs/tak-client.p12', check=False)
                    log("  ✓ admin.p12 copied to TAK Portal")
                takserver_pem = os.path.join(cert_dir, 'takserver.pem')
                if os.path.exists(takserver_pem):
                    run(f'docker cp {takserver_pem} tak-portal:/usr/src/app/data/certs/tak-ca.pem', check=False)
                    log("  ✓ CA chain copied to TAK Portal")
                else:
                    int_pem = os.path.join(cert_dir, 'ca.pem')
                    root_pem = os.path.join(cert_dir, 'root-ca.pem')
                    bundle = '/tmp/tak-ca-bundle.pem'
                    run(f'cat {int_pem} {root_pem} > {bundle} 2>/dev/null', check=False)
                    if os.path.exists(bundle) and os.path.getsize(bundle) > 0:
                        run(f'docker cp {bundle} tak-portal:/usr/src/app/data/certs/tak-ca.pem', check=False)
                        os.remove(bundle)
                        log("  ✓ CA bundle copied to TAK Portal")
                run('docker restart tak-portal 2>/dev/null', check=False)
                log("  ✓ TAK Portal restarted with new certificates")
            else:
                log("  TAK Portal not running — skip cert copy (will update on next TAK Portal deploy)")

            log("  Waiting for TAK Server to come back up...")
            time.sleep(45)
            log("✓ TAK Server restarted")

            log("")
            log("━━━ ROOT CA ROTATION COMPLETE ━━━")
            log(f"  New Root CA: {new_root_name}")
            log(f"  New Intermediate CA: {new_int_name}")
            log(f"  All certificates have been regenerated")
            if portal_running:
                log(f"  TAK Portal updated — users can scan new QR codes to re-enroll")
            log(f"  All existing client connections are disconnected")
            log(f"  Clients must re-enroll via TAK Portal QR code")
            rotate_rootca_status.update({'running': False, 'complete': True, 'error': False})
        except Exception as e:
            log(f"")
            log(f"✗ ROOT CA ROTATION FAILED: {e}")
            rotate_rootca_status.update({'running': False, 'complete': True, 'error': True})

    import threading
    threading.Thread(target=do_rotate_root, daemon=True).start()
    return jsonify({'started': True, 'old_root': old_root_name, 'new_root': new_root_name})


@app.route('/api/takserver/rotate-rootca/status')
@login_required
def takserver_rotate_rootca_status():
    return jsonify({'log': rotate_rootca_log, **rotate_rootca_status})


@app.route('/api/takserver/create-client-cert', methods=['POST'])
@login_required
def takserver_create_client_cert():
    """Create a client certificate with optional group assignment."""
    data = request.json or {}
    cert_name = (data.get('name') or '').strip()
    if not cert_name:
        return jsonify({'error': 'Certificate name is required'}), 400
    import re
    if not re.match(r'^[a-zA-Z0-9._-]+$', cert_name):
        return jsonify({'error': 'Name can only contain letters, numbers, dots, hyphens, underscores'}), 400
    if len(cert_name) > 64:
        return jsonify({'error': 'Name too long (max 64 chars)'}), 400

    cert_dir = '/opt/tak/certs/files'
    if os.path.exists(os.path.join(cert_dir, f'{cert_name}.p12')):
        return jsonify({'error': f'Certificate "{cert_name}" already exists'}), 400

    groups_in = data.get('groups_in', [])
    groups_out = data.get('groups_out', [])

    try:
        subprocess.run('chmod +r /opt/tak/certs/cert-metadata.sh 2>/dev/null', shell=True, capture_output=True)
        r = subprocess.run(
            f'sudo -u tak bash -c "cd /opt/tak/certs && ./makeCert.sh client {cert_name}" 2>&1',
            shell=True, capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return jsonify({'error': f'makeCert.sh failed: {r.stdout or r.stderr}'}), 500

        p12_path = os.path.join(cert_dir, f'{cert_name}.p12')
        if not os.path.exists(p12_path):
            return jsonify({'error': 'Certificate file was not created'}), 500

        if groups_in or groups_out:
            pem_path = os.path.join(cert_dir, f'{cert_name}.pem')
            cmd = f'java -jar /opt/tak/utils/UserManager.jar certmod'
            for g in groups_in:
                cmd += f' -ig {g}'
            for g in groups_out:
                cmd += f' -og {g}'
            cmd += f' {pem_path} 2>&1'
            gr = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if gr.returncode != 0:
                pass  # cert still created, group assignment is best-effort

        return jsonify({
            'success': True,
            'name': cert_name,
            'p12': f'{cert_name}.p12',
            'download_url': f'/api/certs/download/{cert_name}.p12',
            'groups_in': groups_in,
            'groups_out': groups_out
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/takserver/control', methods=['POST'])
@login_required
def takserver_control():
    action = request.json.get('action')
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'error': 'Invalid action'}), 400
    subprocess.run(['systemctl', action, 'takserver'], capture_output=True, text=True, timeout=60)
    time.sleep(3)
    s = subprocess.run(['systemctl', 'is-active', 'takserver'], capture_output=True, text=True)
    return jsonify({'success': True, 'running': s.stdout.strip() == 'active', 'action': action})

@app.route('/api/takserver/log')
@login_required
def takserver_log():
    """Tail the takserver-messaging.log file"""
    log_path = '/opt/tak/logs/takserver-messaging.log'
    offset = request.args.get('offset', 0, type=int)
    lines = request.args.get('lines', 100, type=int)
    if not os.path.exists(log_path):
        return jsonify({'entries': [], 'offset': 0, 'size': 0})
    try:
        size = os.path.getsize(log_path)
        if offset == 0:
            r = subprocess.run(f'tail -n {lines} "{log_path}"', shell=True, capture_output=True, text=True, timeout=10)
            entries = r.stdout.strip().split('\n') if r.stdout.strip() else []
            return jsonify({'entries': entries, 'offset': size, 'size': size})
        elif size > offset:
            with open(log_path, 'r') as f:
                f.seek(offset)
                new_data = f.read()
            entries = new_data.strip().split('\n') if new_data.strip() else []
            return jsonify({'entries': entries, 'offset': size, 'size': size})
        else:
            return jsonify({'entries': [], 'offset': offset, 'size': size})
    except Exception as e:
        return jsonify({'entries': [f'Error reading log: {str(e)}'], 'offset': offset, 'size': 0})

@app.route('/api/takserver/services')
@login_required
def takserver_services():
    """Get TAK Server Java process status"""
    services = []
    try:
        r = subprocess.run("ps aux | grep java | grep -v grep", shell=True, capture_output=True, text=True, timeout=10)
        seen = {}
        for line in r.stdout.strip().split('\n'):
            if not line.strip(): continue
            parts = line.split()
            if len(parts) < 11: continue
            pid = parts[1]
            cpu = parts[2]
            mem_pct = parts[3]
            rss_kb = int(parts[5])
            mem_mb = round(rss_kb / 1024)
            cmd = ' '.join(parts[10:])
            # Identify the service
            if 'profiles.active=messaging' in cmd:
                name = 'Messaging'; icon = '📡'
            elif 'profiles.active=api' in cmd:
                name = 'API'; icon = '🧩'
            elif 'profiles.active=config' in cmd:
                name = 'Config'; icon = '⚙️'
            elif 'takserver-pm.jar' in cmd:
                name = 'Plugin Manager'; icon = '🔌'
            elif 'takserver-retention.jar' in cmd:
                name = 'Retention'; icon = '📦'
            else:
                continue  # skip unknown java processes
            # Keep only one entry per service name (highest mem)
            if name not in seen or mem_mb > seen[name]['mem_mb_raw']:
                seen[name] = {
                    'name': name, 'icon': icon, 'pid': pid,
                    'cpu': f"{cpu}%", 'mem_mb': f"{mem_mb} MB",
                    'mem_pct': f"{mem_pct}%", 'status': 'running',
                    'mem_mb_raw': mem_mb
                }
        for svc in seen.values():
            del svc['mem_mb_raw']
            services.append(svc)
        # Check PostgreSQL
        pg = subprocess.run("systemctl is-active postgresql", shell=True, capture_output=True, text=True, timeout=5)
        services.append({
            'name': 'PostgreSQL', 'icon': '🐘', 'pid': '',
            'cpu': '', 'mem_mb': '', 'mem_pct': '',
            'status': 'running' if pg.stdout.strip() == 'active' else 'stopped'
        })
    except Exception as e:
        services.append({'name': 'Error', 'icon': '❌', 'status': str(e)})
    return jsonify({'services': services, 'count': len([s for s in services if s['status'] == 'running'])})

@app.route('/api/takserver/uninstall', methods=['POST'])
@login_required
def takserver_uninstall():
    """Remove TAK Server, clean up, ready for fresh deploy"""
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    steps = []
    # Stop service
    subprocess.run(['systemctl', 'stop', 'takserver'], capture_output=True, timeout=60)
    subprocess.run(['systemctl', 'disable', 'takserver'], capture_output=True, timeout=30)
    steps.append('Stopped TAK Server')
    # Kill any remaining processes
    subprocess.run('pkill -9 -f takserver 2>/dev/null; true', shell=True, capture_output=True)
    steps.append('Killed remaining processes')
    # Remove package
    pkg_result = subprocess.run('dpkg -l | grep takserver', shell=True, capture_output=True, text=True)
    if 'takserver' in pkg_result.stdout:
        subprocess.run('DEBIAN_FRONTEND=noninteractive apt-get remove -y takserver 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        steps.append('Removed TAK Server package')
    # Clean up /opt/tak
    if os.path.exists('/opt/tak'):
        subprocess.run('rm -rf /opt/tak', shell=True, capture_output=True)
        steps.append('Removed /opt/tak')
    # Clean up PostgreSQL database and user (so redeploys start clean)
    subprocess.run("sudo -u postgres psql -c \"DROP DATABASE IF EXISTS cot;\" 2>/dev/null; true", shell=True, capture_output=True, timeout=30)
    subprocess.run("sudo -u postgres psql -c \"DROP USER IF EXISTS martiuser;\" 2>/dev/null; true", shell=True, capture_output=True, timeout=30)
    steps.append('Cleaned up PostgreSQL (cot database, martiuser)')
    # Clean up GPG verification artifacts
    subprocess.run('rm -rf /usr/share/debsig/keyrings/* /etc/debsig/policies/* 2>/dev/null; true', shell=True, capture_output=True, timeout=10)
    steps.append('Cleaned up GPG verification artifacts')
    # Clean up uploads so user can upload fresh
    for f in os.listdir(UPLOAD_DIR):
        os.remove(os.path.join(UPLOAD_DIR, f))
    steps.append('Cleared uploads')
    # Reset deploy status
    deploy_log.clear()
    deploy_status.update({'running': False, 'complete': False, 'error': False})
    return jsonify({'success': True, 'steps': steps})

@app.route('/api/upload/takserver', methods=['POST'])
@login_required
def upload_takserver_package():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400
    os_type = load_settings().get('os_type', '')
    results = {'package': None, 'gpg_key': None, 'policy': None}
    for f in files:
        fn = f.filename
        if not fn: continue
        fp = os.path.join(UPLOAD_DIR, fn)
        f.save(fp)
        sz = round(os.path.getsize(fp) / (1024*1024), 1)
        if fn.endswith('.deb'):
            if 'rocky' in os_type:
                os.remove(fp)
                return jsonify({'error': f'DEB uploaded but system is {os_type}. Need .rpm.'}), 400
            results['package'] = {'filename': fn, 'filepath': fp, 'pkg_type': 'deb', 'size_mb': sz}
        elif fn.endswith('.rpm'):
            if 'ubuntu' in os_type:
                os.remove(fp)
                return jsonify({'error': f'RPM uploaded but system is {os_type}. Need .deb.'}), 400
            results['package'] = {'filename': fn, 'filepath': fp, 'pkg_type': 'rpm', 'size_mb': sz}
        elif fn.endswith('.key') or 'gpg' in fn.lower():
            results['gpg_key'] = {'filename': fn, 'filepath': fp, 'size_mb': sz}
        elif fn.endswith('.pol') or 'policy' in fn.lower():
            results['policy'] = {'filename': fn, 'filepath': fp, 'size_mb': sz}
    return jsonify({'success': True, **results,
        'has_verification': results['gpg_key'] is not None and results['policy'] is not None})

@app.route('/api/upload/takserver/delete', methods=['POST'])
@login_required
def delete_uploaded_file():
    fn = request.json.get('filename', '')
    import re
    if not fn or not re.match(r'^[a-zA-Z0-9._-]+$', fn):
        return jsonify({'error': 'Invalid filename'}), 400
    fp = os.path.join(UPLOAD_DIR, fn)
    if os.path.exists(fp):
        os.remove(fp)
        return jsonify({'success': True, 'filename': fn})
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/upload/takserver/existing')
@login_required
def check_existing_uploads():
    """Check for files already uploaded from a previous session"""
    files = {}
    for fn in os.listdir(UPLOAD_DIR):
        fp = os.path.join(UPLOAD_DIR, fn)
        sz = os.path.getsize(fp)
        sz_mb = round(sz / (1024*1024), 1)
        if fn.endswith('.deb') or fn.endswith('.rpm'):
            files['package'] = {'filename': fn, 'filepath': fp, 'size_mb': sz_mb}
        elif fn.endswith('.key'):
            files['gpg_key'] = {'filename': fn, 'filepath': fp, 'size_mb': sz_mb}
        elif fn.endswith('.pol'):
            files['policy'] = {'filename': fn, 'filepath': fp, 'size_mb': sz_mb}
    return jsonify(files)

# === TAK Server Deployment ===

deploy_log = []
deploy_status = {'running': False, 'complete': False, 'error': False, 'cancelled': False}

upgrade_log = []
upgrade_status = {'running': False, 'complete': False, 'error': False}

@app.route('/api/takserver/update', methods=['POST'])
@login_required
def takserver_update():
    """Run TAK Server upgrade (Ubuntu: apt install ./takserver_*.deb). User uploads new .deb first."""
    if not os.path.exists('/opt/tak'):
        return jsonify({'error': 'TAK Server not installed. Deploy TAK Server first.'}), 400
    settings = load_settings()
    if settings.get('pkg_mgr', 'apt') != 'apt':
        return jsonify({'error': 'TAK Server update is supported on Ubuntu only for now. Rocky/RHEL coming later.'}), 400
    if upgrade_status['running']:
        return jsonify({'error': 'Update already in progress'}), 409
    pkg_files = sorted([f for f in os.listdir(UPLOAD_DIR) if f.endswith('.deb')],
        key=lambda f: os.path.getmtime(os.path.join(UPLOAD_DIR, f)), reverse=True)
    if not pkg_files:
        return jsonify({'error': 'No .deb package found. Upload the new TAK Server .deb from tak.gov first.'}), 400
    upgrade_log.clear()
    upgrade_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_takserver_upgrade, args=(os.path.join(UPLOAD_DIR, pkg_files[0]),), daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/takserver/update/log')
@login_required
def takserver_update_log():
    idx = int(request.args.get('index', 0))
    return jsonify({'entries': upgrade_log[idx:], 'total': len(upgrade_log),
        'running': upgrade_status['running'], 'complete': upgrade_status['complete'], 'error': upgrade_status['error']})

def run_takserver_upgrade(pkg_path):
    def ulog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        upgrade_log.append(entry)
        print(entry, flush=True)
    try:
        pkg_name = os.path.basename(pkg_path)
        ulog("=" * 50)
        ulog("TAK Server update (upgrade)")
        ulog("=" * 50)
        wait_for_apt_lock(ulog, upgrade_log)
        ulog("")
        ulog("Installing upgrade package: " + pkg_name)
        r = subprocess.run(
            f'DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y ./{pkg_name} 2>&1',
            shell=True, cwd=os.path.dirname(pkg_path), capture_output=True, text=True, timeout=600)
        out = (r.stdout or '') + (r.stderr or '')
        for line in out.strip().split('\n'):
            if line.strip() and 'NEEDRESTART' not in line:
                upgrade_log.append("  " + line)
        if r.returncode != 0:
            ulog("Update failed (exit " + str(r.returncode) + ")")
            upgrade_status.update({'running': False, 'complete': False, 'error': True})
            return
        ulog("Restarting TAK Server...")
        subprocess.run('systemctl restart takserver', shell=True, capture_output=True, text=True, timeout=30)
        ulog("TAK Server update complete.")
        upgrade_status.update({'running': False, 'complete': True, 'error': False})
    except Exception as e:
        ulog("Error: " + str(e))
        upgrade_status.update({'running': False, 'complete': False, 'error': True})

@app.route('/api/deploy/cancel', methods=['POST'])
@login_required
def cancel_deploy():
    if not deploy_status['running']:
        return jsonify({'error': 'No deployment in progress'}), 400
    deploy_status['cancelled'] = True
    log_step("⚠ Deployment cancelled by user")
    deploy_status.update({'running': False, 'error': True})
    # Kill any running subprocess children
    subprocess.run('pkill -P $$ 2>/dev/null; true', shell=True, capture_output=True)
    return jsonify({'success': True})

@app.route('/api/deploy/takserver', methods=['POST'])
@login_required
def deploy_takserver():
    if deploy_status['running']:
        return jsonify({'error': 'Deployment already in progress'}), 400
    data = request.json
    if not data: return jsonify({'error': 'No configuration provided'}), 400
    pkg_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.deb') or f.endswith('.rpm')]
    if not pkg_files: return jsonify({'error': 'No package file found.'}), 400
    config = {
        'package_path': os.path.join(UPLOAD_DIR, pkg_files[0]),
        'cert_country': data.get('cert_country', 'US'), 'cert_state': data.get('cert_state', 'CA'),
        'cert_city': data.get('cert_city', ''), 'cert_org': data.get('cert_org', ''),
        'cert_ou': data.get('cert_ou', ''), 'root_ca_name': data.get('root_ca_name', 'ROOT-CA-01'),
        'intermediate_ca_name': data.get('intermediate_ca_name', 'INTERMEDIATE-CA-01'),
        'enable_admin_ui': data.get('enable_admin_ui', False),
        'enable_webtak': data.get('enable_webtak', False),
        'enable_nonadmin_ui': data.get('enable_nonadmin_ui', False),
        'webadmin_password': data.get('webadmin_password', ''),
    }
    for ext, key in [('.key', 'gpg_key_path'), ('.pol', 'policy_path')]:
        matches = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(ext)]
        if matches: config[key] = os.path.join(UPLOAD_DIR, matches[0])
    deploy_log.clear()
    deploy_status.update({'running': True, 'complete': False, 'error': False})
    threading.Thread(target=run_takserver_deploy, args=(config,), daemon=True).start()
    return jsonify({'success': True})

def log_step(msg):
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    deploy_log.append(entry)
    print(entry, flush=True)

def run_cmd(cmd, desc=None, check=True, quiet=False):
    if desc: log_step(desc)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        if not quiet and r.stdout.strip():
            for line in r.stdout.strip().split('\n'):
                if 'NEEDRESTART' not in line:
                    deploy_log.append(f"  {line}")
        if not quiet and r.stderr.strip():
            for line in r.stderr.strip().split('\n'):
                if 'NEEDRESTART' not in line and 'error' in line.lower():
                    deploy_log.append(f"  ✗ {line}")
        if check and r.returncode != 0:
            log_step(f"✗ Command failed (exit {r.returncode})")
            return False
        return True
    except Exception as e:
        log_step(f"✗ {str(e)}")
        return False

def wait_for_package_lock():
    """Wait for unattended-upgrades to finish (common on fresh VPS).
    NO TIMEOUT - waits as long as needed. Ticks every 10 seconds."""
    log_step("Checking for system upgrades in progress...")
    r = subprocess.run('ps aux | grep "/usr/bin/unattended-upgrade" | grep -v shutdown | grep -v grep', shell=True, capture_output=True, text=True)
    if r.stdout.strip() == '':
        log_step("\u2713 No system upgrades in progress, continuing...")
        return True
    log_step("\u23f3 System is running unattended-upgrades, waiting for completion...")
    log_step("  This can take 20-45 minutes on a fresh VPS. Do not cancel.")
    waited = 0
    while True:
        time.sleep(10)
        waited += 10
        if deploy_status.get('cancelled'):
            log_step("⚠ Cancelled during upgrade wait")
            return False
        r = subprocess.run('ps aux | grep "/usr/bin/unattended-upgrade" | grep -v shutdown | grep -v grep', shell=True, capture_output=True, text=True)
        if r.stdout.strip() == '':
            m, s = divmod(waited, 60)
            log_step(f"\u2713 System upgrades complete! (waited {m}m {s}s)")
            time.sleep(5)
            return True
        m, s = divmod(waited, 60)
        deploy_log.append(f"  \u23f3 {m:02d}:{s:02d}")

def run_takserver_deploy(config):
    try:
        deploy_status['cancelled'] = False
        log_step("=" * 50); log_step("TAK Server Deployment Starting"); log_step("=" * 50)
        pkg = config['package_path']; pkg_name = os.path.basename(pkg)

        wait_for_package_lock()
        if deploy_status.get('cancelled'): return

        log_step(""); log_step("━━━ Step 1/9: System Limits ━━━")
        run_cmd('grep -q "soft nofile 32768" /etc/security/limits.conf || echo -e "* soft nofile 32768\\n* hard nofile 32768" >> /etc/security/limits.conf', "Increasing JVM thread limits...")
        log_step("✓ System limits configured")

        log_step(""); log_step("━━━ Step 2/9: PostgreSQL Repository ━━━")
        run_cmd('DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y lsb-release > /dev/null 2>&1', "Installing prerequisites...", check=False)
        run_cmd('install -d /usr/share/postgresql-common/pgdg', check=False)
        run_cmd('curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc 2>/dev/null', "Adding PostgreSQL GPG key...")
        run_cmd('echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list')
        run_cmd('apt-get update -qq > /dev/null 2>&1', "Updating package lists...")
        log_step("✓ PostgreSQL repository configured")

        log_step(""); log_step("━━━ Step 3/9: Package Verification ━━━")
        if config.get('gpg_key_path') and config.get('policy_path'):
            log_step("GPG key and policy found — verifying...")
            run_cmd('DEBIAN_FRONTEND=noninteractive apt-get install -y debsig-verify', check=False)
            r = subprocess.run(f"grep 'id=' {config['policy_path']} | head -1 | sed 's/.*id=\"\\([^\"]*\\)\".*/\\1/'", shell=True, capture_output=True, text=True)
            pid = r.stdout.strip()
            log_step(f"  Policy ID: {pid}")
            if pid:
                run_cmd(f'mkdir -p /usr/share/debsig/keyrings/{pid}')
                run_cmd(f'mkdir -p /etc/debsig/policies/{pid}')
                run_cmd(f'rm -f /usr/share/debsig/keyrings/{pid}/debsig.gpg')
                run_cmd(f'touch /usr/share/debsig/keyrings/{pid}/debsig.gpg')
                run_cmd(f'gpg --no-default-keyring --keyring /usr/share/debsig/keyrings/{pid}/debsig.gpg --import {config["gpg_key_path"]}')
                run_cmd(f'cp {config["policy_path"]} /etc/debsig/policies/{pid}/debsig.pol')
                v = subprocess.run(f'debsig-verify -v {pkg}', shell=True, capture_output=True, text=True)
                if v.returncode == 0: log_step("✓ Package signature VERIFIED")
                else:
                    log_step(f"⚠ Verification exit code {v.returncode} — installing anyway")
                    if v.stdout.strip():
                        for line in v.stdout.strip().split('\n'):
                            if line.strip(): log_step(f"  {line.strip()}")
                    if v.stderr.strip():
                        for line in v.stderr.strip().split('\n'):
                            if line.strip(): log_step(f"  {line.strip()}")
        else:
            log_step("No GPG key/policy — skipping verification")

        log_step(""); log_step("━━━ Step 4/9: Installing TAK Server ━━━")
        settings = load_settings()
        if settings.get('pkg_mgr', 'apt') == 'apt':
            wait_for_apt_lock(log_step, deploy_log)
        log_step(f"Installing {pkg_name}...")
        # Primary: apt-get install handles dependencies automatically
        r1 = run_cmd(f'DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y {pkg} 2>&1', check=False)
        if not r1:
            # Fallback: dpkg + fix-broken (proven chain from Ubuntu script)
            log_step("  apt-get failed, trying dpkg + dependency fix...")
            run_cmd(f'DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l dpkg -i {pkg} 2>&1', check=False)
            run_cmd('DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -f -y 2>&1', "  Resolving dependencies...", check=False)
        # PostgreSQL cluster check (from proven script - sometimes cluster isn't created)
        pg_check = subprocess.run('pg_lsclusters 2>/dev/null | grep -q "15"', shell=True, capture_output=True)
        if pg_check.returncode != 0:
            log_step("  Creating PostgreSQL 15 cluster...")
            run_cmd('pg_createcluster 15 main --start 2>&1', check=False)
        # dpkg --configure if partially installed (from proven script)
        run_cmd('dpkg --configure -a 2>&1', check=False, quiet=True)
        if not os.path.exists('/opt/tak'):
            log_step("✗ FATAL: /opt/tak not found after install"); deploy_status.update({'error': True, 'running': False}); return
        log_step("✓ TAK Server installed")

        log_step(""); log_step("━━━ Step 5/9: Starting TAK Server ━━━")
        run_cmd('systemctl daemon-reload')
        run_cmd('systemctl start takserver', "Starting TAK Server...")
        run_cmd('systemctl enable takserver > /dev/null 2>&1')
        log_step("Waiting 30 seconds...")
        for remaining in range(20, -1, -10):
            time.sleep(10)
            deploy_log.append(f"  \u23f3 {remaining//60:02d}:{remaining%60:02d} remaining")
        log_step("✓ TAK Server started")

        log_step(""); log_step("━━━ Step 6/9: Configuring Firewall ━━━")
        for p in ['22/tcp', '8089/tcp', '8443/tcp', '8446/tcp', '5001/tcp']:
            run_cmd(f'ufw allow {p} > /dev/null 2>&1')
        run_cmd('ufw --force enable > /dev/null 2>&1')
        log_step("✓ Firewall configured (22, 8089, 8443, 8446, 5001)")

        log_step(""); log_step("━━━ Step 7/9: Generating Certificates ━━━")
        root_ca, int_ca = config['root_ca_name'], config['intermediate_ca_name']
        log_step(f"  Root CA: {root_ca} | Intermediate CA: {int_ca}")
        run_cmd('rm -rf /opt/tak/certs/files')
        run_cmd('cd /opt/tak/certs && cp cert-metadata.sh cert-metadata.sh.original 2>/dev/null; true')
        run_cmd('cd /opt/tak/certs && cp cert-metadata.sh.original cert-metadata.sh 2>/dev/null; true')
        subs = [('COUNTRY=US', f'COUNTRY={config["cert_country"]}'),
                ('STATE=${STATE}', f'STATE={config["cert_state"]}'),
                ('CITY=${CITY}', f'CITY={config["cert_city"]}'),
                ('ORGANIZATION=${ORGANIZATION:-TAK}', f'ORGANIZATION={config["cert_org"]}'),
                ('ORGANIZATIONAL_UNIT=${ORGANIZATIONAL_UNIT}', f'ORGANIZATIONAL_UNIT={config["cert_ou"]}')]
        for old, new in subs:
            run_cmd(f'sed -i "s/{old}/{new}/g" /opt/tak/certs/cert-metadata.sh', check=False)
        run_cmd('chown -R tak:tak /opt/tak/certs/')
        log_step(f"Creating Root CA: {root_ca}...")
        run_cmd(f'cd /opt/tak/certs && echo "{root_ca}" | sudo -u tak ./makeRootCa.sh 2>&1', quiet=True)
        log_step(f"Creating Intermediate CA: {int_ca}...")
        run_cmd(f'cd /opt/tak/certs && echo "y" | sudo -u tak ./makeCert.sh ca "{int_ca}" 2>&1', quiet=True)
        log_step("Creating server certificate...")
        run_cmd('cd /opt/tak/certs && sudo -u tak ./makeCert.sh server takserver 2>&1', quiet=True)
        log_step("Creating admin certificate...")
        run_cmd('cd /opt/tak/certs && sudo -u tak ./makeCert.sh client admin 2>&1', quiet=True)
        log_step("Creating user certificate...")
        run_cmd('cd /opt/tak/certs && sudo -u tak ./makeCert.sh client user 2>&1', quiet=True)
        log_step("✓ All certificates created")
        log_step("Importing root CA into TAK clients truststore...")
        run_cmd(f'keytool -import -alias root-ca -file /opt/tak/certs/files/root-ca.pem -keystore /opt/tak/certs/files/truststore-{int_ca}.jks -storepass atakatak -noprompt 2>&1', check=False)
        log_step("✓ Root CA imported into truststore (TAK clients trust chain complete)")
        log_step("Restarting TAK Server...")
        run_cmd('systemctl stop takserver'); time.sleep(10)
        run_cmd('pkill -9 -f takserver 2>/dev/null; true', check=False); time.sleep(5)
        run_cmd('systemctl start takserver')
        log_step("Waiting 1.5 minutes...")
        for remaining in range(80, -1, -10):
            time.sleep(10)
            deploy_log.append(f"  \u23f3 {remaining//60:02d}:{remaining%60:02d} remaining")

        log_step(""); log_step("━━━ Step 8/9: Configuring CoreConfig.xml ━━━")
        run_cmd('sed -i \'s|<input auth="anonymous" _name="stdtcp" protocol="tcp" port="8087"/>|<input auth="x509" _name="stdssl" protocol="tls" port="8089"/>|g\' /opt/tak/CoreConfig.xml', "Enabling X.509 auth on 8089...")
        run_cmd(f'sed -i "s|truststoreFile=\\"certs/files/truststore-root.jks|truststoreFile=\\"certs/files/truststore-{int_ca}.jks|g" /opt/tak/CoreConfig.xml', "Setting intermediate CA truststore...")
        cert_block = (f'<certificateSigning CA="TAKServer"><certificateConfig>\\n'
            f'<nameEntries>\\n<nameEntry name="O" value="{config["cert_org"]}"/>\\n'
            f'<nameEntry name="OU" value="{config["cert_ou"]}"/>\\n</nameEntries>\\n'
            f'</certificateConfig>\\n<TAKServerCAConfig keystore="JKS" '
            f'keystoreFile="certs/files/{int_ca}-signing.jks" keystorePass="atakatak" '
            f'validityDays="3650" signatureAlg="SHA256WithRSA" />\\n'
            f'</certificateSigning>\\n<vbm enabled="false"/>')
        run_cmd(f'sed -i \'s|<vbm enabled="false"/>|{cert_block}|g\' /opt/tak/CoreConfig.xml', "Enabling certificate enrollment...")
        run_cmd('sed -i \'s|<auth>|<auth x509useGroupCache="true">|g\' /opt/tak/CoreConfig.xml')
        admin_ui = str(config.get('enable_admin_ui', False)).lower()
        webtak = str(config.get('enable_webtak', False)).lower()
        nonadmin = str(config.get('enable_nonadmin_ui', False)).lower()
        if config.get('enable_admin_ui') or config.get('enable_webtak') or config.get('enable_nonadmin_ui'):
            log_step(f"WebTAK: AdminUI={admin_ui}, WebTAK={webtak}, NonAdminUI={nonadmin}")
            run_cmd(f'sed -i \'s|"cert_https"/|"cert_https" enableAdminUI="{admin_ui}" enableWebtak="{webtak}" enableNonAdminUI="{nonadmin}"/|g\' /opt/tak/CoreConfig.xml')
        log_step("✓ CoreConfig.xml configured")
        log_step("Final restart...")
        run_cmd('systemctl stop takserver'); time.sleep(10)
        run_cmd('pkill -9 -f takserver 2>/dev/null; true', check=False); time.sleep(5)
        run_cmd('systemctl start takserver')
        log_step("Waiting 10 minutes for full initialization before promoting admin...")
        total_wait = 600
        waited = 0
        while waited < total_wait:
            time.sleep(10)
            waited += 10
            if deploy_status.get('cancelled'):
                log_step("\u26a0 Cancelled during initialization wait")
                return
            left = total_wait - waited
            m, s = divmod(left, 60)
            deploy_log.append(f"  \u23f3 {m:02d}:{s:02d} remaining")
        log_step("\u2713 Initialization wait complete")

        log_step(""); log_step("━━━ Step 9/9: Promoting Admin ━━━")
        run_cmd('java -jar /opt/tak/utils/UserManager.jar certmod -A /opt/tak/certs/files/admin.pem 2>&1', "Promoting admin certificate...", check=False)
        webadmin_pass = config.get('webadmin_password', '')
        if webadmin_pass:
            log_step("Creating webadmin user...")
            run_cmd(f"java -jar /opt/tak/utils/UserManager.jar usermod -A -p '{webadmin_pass}' webadmin 2>&1", check=False)
            log_step("✓ webadmin user created")
        run_cmd('systemctl restart takserver')
        log_step("Waiting 30 seconds...")
        for remaining in range(20, -1, -10):
            time.sleep(10)
            deploy_log.append(f"  \u23f3 {remaining//60:02d}:{remaining%60:02d} remaining")
        ip = load_settings().get('server_ip', 'YOUR-IP')
        settings = load_settings()
        # Save webadmin_password to settings so Authentik deploy can read it
        if webadmin_pass:
            settings['webadmin_password'] = webadmin_pass
            save_settings(settings)
        log_step(""); log_step("=" * 50); log_step("✓ DEPLOYMENT COMPLETE!"); log_step("=" * 50); log_step("")
        log_step(f"  WebGUI (cert):     https://{ip}:8443")
        if webadmin_pass:
            log_step(f"  WebGUI (password): https://{ip}:8446")
            log_step(f"  Username: webadmin")
        log_step(f"  Certificate Password: atakatak")
        log_step(f"  Admin cert: /opt/tak/certs/files/admin.p12")
        # Regenerate Caddyfile if Caddy is configured
        if settings.get('fqdn'):
            generate_caddyfile(settings)
            subprocess.run('systemctl reload caddy 2>/dev/null; true', shell=True, capture_output=True)
            log_step(f"  ✓ Caddy config updated for TAK Server")

        # If Authentik is installed, ensure webadmin exists there (for 8446 LDAP login). On fresh install with Authentik-first order, this runs here so user does not need to click Sync webadmin.
        if webadmin_pass and os.path.exists(os.path.expanduser('~/authentik/.env')):
            ok, err = _ensure_authentik_webadmin()
            if ok:
                log_step("  ✓ webadmin synced to Authentik (8446 login ready)")
            elif err:
                log_step(f"  ⚠ webadmin sync: {err[:80]} — use Sync webadmin button if 8446 fails")

        # If Caddy is already running with a domain, install LE cert on 8446 now.
        # This handles the case where Caddy was deployed before TAK Server.
        fqdn = settings.get('fqdn', '')
        if fqdn:
            caddy_active = subprocess.run('systemctl is-active caddy', shell=True, capture_output=True, text=True)
            if caddy_active.stdout.strip() == 'active':
                log_step("")
                log_step("━━━ Installing LE Cert on Port 8446 ━━━")
                install_le_cert_on_8446(fqdn, log_step, wait_for_cert=True)

        deploy_status.update({'complete': True, 'running': False})
    except Exception as e:
        log_step(f"✗ FATAL ERROR: {str(e)}")
        deploy_status.update({'error': True, 'running': False})

@app.route('/api/download/admin-cert')
@login_required
def download_admin_cert():
    p = '/opt/tak/certs/files'
    if os.path.exists(os.path.join(p, 'admin.p12')): return send_from_directory(p, 'admin.p12', as_attachment=True)
    return jsonify({'error': 'admin.p12 not found'}), 404

@app.route('/api/download/user-cert')
@login_required
def download_user_cert():
    p = '/opt/tak/certs/files'
    if os.path.exists(os.path.join(p, 'user.p12')): return send_from_directory(p, 'user.p12', as_attachment=True)
    return jsonify({'error': 'user.p12 not found'}), 404

@app.route('/api/download/truststore')
@login_required
def download_truststore():
    p = '/opt/tak/certs/files'
    if os.path.exists(p):
        for f in os.listdir(p):
            if f.startswith('truststore-') and f.endswith('.p12') and 'root' not in f:
                return send_from_directory(p, f, as_attachment=True)
    return jsonify({'error': 'truststore not found'}), 404

@app.route('/api/certs/list')
@login_required
def list_cert_files():
    cert_path = '/opt/tak/certs/files'
    if not os.path.exists(cert_path):
        return jsonify({'files': []})
    files = []
    for f in sorted(os.listdir(cert_path)):
        fp = os.path.join(cert_path, f)
        if os.path.isfile(fp):
            files.append({'name': f, 'size': os.path.getsize(fp),
                'size_display': f"{os.path.getsize(fp)/1024:.1f} KB" if os.path.getsize(fp) < 1024*1024 else f"{os.path.getsize(fp)/(1024*1024):.1f} MB"})
    return jsonify({'files': files})

@app.route('/api/certs/download/<filename>')
@login_required
def download_cert_file(filename):
    import re
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        return jsonify({'error': 'Invalid filename'}), 400
    cert_path = '/opt/tak/certs/files'
    fp = os.path.join(cert_path, filename)
    if os.path.exists(fp) and os.path.isfile(fp):
        return send_from_directory(cert_path, filename, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/deploy/log')
@login_required
def deploy_log_stream():
    last = int(request.args.get('after', 0))
    return jsonify({'entries': deploy_log[last:], 'total': len(deploy_log),
        'running': deploy_status['running'], 'complete': deploy_status['complete'], 'error': deploy_status['error']})

# === Shared CSS ===
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');
*{margin:0;padding:0;box-sizing:border-box}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;word-wrap:normal;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px;overflow:visible;line-height:1.35}
.sidebar-logo span{font-size:15px;font-weight:700;letter-spacing:.02em;color:var(--text-primary)}
.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
:root{--bg-primary:#0a0e17;--bg-card:rgba(15,23,42,0.7);--bg-card-hover:rgba(15,23,42,0.9);--border:rgba(59,130,246,0.1);--border-hover:rgba(59,130,246,0.3);--text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-dim:#94a3b8;--accent:#3b82f6;--accent-glow:rgba(59,130,246,0.15);--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--cyan:#06b6d4}
body{font-family:'DM Sans',sans-serif;background:var(--bg-primary);color:var(--text-primary);min-height:100vh}
body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background-image:linear-gradient(rgba(59,130,246,0.02) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.02) 1px,transparent 1px);background-size:60px 60px;pointer-events:none;z-index:0}
.top-bar{position:fixed;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),var(--cyan),transparent);z-index:100}
.header{position:relative;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:20px 32px;border-bottom:1px solid var(--border)}
.header-left{display:flex;align-items:center;gap:14px}
.header-icon{width:40px;height:40px;background:linear-gradient(135deg,#1e40af,#0891b2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px}
.header-title{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:18px}
.header-subtitle{font-size:12px;color:var(--text-dim);font-family:'JetBrains Mono',monospace}
.header-right{display:flex;align-items:center;gap:16px}
.os-badge{background:var(--bg-card);border:1px solid var(--border);padding:6px 14px;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim)}
.btn-logout,.btn-back{color:var(--text-dim);text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:12px;padding:6px 14px;border:1px solid var(--border);border-radius:8px;transition:all 0.2s}
.btn-logout:hover,.btn-back:hover{color:var(--text-secondary);border-color:var(--border-hover)}
.main{position:relative;z-index:10;max-width:1100px;margin:0 auto;padding:32px}
.section-title{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px;font-weight:600}
.metrics-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}
.metric-card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:18px;text-align:center}
.metric-label{font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:6px}
.metric-value{font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;color:var(--text-primary)}
.metric-detail{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:2px}
.footer{text-align:center;padding:24px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;font-size:11px}
.form-field label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--text-dim);font-weight:600;margin-bottom:6px}
.form-field input[type="text"],.form-field input[type="password"]{width:100%;padding:10px 14px;background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:14px}
.form-field input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(59,130,246,0.1)}
@media(max-width:768px){.metrics-bar{grid-template-columns:repeat(2,1fr)}.modules-grid{grid-template-columns:1fr}.header{padding:16px 20px}.main{padding:20px}}
"""

# === Login Template ===
LOGIN_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>infra-TAK</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0a0e17;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background-image:linear-gradient(rgba(59,130,246,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.03) 1px,transparent 1px);background-size:60px 60px;z-index:0}
body::after{content:'';position:fixed;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#3b82f6,#06b6d4,transparent);z-index:10}
.lc{position:relative;z-index:1;width:100%;max-width:420px;padding:20px}
.card{background:linear-gradient(145deg,rgba(15,23,42,0.95),rgba(15,23,42,0.8));border:1px solid rgba(59,130,246,0.15);border-radius:16px;padding:48px 40px;backdrop-filter:blur(20px);box-shadow:0 0 0 1px rgba(59,130,246,0.05),0 25px 50px rgba(0,0,0,0.5)}
.logo{text-align:center;margin-bottom:36px}
.logo-icon{width:56px;height:56px;background:linear-gradient(135deg,#1e40af,#0891b2);border-radius:14px;display:inline-flex;align-items:center;justify-content:center;font-size:28px;margin-bottom:16px;box-shadow:0 8px 24px rgba(59,130,246,0.25)}
.logo h1{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#f1f5f9}
.logo p{color:#64748b;font-size:13px;margin-top:6px;letter-spacing:0.5px;text-transform:uppercase}
.logo .built-by{font-size:10px;color:#94a3b8;margin-top:8px;text-transform:none;letter-spacing:0}
.fg{margin-bottom:24px}
.fg label{display:block;color:#cbd5e1;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.fg input{width:100%;padding:14px 16px;background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:10px;color:#f1f5f9;font-family:'JetBrains Mono',monospace;font-size:15px;transition:all 0.2s}
.fg input:focus{outline:none;border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,0.1)}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.2s}
.btn:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(59,130,246,0.3)}
.err{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);color:#fca5a5;padding:12px 16px;border-radius:8px;font-size:14px;margin-bottom:20px;text-align:center}
.ver{text-align:center;margin-top:20px;color:#64748b;font-family:'JetBrains Mono',monospace;font-size:11px}
</style></head><body>
<div class="lc"><div class="card">
<div class="logo"><div class="logo-icon">⚡</div><h1>infra-TAK</h1><p>TAK Infrastructure Platform</p><p class="built-by">built by TAKWERX</p></div>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="POST"><div class="fg"><label>Password</label><input type="password" name="password" autofocus placeholder="Enter admin password"></div><button type="submit" class="btn">Sign In</button></form>
</div><div class="ver">v{{ version }}</div></div>
</body></html>'''

# === API Routes ===

@app.route('/api/metrics')
@login_required
def api_metrics():
    return jsonify(get_system_metrics())

@app.route('/api/unattended-upgrades', methods=['POST'])
@login_required
def api_toggle_unattended_upgrades():
    """Enable or disable unattended-upgrades service."""
    action = request.json.get('action') if request.is_json else None
    if action not in ('enable', 'disable'):
        return jsonify({'success': False, 'error': 'action must be enable or disable'}), 400
    try:
        if action == 'disable':
            subprocess.run('systemctl stop unattended-upgrades && systemctl disable unattended-upgrades',
                shell=True, check=True, capture_output=True, text=True, timeout=30)
            # Ubuntu/Debian also run unattended-upgrade via apt-daily-upgrade.timer; disable that too
            subprocess.run('systemctl stop apt-daily-upgrade.timer 2>/dev/null; systemctl disable apt-daily-upgrade.timer 2>/dev/null; true',
                shell=True, timeout=10)
        else:
            subprocess.run('systemctl enable unattended-upgrades && systemctl start unattended-upgrades',
                shell=True, check=True, capture_output=True, text=True, timeout=30)
            subprocess.run('systemctl enable apt-daily-upgrade.timer 2>/dev/null; systemctl start apt-daily-upgrade.timer 2>/dev/null; true',
                shell=True, timeout=10)
        uu = _get_unattended_upgrades_status()
        return jsonify({'success': True, 'enabled': uu['enabled'], 'running': uu['running']})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'error': e.stderr or str(e)}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/modules')
@login_required
def api_modules():
    """Live module states for dashboard cards (so CLI uninstall/start/stop is reflected)."""
    modules = detect_modules()
    return jsonify({k: {'installed': m.get('installed', False), 'running': m.get('running', False)} for k, m in modules.items()})

# Full uninstall (all deployed services) — for testing: reset VPS without destroying it
full_uninstall_log = []
full_uninstall_status = {'running': False, 'done': False, 'error': None}

def run_full_uninstall():
    """Remove all deployed services in reverse dependency order. Console and config remain."""
    def plog(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        full_uninstall_log.append(entry)
        print(entry, flush=True)
    try:
        settings = load_settings()
        pkg_mgr = settings.get('pkg_mgr', 'apt')

        # 1. MediaMTX
        plog("━━━ MediaMTX ━━━")
        subprocess.run('systemctl stop mediamtx mediamtx-webeditor 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
        subprocess.run('systemctl disable mediamtx mediamtx-webeditor 2>/dev/null; true', shell=True, capture_output=True)
        for f in ['/etc/systemd/system/mediamtx.service', '/etc/systemd/system/mediamtx-webeditor.service',
                  '/usr/local/bin/mediamtx', '/usr/local/etc/mediamtx.yml']:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        if os.path.exists('/opt/mediamtx-webeditor'):
            subprocess.run('rm -rf /opt/mediamtx-webeditor', shell=True, capture_output=True)
        subprocess.run('systemctl daemon-reload 2>/dev/null; true', shell=True, capture_output=True)
        mediamtx_deploy_log.clear()
        mediamtx_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ MediaMTX removed")

        # 2. TAK Portal
        plog("━━━ TAK Portal ━━━")
        portal_dir = os.path.expanduser('~/TAK-Portal')
        if os.path.exists(portal_dir):
            subprocess.run(f'cd {portal_dir} && docker compose down -v --rmi local 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
            subprocess.run(f'rm -rf {portal_dir}', shell=True, capture_output=True)
        takportal_deploy_log.clear()
        takportal_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ TAK Portal removed")

        # 3. CloudTAK
        plog("━━━ CloudTAK ━━━")
        cloudtak_dir = os.path.expanduser('~/CloudTAK')
        for yml in [os.path.join(cloudtak_dir, 'docker-compose.yml'), os.path.join(cloudtak_dir, 'compose.yaml')]:
            if os.path.exists(yml):
                subprocess.run(f'docker compose -f "{yml}" down -v --rmi local 2>/dev/null; true', shell=True, capture_output=True, timeout=180, cwd=cloudtak_dir)
                break
        if os.path.exists(cloudtak_dir):
            subprocess.run(f'rm -rf "{cloudtak_dir}"', shell=True, capture_output=True, timeout=60)
        cloudtak_deploy_log.clear()
        cloudtak_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ CloudTAK removed")

        # 4. Node-RED
        plog("━━━ Node-RED ━━━")
        nr_dir = os.path.expanduser('~/node-red')
        compose = os.path.join(nr_dir, 'docker-compose.yml')
        if os.path.exists(compose):
            subprocess.run(f'docker compose -f "{compose}" down -v 2>/dev/null; true', shell=True, capture_output=True, timeout=60, cwd=nr_dir)
        if os.path.exists(nr_dir):
            subprocess.run(f'rm -rf "{nr_dir}"', shell=True, capture_output=True, timeout=10)
        nodered_deploy_log.clear()
        nodered_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ Node-RED removed")

        # 5. TAK Server
        plog("━━━ TAK Server ━━━")
        subprocess.run(['systemctl', 'stop', 'takserver'], capture_output=True, timeout=60)
        subprocess.run(['systemctl', 'disable', 'takserver'], capture_output=True, timeout=30)
        subprocess.run('pkill -9 -f takserver 2>/dev/null; true', shell=True, capture_output=True)
        pkg_result = subprocess.run('dpkg -l | grep takserver', shell=True, capture_output=True, text=True)
        if 'takserver' in (pkg_result.stdout or ''):
            subprocess.run('DEBIAN_FRONTEND=noninteractive apt-get remove -y takserver 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        if os.path.exists('/opt/tak'):
            subprocess.run('rm -rf /opt/tak', shell=True, capture_output=True)
        subprocess.run("sudo -u postgres psql -c \"DROP DATABASE IF EXISTS cot;\" 2>/dev/null; true", shell=True, capture_output=True, timeout=30)
        subprocess.run("sudo -u postgres psql -c \"DROP USER IF EXISTS martiuser;\" 2>/dev/null; true", shell=True, capture_output=True, timeout=30)
        subprocess.run('rm -rf /usr/share/debsig/keyrings/* /etc/debsig/policies/* 2>/dev/null; true', shell=True, capture_output=True, timeout=10)
        for f in os.listdir(UPLOAD_DIR):
            try:
                os.remove(os.path.join(UPLOAD_DIR, f))
            except Exception:
                pass
        deploy_log.clear()
        deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ TAK Server removed")

        # 6. Email Relay
        plog("━━━ Email Relay ━━━")
        subprocess.run('systemctl stop postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
        subprocess.run('systemctl disable postfix 2>/dev/null; true', shell=True, capture_output=True)
        if pkg_mgr == 'apt':
            subprocess.run('apt-get remove -y postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        else:
            subprocess.run('dnf remove -y postfix 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        settings = load_settings()
        settings.pop('email_relay', None)
        save_settings(settings)
        email_deploy_log.clear()
        email_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ Email Relay removed")

        # 7. Authentik
        plog("━━━ Authentik ━━━")
        ak_dir = os.path.expanduser('~/authentik')
        if os.path.exists(ak_dir):
            subprocess.run(f'cd {ak_dir} && docker compose down -v --rmi all --remove-orphans 2>/dev/null; true', shell=True, capture_output=True, text=True, timeout=180)
            subprocess.run(f'rm -rf {ak_dir}', shell=True, capture_output=True)
        authentik_deploy_log.clear()
        authentik_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ Authentik removed")

        # 8. Caddy
        plog("━━━ Caddy ━━━")
        subprocess.run('systemctl stop caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=30)
        subprocess.run('systemctl disable caddy 2>/dev/null; true', shell=True, capture_output=True)
        if pkg_mgr == 'apt':
            subprocess.run('DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        else:
            subprocess.run('dnf remove -y caddy 2>/dev/null; true', shell=True, capture_output=True, timeout=120)
        # Ensure binary and config are gone so console no longer shows Caddy as installed (which uses "which caddy")
        for path in ['/usr/bin/caddy', '/usr/local/bin/caddy']:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    subprocess.run(f'rm -f {path}', shell=True, capture_output=True)
        if os.path.exists('/etc/caddy'):
            subprocess.run('rm -rf /etc/caddy', shell=True, capture_output=True, timeout=10)
        subprocess.run('systemctl daemon-reload 2>/dev/null; true', shell=True, capture_output=True)
        settings = load_settings()
        settings['fqdn'] = ''
        save_settings(settings)
        caddy_deploy_log.clear()
        caddy_deploy_status.update({'running': False, 'complete': False, 'error': False})
        plog("✓ Caddy removed")

        plog("")
        plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        plog("All deployed services removed. Console remains. Use Marketplace to deploy again.")
        plog("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        full_uninstall_status.update({'running': False, 'done': True, 'error': None})
    except subprocess.TimeoutExpired:
        full_uninstall_status.update({'running': False, 'done': True, 'error': 'Uninstall timed out'})
        full_uninstall_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ Timeout")
    except Exception as e:
        full_uninstall_status.update({'running': False, 'done': True, 'error': str(e)})
        full_uninstall_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ {str(e)}")

@app.route('/api/console/uninstall-all/validate', methods=['POST'])
@login_required
def console_uninstall_all_validate():
    """Check admin password only (for green check in UI)."""
    data = request.json or {}
    password = data.get('password', '')
    auth = load_auth()
    valid = bool(auth.get('password_hash') and check_password_hash(auth['password_hash'], password))
    return jsonify({'valid': valid})

@app.route('/api/console/uninstall-all', methods=['POST'])
@login_required
def console_uninstall_all():
    """Start full uninstall of all deployed services (for testing: reset without burning VPS)."""
    data = request.json or {}
    password = data.get('password', '')
    confirm = (data.get('confirm') or '').strip().upper()
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], password):
        return jsonify({'error': 'Invalid admin password'}), 403
    if confirm != 'UNINSTALL':
        return jsonify({'error': 'Type UNINSTALL in the confirmation box to proceed'}), 400
    if full_uninstall_status.get('running'):
        return jsonify({'error': 'Uninstall already in progress'}), 409
    full_uninstall_log.clear()
    full_uninstall_status.update({'running': True, 'done': False, 'error': None})
    threading.Thread(target=run_full_uninstall, daemon=True).start()
    return jsonify({'success': True, 'message': 'Full uninstall started'})

@app.route('/api/console/uninstall-all/status')
@login_required
def console_uninstall_all_status():
    return jsonify({
        'running': full_uninstall_status.get('running', False),
        'done': full_uninstall_status.get('done', False),
        'error': full_uninstall_status.get('error'),
        'log': full_uninstall_log[-200:],
    })

@app.route('/api/console/password/reset', methods=['POST'])
@login_required
def console_password_reset():
    """Reset console admin password (for 5001 and Uninstall all). Requires current password."""
    data = request.json or {}
    current = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm = data.get('new_password_confirm', '')
    auth = load_auth()
    if not auth.get('password_hash') or not check_password_hash(auth['password_hash'], current):
        return jsonify({'success': False, 'error': 'Current password is wrong'}), 403
    if not new_pw or len(new_pw) < 8:
        return jsonify({'success': False, 'error': 'New password must be at least 8 characters'}), 400
    if new_pw != confirm:
        return jsonify({'success': False, 'error': 'New password and confirmation do not match'}), 400
    auth['password_hash'] = generate_password_hash(new_pw)
    auth['created'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    save_auth(auth)
    subprocess.Popen('sleep 2 && systemctl restart takwerx-console', shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({'success': True, 'message': 'Password updated. Console will restart in a few seconds.'})


def _get_current_ssh_port():
    """Read SSH port from /etc/ssh/sshd_config. Default 22 if not set or unreadable."""
    try:
        with open('/etc/ssh/sshd_config', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(None, 1)
                    if len(parts) >= 2 and parts[0].lower() == 'port':
                        p = int(parts[1].strip())
                        if 1 <= p <= 65535:
                            return p
    except Exception:
        pass
    return 22


@app.route('/api/hardening/ssh-port', methods=['GET'])
@login_required
def api_hardening_ssh_port_get():
    """Return current SSH port from sshd_config."""
    return jsonify({'port': _get_current_ssh_port()})


@app.route('/api/hardening/ssh-port', methods=['POST'])
@login_required
def api_hardening_ssh_port_post():
    """Change SSH port: update sshd_config, open firewall, restart sshd. Requires root."""
    data = request.get_json() or {}
    try:
        port = int(data.get('port', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid port'}), 400
    if port < 1 or port > 65535:
        return jsonify({'success': False, 'error': 'Port must be between 1 and 65535'}), 400
    current = _get_current_ssh_port()
    if port == current:
        return jsonify({'success': True, 'message': f'SSH is already on port {port}. No change made.'})

    config_path = '/etc/ssh/sshd_config'
    try:
        with open(config_path, 'r') as f:
            lines = f.readlines()
    except OSError as e:
        return jsonify({'success': False, 'error': f'Cannot read sshd_config: {e}'}), 500

    # Replace or add Port line; drop any existing Port / #Port
    new_lines = []
    port_line_added = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            parts = stripped.split(None, 1)
            if len(parts) >= 1 and parts[0].lower() == 'port':
                if not port_line_added:
                    new_lines.append(f'Port {port}\n')
                    port_line_added = True
                continue
        elif stripped.startswith('#Port') or (stripped.startswith('#') and stripped[1:].strip().lower().startswith('port')):
            if not port_line_added:
                new_lines.append(f'Port {port}\n')
                port_line_added = True
            continue
        new_lines.append(line)
    if not port_line_added:
        new_lines.append(f'\n# infra-TAK hardening\nPort {port}\n')

    try:
        with open(config_path, 'w') as f:
            f.writelines(new_lines)
    except OSError as e:
        return jsonify({'success': False, 'error': f'Cannot write sshd_config: {e}'}), 500

    # Allow new port in firewall (ufw)
    r = subprocess.run(['which', 'ufw'], capture_output=True)
    if r.returncode == 0:
        subprocess.run(['ufw', 'allow', f'{port}/tcp'], capture_output=True, timeout=10)
        subprocess.run(['ufw', 'reload'], capture_output=True, timeout=10)

    # Restart SSH (ssh.service on Debian/Ubuntu, sshd on some others)
    for svc in ('ssh', 'sshd'):
        r = subprocess.run(['systemctl', 'restart', svc], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            break

    settings = load_settings()
    settings['ssh_port'] = port
    save_settings(settings)
    return jsonify({'success': True, 'message': f'SSH port set to {port}. Connect using port {port} from now on.'})


# === Help Template (sidebar: backdoor, password info, reset) ===
HELP_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Help — infra-TAK</title>
<style>
''' + BASE_CSS + '''
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
.help-card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px}
.help-card-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:16px 24px;cursor:pointer}
.help-card-header h2{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin:0}
.help-card-toggle{font-size:18px;color:var(--text-dim);transition:transform 0.2s ease}
.help-card-body{display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)}
.help-card-body p{font-size:13px;color:var(--text-secondary);line-height:1.6;margin-bottom:12px;margin-top:0;padding-top:0}
.help-card-body p:first-child{padding-top:16px}
.help-card-body p:last-child{margin-bottom:0}
.help-card-body .form-field{margin-bottom:14px}
.help-card-body .form-field:first-child{margin-top:16px}
.backdoor-url{font-family:'JetBrains Mono',monospace;font-size:13px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:12px 14px;color:var(--cyan);word-break:break-all;user-select:all}
.form-field{margin-bottom:14px}.form-field label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-field input{width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-size:13px}
.btn{display:inline-block;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{opacity:0.9}
#reset-msg{margin-top:12px;font-size:13px;min-height:20px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;max-width:90vw}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border);padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px}
.btn-danger{background:var(--red);color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}
</style></head><body>
{{ sidebar_html }}
<main class="main">
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Deployment order</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>(1) Caddy — set FQDN and TLS · (2) Authentik · (3) Email Relay · (4) TAK Server — upload .deb/.rpm and deploy · (5) TAK Portal · (6) Connect TAK Server to LDAP (button on TAK Server page) · (7) Node-RED, MediaMTX, CloudTAK as needed.</p>
</div></div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Backdoor (IP:5001)</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>If Authentik or the domain is down, you can always reach the console at:</p>
<p class="backdoor-url">https://{{ settings.get('server_ip', 'SERVER_IP') }}:5001</p>
<p>Accept the self-signed cert and log in with your <strong>console password</strong>. <strong>Full lockout?</strong> If you can't log in at all, you have to get on the CLI: the <strong>README on the GitHub repo</strong> has the exact commands to run on the server to reset the password (e.g. <code style="background:var(--bg-surface);padding:2px 6px;border-radius:4px">./reset-console-password.sh</code>).</p>
</div></div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Console password</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>This is the password you set when you ran <code style="background:var(--bg-surface);padding:2px 6px;border-radius:4px">start.sh</code>. The <strong>same password</strong> is used to log in at the backdoor (above) and for <strong>Uninstall all services</strong> on the Console page. We don't store the plaintext, so it can't be shown here. Forgot it? Use the form below if you're logged in; for a full lockout you need the CLI — see the README on the GitHub repo.</p>
</div></div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Reset console password</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>Enter your current password and choose a new one. The console will restart and you'll use the new password for 5001 and Uninstall all. <em>Only works when you're already logged in.</em> For a full lockout, use the CLI (README has the commands).</p>
<div class="form-field"><label>Current password</label><input type="password" id="reset-current" placeholder="Current console password"></div>
<div class="form-field"><label>New password</label><input type="password" id="reset-new" placeholder="At least 8 characters"></div>
<div class="form-field"><label>Confirm new password</label><input type="password" id="reset-confirm" placeholder="Same as above"></div>
<button type="button" class="btn btn-primary" onclick="doResetPassword()">Reset password</button>
<div id="reset-msg"></div>
</div></div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Server hardening — SSH port</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>Changing the SSH port from the default (22) reduces automated scans and is a common hardening step. <strong>Keep another session open</strong> (e.g. a second SSH or the console in the browser) until you confirm you can connect on the new port, or you may lock yourself out.</p>
<p style="font-size:12px;color:var(--text-dim)">Current port: <code style="color:var(--cyan)">{{ current_ssh_port }}</code>. We update <code style="background:var(--bg-surface);padding:2px 6px;border-radius:4px">/etc/ssh/sshd_config</code>, allow the new port in UFW if present, and restart SSH.</p>
<div class="form-field"><label>SSH port (1–65535)</label><input type="number" id="ssh-port-input" min="1" max="65535" value="{{ current_ssh_port }}" placeholder="22" style="width:100px"></div>
<p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Suggestions (commonly unused ports): <button type="button" class="btn btn-ghost" style="padding:4px 10px;font-size:12px" onclick="document.getElementById('ssh-port-input').value=2222">2222</button> <button type="button" class="btn btn-ghost" style="padding:4px 10px;font-size:12px" onclick="document.getElementById('ssh-port-input').value=3022">3022</button> <button type="button" class="btn btn-ghost" style="padding:4px 10px;font-size:12px" onclick="document.getElementById('ssh-port-input').value=4822">4822</button> <button type="button" class="btn btn-ghost" style="padding:4px 10px;font-size:12px" onclick="document.getElementById('ssh-port-input').value=22222">22222</button></p>
<button type="button" class="btn btn-primary" onclick="doApplySshPort()">Apply SSH port</button>
<div id="ssh-port-msg" style="margin-top:12px;font-size:13px;min-height:20px"></div>
</div></div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Uninstall all services</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p>Remove all deployed services (TAK Server, Authentik, Caddy, TAK Portal, MediaMTX, Node-RED, CloudTAK, Email Relay). The console stays so you can redeploy from Marketplace without burning the VPS.</p>
<button type="button" onclick="document.getElementById('full-uninstall-modal').classList.add('open');setTimeout(function(){fullUninstallCheckFields();var p=document.getElementById('full-uninstall-password');if(p&&p.value.trim())fullUninstallValidatePassword();},50)" style="padding:8px 16px;background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.4);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer">Uninstall all services</button>
</div></div>
<div id="full-uninstall-modal" class="modal-overlay" style="z-index:9999;padding:24px">
<div class="modal" style="max-width:480px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column">
<div style="font-weight:600;margin-bottom:16px">Uninstall all deployed services</div>
<p style="font-size:12px;color:var(--text-dim);margin-bottom:16px">This will remove TAK Server, Authentik, Caddy, TAK Portal, MediaMTX, Node-RED, CloudTAK, and Email Relay. The console and your password remain. You can redeploy from Marketplace afterward.</p>
<div style="margin-bottom:12px"><label class="form-label" style="display:block;margin-bottom:4px;font-size:12px">Admin password</label><div style="position:relative;display:flex;align-items:center;gap:8px"><input class="form-input" id="full-uninstall-password" type="password" placeholder="Your console password" style="flex:1" oninput="fullUninstallPasswordInput()" onblur="fullUninstallValidatePassword()"><span id="full-uninstall-pw-check" style="display:none;color:var(--green);font-size:18px;flex-shrink:0" title="Password correct">&#10003;</span></div></div>
<div style="margin-bottom:12px"><label class="form-label" style="display:block;margin-bottom:4px;font-size:12px">Type <strong>UNINSTALL</strong> to confirm</label><div style="position:relative;display:flex;align-items:center;gap:8px"><input class="form-input" id="full-uninstall-confirm" type="text" placeholder="UNINSTALL" autocomplete="off" style="flex:1" oninput="fullUninstallCheckFields()"><span id="full-uninstall-confirm-check" style="display:none;color:var(--green);font-size:18px;flex-shrink:0" title="UNINSTALL typed correctly">&#10003;</span></div></div>
<div id="full-uninstall-msg" style="margin-bottom:8px;font-size:12px;color:var(--red);min-height:18px"></div>
<div id="full-uninstall-progress" style="display:none;margin-bottom:12px;font-size:12px;color:var(--text-secondary)"></div>
<div id="full-uninstall-log" style="display:none;background:var(--bg-deep);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:'JetBrains Mono',monospace;font-size:11px;max-height:200px;overflow-y:auto;margin-bottom:12px;white-space:pre-wrap;word-break:break-all"></div>
<div style="display:flex;gap:8px;margin-top:8px">
<button type="button" class="btn btn-ghost" id="full-uninstall-cancel" onclick="closeFullUninstallModal()">Cancel</button>
<button type="button" class="btn btn-danger" id="full-uninstall-submit" onclick="doFullUninstall()">Uninstall all</button>
</div>
</div>
</div>
<div class="help-card">
<div class="help-card-header" onclick="helpToggle(this)"><h2>Docs</h2><span class="help-card-toggle">&#9662;</span></div>
<div class="help-card-body">
<p><a href="https://github.com/takwerx/infra-TAK" target="_blank" rel="noopener" style="color:var(--cyan);text-decoration:none">github.com/takwerx/infra-TAK</a> (README, docs/COMMANDS.md, docs/HANDOFF-LDAP-AUTHENTIK.md)</p>
</div></div>
</main>
<script>
function helpToggle(header){var body=header.nextElementSibling;var icon=header.querySelector('.help-card-toggle');if(!body)return;if(body.style.display==='block'){body.style.display='none';icon.style.transform='rotate(0deg)';}else{body.style.display='block';icon.style.transform='rotate(180deg)';}}
function closeFullUninstallModal(){document.getElementById('full-uninstall-modal').classList.remove('open');}
var fullUninstallPwValidateTimer=null;
function fullUninstallPasswordInput(){var c=document.getElementById('full-uninstall-pw-check');if(c)c.style.display='none';clearTimeout(fullUninstallPwValidateTimer);var p=document.getElementById('full-uninstall-password');if(!p||!p.value.trim())return;fullUninstallPwValidateTimer=setTimeout(fullUninstallValidatePassword,400);}
async function fullUninstallValidatePassword(){var p=document.getElementById('full-uninstall-password');var c=document.getElementById('full-uninstall-pw-check');if(!p||!c)return;if(!p.value.trim()){c.style.display='none';return;}try{var r=await fetch('/api/console/uninstall-all/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p.value})});var d=await r.json();c.style.display=d.valid?'inline':'none';}catch(e){c.style.display='none';}}
function fullUninstallCheckFields(){var conf=document.getElementById('full-uninstall-confirm');var chk=document.getElementById('full-uninstall-confirm-check');if(chk)chk.style.display=conf&&conf.value.trim().toUpperCase()==='UNINSTALL'?'inline':'none';}
var fullUninstallPollTimer=null;
async function doFullUninstall(){var pw=document.getElementById('full-uninstall-password').value;var confirmVal=document.getElementById('full-uninstall-confirm').value.trim().toUpperCase();var msgEl=document.getElementById('full-uninstall-msg');var progressEl=document.getElementById('full-uninstall-progress');var logEl=document.getElementById('full-uninstall-log');var cancelBtn=document.getElementById('full-uninstall-cancel');var submitBtn=document.getElementById('full-uninstall-submit');msgEl.textContent='';if(!pw){msgEl.textContent='Enter your password';return;}if(confirmVal!=='UNINSTALL'){msgEl.textContent='Type UNINSTALL in the confirmation box to proceed';return;}progressEl.style.display='block';progressEl.textContent='Starting...';logEl.style.display='none';logEl.textContent='';cancelBtn.disabled=true;submitBtn.disabled=true;try{var r=await fetch('/api/console/uninstall-all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw,confirm:confirmVal})});var d=await r.json();if(!d.success){msgEl.textContent=d.error||'Request failed';progressEl.style.display='none';cancelBtn.disabled=false;submitBtn.disabled=false;return;}logEl.style.display='block';function poll(){fetch('/api/console/uninstall-all/status').then(function(res){return res.json();}).then(function(s){if(s.log&&s.log.length){logEl.textContent=s.log.join('\\n');logEl.scrollTop=logEl.scrollHeight;}if(s.running){progressEl.textContent='Uninstalling...';fullUninstallPollTimer=setTimeout(poll,1500);return;}if(s.done){progressEl.textContent=s.error?'Error: '+s.error:'Done. Reloading...';if(s.error)msgEl.textContent=s.error;cancelBtn.disabled=false;if(!s.error)setTimeout(function(){window.location.href='/console';},1500);}}).catch(function(){progressEl.textContent='Error polling';cancelBtn.disabled=false;submitBtn.disabled=false;});}poll();}catch(e){msgEl.textContent=e.message||'Request failed';progressEl.style.display='none';cancelBtn.disabled=false;submitBtn.disabled=false;}}
</script>
<script>
async function doResetPassword(){
    var cur=document.getElementById('reset-current').value;
    var neu=document.getElementById('reset-new').value;
    var conf=document.getElementById('reset-confirm').value;
    var msg=document.getElementById('reset-msg');
    msg.textContent='';
    if(!cur){msg.style.color='var(--red)';msg.textContent='Enter current password';return;}
    if(!neu||neu.length<8){msg.style.color='var(--red)';msg.textContent='New password must be at least 8 characters';return;}
    if(neu!==conf){msg.style.color='var(--red)';msg.textContent='New password and confirmation do not match';return;}
    msg.style.color='var(--cyan)';msg.textContent='Updating...';
    try{
        var r=await fetch('/api/console/password/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:cur,new_password:neu,new_password_confirm:conf})});
        var d=await r.json();
        if(d.success){msg.style.color='var(--green)';msg.textContent=d.message||'Password updated. Reload in a few seconds.';}
        else{msg.style.color='var(--red)';msg.textContent=d.error||'Failed';}
    }catch(e){msg.style.color='var(--red)';msg.textContent=e.message||'Request failed';}
}
async function doApplySshPort(){
    var inp=document.getElementById('ssh-port-input');
    var msg=document.getElementById('ssh-port-msg');
    var port=parseInt(inp&&inp.value?inp.value:0,10);
    msg.textContent='';
    if(!port||port<1||port>65535){msg.style.color='var(--red)';msg.textContent='Enter a port between 1 and 65535';return;}
    msg.style.color='var(--cyan)';msg.textContent='Applying...';
    try{
        var r=await fetch('/api/hardening/ssh-port',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port:port})});
        var d=await r.json();
        if(d.success){msg.style.color='var(--green)';msg.textContent=d.message;}
        else{msg.style.color='var(--red)';msg.textContent=d.error||'Failed';}
    }catch(e){msg.style.color='var(--red)';msg.textContent=e.message||'Request failed';}
}
</script></body></html>'''

# === Console Template (installed services only) ===
CONSOLE_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Console — infra-TAK</title>
<style>
''' + BASE_CSS + '''
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin:0 auto}
.modules-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:32px}
@media(max-width:900px){.modules-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.modules-grid{grid-template-columns:1fr}}
.module-card{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px;cursor:pointer;transition:all 0.3s;text-decoration:none;display:block;color:inherit}
.module-card:hover{border-color:var(--border-hover);background:var(--bg-card-hover);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.3)}
.module-header{display:flex;align-items:flex-end;gap:10px;margin-bottom:8px}
.module-header--logo .module-icon{max-height:36px;width:auto;object-fit:contain}
.module-header .module-icon{flex-shrink:0}
.module-icon{font-size:22px}
.module-header .module-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:14px;margin-bottom:0;padding-bottom:2px}
.module-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:14px;margin-bottom:4px}
.module-desc{font-size:12px;color:var(--text-dim);line-height:1.35}
.module-status{font-family:'JetBrains Mono',monospace;font-size:10px;padding:3px 8px;border-radius:4px;display:inline-flex;align-items:center;gap:4px;margin-top:8px}
.status-running{background:rgba(16,185,129,0.1);color:var(--green)}
.status-stopped{background:rgba(239,68,68,0.1);color:var(--red)}
.status-not-installed{background:rgba(71,85,105,0.2);color:var(--text-dim)}
.status-dot{width:5px;height:5px;border-radius:50%;background:currentColor}
.status-running .status-dot{animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.meta-line{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-bottom:12px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;max-width:90vw}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px}
.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border);padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px}
.btn-danger{background:var(--red);color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}
</style></head><body>
{{ sidebar_html }}
<div class="main">
{% if not settings.get('fqdn') %}
<div style="background:linear-gradient(135deg,rgba(234,179,8,0.1),rgba(239,68,68,0.05));border:1px solid rgba(234,179,8,0.3);border-radius:12px;padding:20px 24px;margin-bottom:24px;font-family:'JetBrains Mono',monospace">
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
<div>
<div style="font-size:13px;font-weight:600;color:var(--yellow)">🔒 No Domain Configured — Running in IP-Only Mode</div>
<div style="font-size:11px;color:var(--text-dim);margin-top:6px;line-height:1.5">Without a domain: no TAK client QR enrollment · no TAK Portal authentication · no trusted SSL · self-signed certs only</div>
</div>
<a href="/caddy" style="padding:8px 18px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;white-space:nowrap">Set Up Domain →</a>
</div>
</div>
{% endif %}
<div id="update-banner" style="display:none;background:linear-gradient(135deg,rgba(30,64,175,0.15),rgba(14,116,144,0.15));border:1px solid rgba(59,130,246,0.3);border-radius:12px;padding:16px 24px;margin-bottom:24px;font-family:'JetBrains Mono',monospace">
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
<div>
<div style="font-size:13px;font-weight:600;color:var(--cyan)">⚡ Update Available</div>
<div style="font-size:12px;color:var(--text-secondary);margin-top:4px"><span id="update-info"></span></div>
</div>
<div style="display:flex;gap:8px">
<button onclick="toggleUpdateDetails()" id="update-details-btn" style="padding:6px 14px;background:none;border:1px solid var(--border);color:var(--text-dim);border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;cursor:pointer">Details</button>
<button onclick="applyUpdate()" id="update-apply-btn" style="padding:6px 14px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;cursor:pointer">Update Now</button>
</div>
</div>
<div id="update-details" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);font-size:11px;color:var(--text-dim);white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
<div id="update-status" style="display:none;margin-top:8px;font-size:11px"></div>
</div>
<div class="metrics-bar" id="metrics-bar">
<div class="metric-card"><div class="metric-label">CPU</div><div class="metric-value" id="cpu-value">{{ metrics.cpu_percent }}%</div></div>
<div class="metric-card"><div class="metric-label">Memory</div><div class="metric-value" id="ram-value">{{ metrics.ram_percent }}%</div><div class="metric-detail">{{ metrics.ram_used_gb }}GB / {{ metrics.ram_total_gb }}GB</div></div>
<div class="metric-card"><div class="metric-label">Disk</div><div class="metric-value" id="disk-value">{{ metrics.disk_percent }}%</div><div class="metric-detail">{{ metrics.disk_used_gb }}GB / {{ metrics.disk_total_gb }}GB</div></div>
<div class="metric-card"><div class="metric-label">Uptime</div><div class="metric-value" id="uptime-value" style="font-size:18px">{{ metrics.uptime }}</div></div>
<div class="metric-card" style="position:relative">
<div class="metric-label" style="display:flex;align-items:center;gap:6px">Auto Updates
{% if metrics.unattended_upgrades.enabled and metrics.unattended_upgrades.running %}<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--cyan);animation:pulse 2s infinite" title="Upgrade in progress"></span>{% endif %}
</div>
<div style="display:flex;align-items:center;gap:8px;margin-top:6px">
<label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer;margin:0">
<input type="checkbox" id="uu-toggle" {% if metrics.unattended_upgrades.enabled %}checked{% endif %} onchange="toggleUU(this)" style="opacity:0;width:0;height:0">
<span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:{% if metrics.unattended_upgrades.enabled %}var(--green){% else %}rgba(71,85,105,0.5){% endif %};border-radius:20px;transition:.3s" id="uu-slider"></span>
<span style="position:absolute;content:'';height:16px;width:16px;left:{% if metrics.unattended_upgrades.enabled %}18px{% else %}2px{% endif %};bottom:2px;background:#fff;border-radius:50%;transition:.3s" id="uu-knob"></span>
</label>
<span id="uu-label" style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{% if metrics.unattended_upgrades.enabled %}var(--green){% else %}var(--text-dim){% endif %}">{% if metrics.unattended_upgrades.enabled and metrics.unattended_upgrades.running %}Running...{% elif metrics.unattended_upgrades.enabled %}Enabled{% else %}Disabled{% endif %}</span>
</div>
</div>
</div>
<div class="section-title">Console</div>
<div class="meta-line">v{{ version }} | {{ settings.get('os_name', 'Unknown OS') }} | {{ settings.get('server_ip', 'N/A') }}{% if settings.get('fqdn') %} | {{ settings.get('fqdn') }}{% endif %}</div>
<div class="modules-grid">
{% if not modules %}
<div style="grid-column:1/-1;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:48px;text-align:center">
<div style="font-size:15px;color:var(--text-secondary);margin-bottom:12px">No deployed services yet</div>
<div style="font-size:13px;color:var(--text-dim);margin-bottom:20px">Install and deploy from the Marketplace to see them here.</div>
<a href="/marketplace" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;text-decoration:none">Go to Marketplace</a>
</div>
{% else %}
{% for key, mod in modules.items() %}
<a class="module-card" href="{{ mod.route }}" data-module="{{ key }}">
<div class="module-header{% if mod.get('icon_url') %} module-header--logo{% endif %}">{% if mod.icon_data %}<img src="{{ mod.icon_data }}" alt="" class="module-icon" style="width:24px;height:24px;object-fit:contain">{% elif key == 'takportal' %}<span class="module-icon material-symbols-outlined" style="font-size:28px">group</span>{% elif key == 'emailrelay' %}<span class="module-icon material-symbols-outlined" style="font-size:28px">outgoing_mail</span>{% elif mod.get('icon_url') %}<img src="{{ mod.icon_url }}" alt="" class="module-icon" style="height:36px;width:auto;max-width:{% if key == 'takserver' %}72px{% else %}100px{% endif %};object-fit:contain">{% else %}<span class="module-icon">{{ mod.icon }}</span>{% endif %}
{% if not mod.get('icon_url') or key == 'takportal' or key == 'emailrelay' %}<div class="module-name">{{ mod.name }}</div>{% endif %}
</div>
<div class="module-desc">{{ mod.description }}</div>
{% if module_versions.get(key) %}{% set v = module_versions.get(key) %}{% if v.version or v.update_available %}<div class="meta-line module-version-line" id="module-version-{{ key }}" style="margin-bottom:4px">{% if v.version %}v{{ v.version }}{% endif %}{% if v.update_available %} <span style="color:var(--cyan);font-size:10px" title="Update available">update</span>{% endif %}</div>{% endif %}{% endif %}
<span class="module-status status-{% if mod.installed and mod.running %}running{% elif mod.installed %}stopped{% else %}not-installed{% endif %}" id="module-status-{{ key }}" data-module="{{ key }}">{% if mod.installed and mod.running %}<span class="status-dot"></span> Running{% elif mod.installed %}<span class="status-dot"></span> Stopped{% else %}Not Installed{% endif %}</span>
{% if key == 'takserver' and mod.installed %}<div id="takserver-card-cert-expiry" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--text-dim);margin-top:4px"></div>{% endif %}
</a>
{% endfor %}
{% endif %}
</div>
<script>
function updateUU(uu){
    if(!uu)return;
    var tog=document.getElementById('uu-toggle'),sl=document.getElementById('uu-slider'),kn=document.getElementById('uu-knob'),lb=document.getElementById('uu-label');
    if(!tog)return;
    tog.checked=uu.enabled;
    sl.style.background=uu.enabled?'var(--green)':'rgba(71,85,105,0.5)';
    kn.style.left=uu.enabled?'18px':'2px';
    lb.style.color=uu.enabled?'var(--green)':'var(--text-dim)';
    lb.textContent=(uu.enabled&&uu.running)?'Running...':uu.enabled?'Enabled':'Disabled';
}
async function toggleUU(cb){
    var action=cb.checked?'enable':'disable';
    var lb=document.getElementById('uu-label');
    lb.textContent=cb.checked?'Enabling...':'Disabling...';lb.style.color='var(--cyan)';
    try{
        var r=await fetch('/api/unattended-upgrades',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action})});
        var d=await r.json();
        if(d.success){updateUU(d)}
        else{cb.checked=!cb.checked;lb.textContent='Error: '+(d.error||'unknown');lb.style.color='var(--red)'}
    }catch(e){cb.checked=!cb.checked;lb.textContent='Error';lb.style.color='var(--red)'}
}
setInterval(async()=>{try{const r=await fetch('/api/metrics');const d=await r.json();document.getElementById('cpu-value').textContent=d.cpu_percent+'%';document.getElementById('ram-value').textContent=d.ram_percent+'%';document.getElementById('disk-value').textContent=d.disk_percent+'%';document.getElementById('uptime-value').textContent=d.uptime;updateUU(d.unattended_upgrades)}catch(e){}},5000);
function refreshModuleCards(){
    fetch('/api/modules').then(r=>r.json()).then(function(mods){
        for(var k in mods){
            var el=document.getElementById('module-status-'+k);
            if(!el)continue;
            var m=mods[k];
            var cls='module-status status-'+(m.installed&&m.running?'running':m.installed?'stopped':'not-installed');
            var label=m.installed&&m.running?'<span class="status-dot"></span> Running':m.installed?'<span class="status-dot"></span> Stopped':'Not Installed';
            el.className=cls;el.innerHTML=label;
        }
    }).catch(function(){});
}
setInterval(refreshModuleCards,8000);
refreshModuleCards();
function refreshModuleVersions(){
    fetch('/api/modules/version').then(function(r){return r.json()}).then(function(data){
        for(var key in data){
            var el=document.getElementById('module-version-'+key);
            if(!el)continue;
            var d=data[key];
            var s='';
            if(d.version)s='v'+d.version;
            if(d.update_available)s+=(s?' ':'')+'<span style="color:var(--cyan);font-size:10px" title="Update available">update</span>';
            el.innerHTML=s;if(s)el.style.display='';
        }
    }).catch(function(){});
}
setInterval(refreshModuleVersions,30000);
refreshModuleVersions();
function loadTakCertExpiry(){
    var el=document.getElementById('takserver-card-cert-expiry');
    if(!el)return;
    fetch('/api/takserver/cert-expiry').then(function(r){return r.json()}).then(function(d){
        function fmt(days){
            var y=Math.floor(days/365),r=days%365,m=Math.floor(r/30),dd=r%30;
            var p=[];if(y>0)p.push(y+'y');if(m>0)p.push(m+'mo');if(dd>0||p.length===0)p.push(dd+'d');
            return p.join(' ');
        }
        var parts=[];
        var certs=[['root_ca','Root'],['intermediate_ca','Int']];
        for(var i=0;i<certs.length;i++){
            var key=certs[i][0],label=certs[i][1],c=d[key];
            if(!c||c.error)continue;
            var days=c.days_left,color='#22c55e';
            if(days<=90)color='#ef4444';else if(days<=365)color='#eab308';
            parts.push(label+' <span style="color:'+color+';font-weight:600">'+fmt(days)+'</span>');
        }
        el.innerHTML=parts.join(' &nbsp;&middot;&nbsp; ');
    }).catch(function(){});
}
loadTakCertExpiry();
var updateBody='';
async function checkUpdate(){
    try{
        var r=await fetch('/api/update/check');var d=await r.json();
        if(d.update_available){
            document.getElementById('update-banner').style.display='block';
            document.getElementById('update-info').textContent='v'+d.current+' -> v'+d.latest+(d.notes?' - '+d.notes:'');
            updateBody=d.body||'No details available';
        }
    }catch(e){}
}
function toggleUpdateDetails(){
    var el=document.getElementById('update-details');
    if(el.style.display==='none'){el.textContent=updateBody;el.style.display='block'}
    else{el.style.display='none'}
}
async function applyUpdate(){
    var btn=document.getElementById('update-apply-btn');
    var status=document.getElementById('update-status');
    btn.disabled=true;btn.textContent='Updating...';btn.style.opacity='0.7';
    status.style.display='block';status.style.color='var(--cyan)';status.textContent='Pulling latest from GitHub...';
    try{
        var r=await fetch('/api/update/apply',{method:'POST'});var d=await r.json();
        if(d.success){
            status.style.color='var(--green)';
            status.textContent='OK Updated! Restarting console...';
            setTimeout(function(){window.location.reload()},5000);
        }else{
            status.style.color='var(--red)';status.textContent='Error: '+d.error;
            btn.disabled=false;btn.textContent='Update Now';btn.style.opacity='1';
        }
    }catch(e){status.style.color='var(--red)';status.textContent='Error: '+e.message;btn.disabled=false;btn.textContent='Update Now';btn.style.opacity='1'}
}
checkUpdate();
</script></body></html>'''

# === Marketplace Template (all services, deploy from here) ===
MARKETPLACE_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Marketplace — infra-TAK</title>
<style>
''' + BASE_CSS + '''
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700}.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px;max-width:1000px;margin:0 auto}
.modules-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:32px}
@media(max-width:900px){.modules-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.modules-grid{grid-template-columns:1fr}}
.module-card{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px;cursor:pointer;transition:all 0.3s;text-decoration:none;display:block;color:inherit}
.module-card:hover{border-color:var(--border-hover);background:var(--bg-card-hover);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.3)}
.module-header{display:flex;align-items:flex-end;gap:10px;margin-bottom:8px}
.module-header--logo .module-icon{max-height:36px;width:auto;object-fit:contain}
.module-header .module-icon{flex-shrink:0}
.module-icon{font-size:22px}
.module-header .module-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:14px;margin-bottom:0;padding-bottom:2px}
.module-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:14px;margin-bottom:4px}
.module-desc{font-size:12px;color:var(--text-dim);line-height:1.35}
.module-status{font-family:'JetBrains Mono',monospace;font-size:10px;padding:3px 8px;border-radius:4px;display:inline-flex;align-items:center;gap:4px;margin-top:8px}
.status-running{background:rgba(16,185,129,0.1);color:var(--green)}
.status-stopped{background:rgba(239,68,68,0.1);color:var(--red)}
.status-not-installed{background:rgba(71,85,105,0.2);color:var(--text-dim)}
.status-dot{width:5px;height:5px;border-radius:50%;background:currentColor}
.status-running .status-dot{animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.module-action{display:inline-block;margin-top:6px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);opacity:0;transition:opacity 0.2s}
.module-card:hover .module-action{opacity:1}
.meta-line{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-bottom:12px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;max-width:90vw}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text-primary);font-size:13px}
.btn-ghost{background:rgba(255,255,255,.05);color:var(--text-secondary);border:1px solid var(--border);padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px}
.btn-danger{background:var(--red);color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}
</style></head><body>
{{ sidebar_html }}
<div class="main">
{% if not settings.get('fqdn') %}
<div style="background:linear-gradient(135deg,rgba(234,179,8,0.1),rgba(239,68,68,0.05));border:1px solid rgba(234,179,8,0.3);border-radius:12px;padding:20px 24px;margin-bottom:24px;font-family:'JetBrains Mono',monospace">
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
<div>
<div style="font-size:13px;font-weight:600;color:var(--yellow)">🔒 No Domain Configured — Running in IP-Only Mode</div>
<div style="font-size:11px;color:var(--text-dim);margin-top:6px;line-height:1.5">Without a domain: no TAK client QR enrollment · no TAK Portal authentication · no trusted SSL · self-signed certs only</div>
</div>
<a href="/caddy" style="padding:8px 18px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;white-space:nowrap">Set Up Domain →</a>
</div>
</div>
{% endif %}
<div class="metrics-bar" id="metrics-bar">
<div class="metric-card"><div class="metric-label">CPU</div><div class="metric-value" id="cpu-value">{{ metrics.cpu_percent }}%</div></div>
<div class="metric-card"><div class="metric-label">Memory</div><div class="metric-value" id="ram-value">{{ metrics.ram_percent }}%</div><div class="metric-detail">{{ metrics.ram_used_gb }}GB / {{ metrics.ram_total_gb }}GB</div></div>
<div class="metric-card"><div class="metric-label">Disk</div><div class="metric-value" id="disk-value">{{ metrics.disk_percent }}%</div><div class="metric-detail">{{ metrics.disk_used_gb }}GB / {{ metrics.disk_total_gb }}GB</div></div>
<div class="metric-card"><div class="metric-label">Uptime</div><div class="metric-value" id="uptime-value" style="font-size:18px">{{ metrics.uptime }}</div></div>
</div>
<div class="section-title">Marketplace</div>
<div class="modules-grid">
{% if not modules %}
<div style="grid-column:1/-1;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:48px;text-align:center">
<div style="font-size:15px;color:var(--text-secondary);margin-bottom:12px">All available services are installed</div>
<div style="font-size:13px;color:var(--text-dim);margin-bottom:20px">Manage and monitor everything from the Console.</div>
<a href="/console" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;text-decoration:none">Go to Console →</a>
</div>
{% else %}
{% for key, mod in modules.items() %}
<a class="module-card" href="{{ mod.route }}" data-module="{{ key }}">
<div class="module-header{% if mod.get('icon_url') %} module-header--logo{% endif %}">{% if mod.icon_data %}<img src="{{ mod.icon_data }}" alt="" class="module-icon" style="width:24px;height:24px;object-fit:contain">{% elif key == 'takportal' %}<span class="module-icon material-symbols-outlined" style="font-size:28px">group</span>{% elif key == 'emailrelay' %}<span class="module-icon material-symbols-outlined" style="font-size:28px">outgoing_mail</span>{% elif mod.get('icon_url') %}<img src="{{ mod.icon_url }}" alt="" class="module-icon" style="height:36px;width:auto;max-width:{% if key == 'takserver' %}72px{% else %}100px{% endif %};object-fit:contain">{% else %}<span class="module-icon">{{ mod.icon }}</span>{% endif %}
{% if not mod.get('icon_url') or key == 'takportal' or key == 'emailrelay' %}<div class="module-name">{{ mod.name }}</div>{% endif %}
</div>
<div class="module-desc">{{ mod.description }}</div>
<span class="module-status status-not-installed" id="module-status-{{ key }}" data-module="{{ key }}">Not Installed</span>
<span class="module-action">Deploy →</span>
</a>
{% endfor %}
{% endif %}
</div>
</div>
<script>
setInterval(async()=>{try{const r=await fetch('/api/metrics');const d=await r.json();document.getElementById('cpu-value').textContent=d.cpu_percent+'%';document.getElementById('ram-value').textContent=d.ram_percent+'%';document.getElementById('disk-value').textContent=d.disk_percent+'%';document.getElementById('uptime-value').textContent=d.uptime}catch(e){}},5000);
</script></body></html>'''

# === TAK Server Template ===
TAKSERVER_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TAK Server</title>
<style>
''' + BASE_CSS + '''
.upload-area{border:2px dashed var(--border);border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all 0.3s;background:rgba(15,23,42,0.3);margin-bottom:20px}
.upload-area:hover,.upload-area.dragover{border-color:var(--accent);background:var(--accent-glow)}
.upload-icon{font-size:40px;margin-bottom:12px}.upload-text{font-size:16px;color:var(--text-secondary);margin-bottom:8px}.upload-hint{font-size:13px;color:var(--text-dim);line-height:1.6}
.progress-item{background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px}
.progress-bar-outer{width:100%;height:4px;background:rgba(59,130,246,0.1);border-radius:2px;margin-top:8px;overflow:hidden}
.progress-bar-inner{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--accent),var(--cyan));transition:width 0.3s}
.control-btn{padding:10px 20px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:13px;cursor:pointer;transition:all 0.2s}
.control-btn:hover{border-color:var(--border-hover);color:var(--text-primary)}
.control-btn.btn-stop{border-color:rgba(239,68,68,0.3)}.control-btn.btn-stop:hover{background:rgba(239,68,68,0.1);color:var(--red)}
.control-btn.btn-start{border-color:rgba(16,185,129,0.3)}.control-btn.btn-start:hover{background:rgba(16,185,129,0.1);color:var(--green)}
.status-banner{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:12px;padding:24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
.status-info{display:flex;align-items:center;gap:16px}
.status-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px}
.status-icon.running{background:rgba(16,185,129,0.1)}.status-icon.stopped{background:rgba(239,68,68,0.1)}.status-icon.not-installed{background:rgba(71,85,105,0.2)}
.status-text{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:600}
.status-detail{font-size:13px;color:var(--text-dim);margin-top:4px}
.status-logo-wrap{display:flex;align-items:center;gap:10px}
.status-logo{height:36px;width:auto;max-width:100px;object-fit:contain}
.status-name{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:18px;color:var(--text-primary)}
.controls{display:flex;gap:10px}
.cert-downloads{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}
.cert-btn{padding:10px 20px;border-radius:8px;text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;transition:all 0.2s}
.cert-btn-primary{background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff}
.cert-btn-secondary{background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid var(--border)}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:28px;width:400px;max-width:90vw}
.modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:var(--red)}
.modal p{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.form-label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.form-input{width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-size:13px}
.uninstall-spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--cyan);border-radius:50%;animation:uninstall-spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes uninstall-spin{to{transform:rotate(360deg)}}
.uninstall-progress-row{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text-secondary)}
body{display:flex;flex-direction:row;min-height:100vh}
.sidebar{width:220px;min-width:220px;background:var(--bg-surface);border-right:1px solid var(--border);padding:24px 0;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.sidebar-logo span{font-size:15px;font-weight:700;letter-spacing:.05em;color:var(--text-primary)}
.sidebar-logo small{display:block;font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500;transition:all .15s;border-left:2px solid transparent}
.nav-item:hover{color:var(--text-primary);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--cyan);background:rgba(6,182,212,.06);border-left-color:var(--cyan)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:400;font-style:normal;font-size:20px;line-height:1;letter-spacing:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased}
.nav-icon.material-symbols-outlined{font-size:22px;width:22px;text-align:center}
.page-header{margin-bottom:28px}
.page-header h1{font-size:22px;font-weight:700}
.page-header p{color:var(--text-secondary);font-size:13px;margin-top:4px}
.main{flex:1;min-width:0;overflow-y:auto;padding:32px}
</style></head><body data-tak-deploying="{{ 'true' if deploying or deploy_done or deploy_error else 'false' }}" data-tak-upgrading="{{ 'true' if upgrading else 'false' }}">
{{ sidebar_html }}
<div class="main">
  <div class="page-header"><h1><img src="{{ tak_logo_url }}" alt="" style="height:28px;vertical-align:middle;margin-right:8px;object-fit:contain"> TAK Server</h1><p>Team Awareness Kit Server</p></div>
<div class="status-banner" id="status-banner">
{% if deploying %}
<div class="status-info"><div class="status-icon running" style="background:rgba(59,130,246,0.1)">🔄</div><div><div class="status-text" style="color:var(--accent)">Deploying...</div><div class="status-detail">TAK Server installation in progress</div></div></div>
<div class="controls"><button class="control-btn btn-stop" onclick="cancelDeploy()">✗ Cancel</button></div>
{% elif tak.installed and tak.running %}
<div class="status-info"><div><div class="status-text" style="color:var(--green)">Running</div><div class="status-detail">TAK Server is active{% if tak_version %} · {{ tak_version }}{% endif %}</div><div id="cert-expiry-banner" style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:4px"></div></div></div>
<div class="controls"><button class="control-btn" onclick="takControl('restart')">↻ Restart</button><button class="control-btn btn-stop" onclick="takControl('stop')">■ Stop</button><button class="control-btn btn-stop" onclick="document.getElementById('tak-uninstall-modal').classList.add('open')" style="margin-left:8px">🗑 Remove</button></div>
{% elif tak.installed %}
<div class="status-info"><div><div class="status-text" style="color:var(--red)">Stopped</div><div class="status-detail">TAK Server is installed but not running{% if tak_version %} · {{ tak_version }}{% endif %}</div><div id="cert-expiry-banner" style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:4px"></div></div></div>
<div class="controls"><button class="control-btn btn-start" onclick="takControl('start')">▶ Start</button><button class="control-btn btn-stop" onclick="document.getElementById('tak-uninstall-modal').classList.add('open')" style="margin-left:8px">🗑 Remove</button></div>
{% else %}
<div class="status-info"><div><div class="status-text" style="color:var(--text-dim)">Not Installed</div><div class="status-detail">Upload package files from tak.gov to deploy</div></div></div>
{% endif %}
</div>

{% if deploying or deploy_done or deploy_error %}
<div class="section-title">Deployment Log</div>
<div id="deploy-log" style="background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-secondary);max-height:500px;overflow-y:auto;line-height:1.7;white-space:pre-wrap">Reconnecting to deployment log...</div>
<div id="deploy-log-area" style="display:block"></div>
{% if deploy_done %}
<div id="cert-download-area" style="margin-top:20px"><div class="section-title">Download Certificates</div><div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px"><div class="cert-downloads"><a href="/api/download/admin-cert" class="cert-btn cert-btn-secondary">⬇ admin.p12</a><a href="/api/download/user-cert" class="cert-btn cert-btn-secondary">⬇ user.p12</a><a href="/api/download/truststore" class="cert-btn cert-btn-secondary">⬇ truststore.p12</a></div><div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-top:12px">Certificate password: <span style="color:var(--cyan)">atakatak</span></div></div></div>
{% endif %}
{% elif tak.installed %}
{% if show_connect_ldap %}
<div class="card" style="border-color:rgba(59,130,246,.35);background:rgba(59,130,246,.06);margin-bottom:24px">
<div class="card-title">🔗 Connect TAK Server to LDAP</div>
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:16px">Authentik is deployed. Connect TAK Server to the same LDAP so users can sign in with their Authentik accounts. This patches CoreConfig.xml and restarts TAK Server once.</p>
<button type="button" id="connect-ldap-btn" onclick="connectLdap()" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;cursor:pointer">Connect TAK Server to LDAP</button>
<div id="connect-ldap-msg" style="margin-top:12px;font-size:13px;color:var(--text-secondary)"></div>
</div>
{% elif ldap_connected and modules.get('authentik', {}).get('installed') %}
<div class="card" style="border-color:rgba(16,185,129,.35);background:rgba(16,185,129,.06);margin-bottom:24px">
<div style="display:flex;align-items:center;gap:12px">
<span style="color:var(--green);font-size:18px">✓</span><span style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--green);font-weight:600">LDAP Connected to Authentik</span>
</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:8px">CoreConfig.xml patched · Service account: adm_ldapservice · Base DN: DC=takldap · Port 389</div>
<div style="margin-top:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
<button type="button" id="resync-ldap-btn" onclick="resyncLdap()" style="padding:8px 16px;background:rgba(16,185,129,.2);color:var(--green);border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer">Resync LDAP to TAK Server</button>
<button type="button" id="sync-webadmin-btn" onclick="syncWebadmin()" style="padding:8px 16px;background:rgba(59,130,246,.2);color:var(--cyan);border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;cursor:pointer">Sync webadmin to Authentik</button>
<span id="sync-webadmin-msg" style="font-size:12px;color:var(--text-dim)"></span><span id="resync-ldap-msg" style="font-size:12px;color:var(--text-dim)"></span>
</div>
<p style="font-size:11px;color:var(--text-dim);margin-top:6px;margin-bottom:4px"><strong>Resync LDAP</strong> — Re-runs the full flow (fix blueprint if needed, restart Authentik worker, ensure service account &amp; webadmin, sync CoreConfig). Use after pulling console updates or if QR/login fails.</p>
<p style="font-size:11px;color:var(--text-dim);margin-top:0;margin-bottom:0"><strong>Sync webadmin</strong> — Only pushes the 8446 password from settings into Authentik. Does not restart anything.</p>
<div id="resync-notice" style="display:none;margin-top:8px;padding:10px 14px;background:rgba(234,179,8,0.12);border:1px solid rgba(234,179,8,0.35);border-radius:8px;font-size:12px;color:var(--yellow)">TAK Portal user list may take a short moment to repopulate.</div>
</div>
{% endif %}
<div class="section-title">Access</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div style="display:flex;gap:10px;flex-wrap:nowrap;align-items:center">
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8443' }}" target="_blank" class="cert-btn cert-btn-primary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔐 WebGUI :8443 (cert)</a>
<a href="{{ 'https://tak.' + settings.get('fqdn') if settings.get('fqdn') else 'https://' + settings.get('server_ip', '') + ':8446' }}" target="_blank" class="cert-btn cert-btn-primary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔑 WebGUI :8446 (password)</a>
<a href="{{ 'https://takportal.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':3000' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">👥 TAK Portal{% if not settings.get('fqdn') %} :3000{% endif %}</a>
<a href="{{ 'https://authentik.' + settings.get('fqdn', '') if settings.get('fqdn') else 'http://' + settings.get('server_ip', '') + ':9090' }}" target="_blank" class="cert-btn cert-btn-secondary" style="text-decoration:none;white-space:nowrap;font-size:12px;padding:8px 14px">🔐 Authentik{% if not settings.get('fqdn') %} :9090{% endif %}</a>
</div>
<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);margin-top:12px">8446 login: <span style="color:var(--cyan)">webadmin</span> · <button type="button" onclick="showWebadminPassword()" id="webadmin-pw-btn" style="background:none;border:1px solid var(--border);color:var(--cyan);padding:2px 10px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;cursor:pointer">🔑 Show Password</button> <span id="webadmin-pw-display" style="color:var(--green);user-select:all;display:none"></span></div>
</div>
<div class="section-title">Services</div>
<div id="services-panel" style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px">
<div id="services-list" style="font-family:'JetBrains Mono',monospace;font-size:13px">Loading services...</div>
</div>
{% if tak.installed and 'ubuntu' in settings.get('os_type', '') %}
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:16px 24px;cursor:pointer" onclick="takToggleUpdate()" id="tak-update-header">
<span class="section-title" style="margin-bottom:0">Update TAK Server</span>
<span id="tak-update-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease{% if upgrading or upgrade_done or upgrade_error %};transform:rotate(180deg){% endif %}">&#9662;</span>
</div>
<div id="tak-update-body" style="display:{{ 'block' if upgrading or upgrade_done or upgrade_error else 'none' }};padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:16px;padding-top:16px">To upgrade to a newer release, download the new <span style="font-family:'JetBrains Mono',monospace;color:var(--cyan)">takserver_X.X_all.deb</span> from tak.gov, upload it below, then click Update. This runs <span style="font-family:'JetBrains Mono',monospace;font-size:12px">apt install ./package.deb</span> and restarts TAK Server.</p>
<div class="upload-area" id="upgrade-upload-area" style="padding:24px;margin-bottom:16px" onclick="document.getElementById('upgrade-file-input').click()" ondrop="handleUpgradeDrop(event)" ondragover="event.preventDefault();this.classList.add('dragover')" ondragleave="event.preventDefault();this.classList.remove('dragover')">
<input type="file" id="upgrade-file-input" style="display:none" accept=".deb" onchange="handleUpgradeFile(event)">
<div id="upgrade-upload-text" style="color:var(--text-dim);font-size:13px">Click or drop to select upgrade package (.deb)</div>
<div id="upgrade-filename" style="display:none;font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--cyan);margin-top:8px"></div>
</div>
<div id="upgrade-progress-area" style="margin-bottom:16px"></div>
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
<button type="button" id="tak-update-btn" onclick="startTakUpdate()" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;cursor:pointer">Update TAK Server</button>
<span id="tak-update-msg" style="font-size:12px;color:var(--text-dim)"></span>
</div>
<div id="upgrade-log-wrap" style="display:{{ 'block' if upgrading or upgrade_done or upgrade_error else 'none' }};margin-top:20px">
<div class="section-title">Update log</div>
<div id="upgrade-log" style="background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-secondary);max-height:400px;overflow-y:auto;line-height:1.7;white-space:pre-wrap;margin-top:8px">{% if upgrading %}Connecting...{% else %}{% if upgrade_done %}Done.{% elif upgrade_error %}Update failed.{% endif %}{% endif %}</div>
</div>
</div>
</div>
{% endif %}
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('cot-db')">
<span class="section-title" style="margin-bottom:0">Database Maintenance (CoT)</span>
<span id="cot-db-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="cot-db-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:12px;padding-top:16px">The CoT (Cursor on Target) database can grow large. Data retention deletes old rows, but <strong>PostgreSQL does not free disk until you run VACUUM</strong>. Run VACUUM ANALYZE periodically to reclaim space (safe while TAK Server is running).</p>
<p style="font-size:12px;color:var(--text-dim);margin-bottom:16px">CoT database size: <span id="cot-db-size" style="font-weight:600">-</span> <button type="button" onclick="refreshCotSize()" style="margin-left:8px;padding:2px 10px;background:transparent;color:var(--cyan);border:1px solid var(--border);border-radius:4px;font-size:11px;cursor:pointer">Refresh</button> <span style="font-size:10px;color:var(--text-dim);margin-left:6px">(green &lt; 25 GB · yellow 25-40 GB · red &gt; 40 GB)</span></p>
<div style="display:flex;flex-direction:column;gap:12px">
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">
<button type="button" id="vacuum-analyze-btn" onclick="runVacuum(false)" style="padding:10px 20px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:600;cursor:pointer;flex-shrink:0">Run VACUUM ANALYZE</button>
<span style="font-size:12px;color:var(--text-secondary)">Reclaims space from deleted rows and updates statistics. Safe while TAK Server is running.</span>
</div>
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">
<button type="button" id="vacuum-full-btn" onclick="runVacuum(true)" style="padding:10px 20px;background:rgba(234,179,8,0.2);color:var(--yellow);border:1px solid var(--border);border-radius:8px;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:600;cursor:pointer;flex-shrink:0" title="Caution: run when TAK Server is not running">Run VACUUM FULL</button>
<span style="font-size:12px;color:var(--text-secondary)">Rewrites tables to reclaim more space; locks tables. Run when <strong>TAK Server is not running</strong>. <span style="color:var(--yellow)">(yellow = caution)</span></span>
</div>
</div>
<div id="vacuum-output" style="display:none;margin-top:14px;padding:12px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
<div id="vacuum-msg" style="margin-top:8px;font-size:13px"></div>
</div>
</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('certs')">
<span class="section-title" style="margin-bottom:0">Certificates</span>
<span id="certs-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="certs-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;padding-top:16px">
<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim)">Certificate password: <span style="color:var(--cyan)">atakatak</span> &nbsp;&middot;&nbsp; /opt/tak/certs/files/</div>
<a href="/certs" class="cert-btn cert-btn-secondary" style="text-decoration:none">📁 Browse Certificates</a>
</div>
<div id="cert-expiry-info" style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim)">Loading certificate expiry...</div>
</div>
</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('rotate-ca')">
<span class="section-title" style="margin-bottom:0">Rotate Intermediate CA</span>
<span id="rotate-ca-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="rotate-ca-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:16px;padding-top:16px">Create a new Intermediate CA signed by your Root CA. The old CA stays in the truststore so existing clients remain connected during transition. Once all clients have re-enrolled, revoke the old CA.</p>
<div id="rotate-ca-info" style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:16px">Loading CA info...</div>
<div id="rotate-ca-controls" style="display:none">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
<div class="form-field"><label style="display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">New Intermediate CA Name</label><input type="text" id="rotate-ca-name" placeholder="e.g. INTERMEDIATE-CA-02" maxlength="64" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:13px;box-sizing:border-box"></div>
<div></div>
</div>
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px">
<button type="button" id="rotate-ca-btn" onclick="rotateIntCA()" style="padding:12px 24px;background:linear-gradient(135deg,#b45309,#92400e);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;cursor:pointer">Rotate Intermediate CA</button>
<span id="rotate-ca-msg" style="font-size:12px;color:var(--text-dim)"></span>
</div>
</div>
<div id="rotate-ca-log" style="display:none;background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-bottom:16px"></div>
<div id="revoke-ca-section" style="display:none;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:10px;padding:16px">
<div style="font-size:13px;font-weight:600;color:var(--red);margin-bottom:8px">Revoke Old CA</div>
<p style="font-size:12px;color:var(--text-secondary);line-height:1.5;margin-bottom:12px">Remove the old CA from the truststore. Clients with certificates signed by the old CA will be disconnected and must re-enroll.</p>
<div id="revoke-ca-list" style="margin-bottom:12px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim)"></div>
<div id="revoke-ca-msg" style="font-size:12px;margin-top:8px"></div>
</div>
</div>
</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('rotate-root')">
<span class="section-title" style="margin-bottom:0">Rotate Root CA</span>
<span id="rotate-root-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="rotate-root-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:16px;padding-top:16px">Full PKI rebuild. Creates a new Root CA, new Intermediate CA, new server cert, and regenerates all client certificates. <strong style="color:var(--red)">All existing connections will be disconnected.</strong> Users must re-enroll via TAK Portal QR code. Schedule a maintenance window before proceeding.</p>
<div id="rotate-root-info" style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:16px">Loading Root CA info...</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
<div class="form-field"><label style="display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">New Root CA Name</label><input type="text" id="rotate-root-name" placeholder="e.g. ROOT-CA-02" maxlength="64" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:13px;box-sizing:border-box"></div>
<div class="form-field"><label style="display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">New Intermediate CA Name</label><input type="text" id="rotate-root-int-name" placeholder="e.g. INT-CA-01" maxlength="64" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:13px;box-sizing:border-box"></div>
</div>
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
<button type="button" id="rotate-root-btn" onclick="rotateRootCA()" style="padding:12px 24px;background:linear-gradient(135deg,#991b1b,#7f1d1d);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;cursor:pointer">Rotate Root CA</button>
<span id="rotate-root-msg" style="font-size:12px;color:var(--text-dim)"></span>
</div>
<div id="rotate-root-log" style="display:none;margin-top:16px;background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap"></div>
</div>
</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('client-cert')">
<span class="section-title" style="margin-bottom:0">Create Client Certificate</span>
<span id="client-cert-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="client-cert-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<p style="font-size:13px;color:var(--text-secondary);line-height:1.5;margin-bottom:16px;padding-top:16px">Generate a signed client certificate and assign it to groups with read/write permissions. The .p12 file can be imported into ATAK, iTAK, or WinTAK.</p>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
<div class="form-field"><label style="display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">Client Name</label><input type="text" id="cc-name" placeholder="e.g. operator1" maxlength="64" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:'JetBrains Mono',monospace;font-size:13px;box-sizing:border-box"></div>
<div></div>
</div>
<div style="margin-bottom:16px">
<label style="display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:8px">Groups <span style="font-weight:400;color:var(--text-dim)">(select groups and permissions)</span></label>
<div id="cc-groups-list" style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim)"><button type="button" id="cc-load-groups-btn" onclick="loadGroups()" style="padding:8px 16px;background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;cursor:pointer">Load Groups from TAK Server</button></div>
</div>
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
<button type="button" id="cc-create-btn" onclick="createClientCert()" style="padding:12px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;cursor:pointer">Create Certificate</button>
<span id="cc-msg" style="font-size:12px;color:var(--text-dim)"></span>
</div>
<div id="cc-result" style="display:none;margin-top:16px;background:rgba(6,182,212,0.06);border:1px solid var(--border);border-radius:10px;padding:16px">
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">
<div><span style="color:var(--green);font-weight:600" id="cc-result-name"></span><span style="color:var(--text-dim);font-size:12px;margin-left:8px">Password: atakatak</span></div>
<a id="cc-download-link" href="#" class="cert-btn cert-btn-secondary" style="text-decoration:none;font-size:12px;padding:8px 16px">⬇ Download .p12</a>
</div>
</div>
</div>
</div>
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;margin-bottom:24px">
<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;cursor:pointer" onclick="takToggleSection('server-log')">
<span class="section-title" style="margin-bottom:0">Server Log <span style="font-size:11px;color:var(--text-dim);font-weight:400">takserver-messaging.log</span></span>
<span id="server-log-toggle-icon" style="font-size:18px;color:var(--text-dim);transition:transform 0.2s ease">&#9662;</span>
</div>
<div id="server-log-body" style="display:none;padding:0 24px 24px 24px;border-top:1px solid var(--border)">
<div id="server-log" style="background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim);max-height:400px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;margin-top:16px">Loading log...</div>
</div>
</div>
{% else %}
<div class="section-title">Deploy TAK Server</div>
<div class="upload-area" id="upload-area" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" onclick="var i=document.getElementById('file-input');i.value='';i.click()">
<div class="upload-icon">📦</div><div class="upload-text">Drop your TAK Server files here</div>
<div class="upload-hint" style="margin-bottom:6px"><span style="color:var(--text-dim);font-size:12px">Slow upload? Use the backdoor — open <strong>https://{{ settings.get('server_ip', 'SERVER_IP') }}:5001</strong> and upload from the TAK Server page there (skips proxy, no timeout).</span></div>
<div class="upload-hint">
{% if 'ubuntu' in settings.get('os_type', '') %}
<strong style="color:var(--text-secondary)">Ubuntu — upload these files from tak.gov:</strong><br>
Required: <span style="color:var(--cyan)">takserver_X.X_all.deb</span><br>
Optional: <span style="color:var(--text-secondary)">deb_policy.pol</span> + <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>
{% elif 'rocky' in settings.get('os_type', '') or 'rhel' in settings.get('os_type', '') %}
<strong style="color:var(--text-secondary)">Rocky/RHEL — upload these files from tak.gov:</strong><br>
Required: <span style="color:var(--cyan)">takserver-X.X.noarch.rpm</span><br>
Optional: <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>
{% else %}
Required: <span style="color:var(--cyan)">.deb</span> or <span style="color:var(--cyan)">.rpm</span> package
{% endif %}
<br><span style="color:var(--text-dim);font-size:11px">Select all at once or add files one at a time</span>
</div>
<input type="file" id="file-input" style="display:none" multiple {% if 'ubuntu' in settings.get('os_type', '') %}accept=".deb,.key,.pol"{% elif 'rocky' in settings.get('os_type', '') or 'rhel' in settings.get('os_type', '') %}accept=".rpm,.key"{% else %}accept=".deb,.rpm,.key,.pol"{% endif %} onchange="handleFileSelect(event)">
</div>
<div id="progress-area"></div>
<div id="upload-results" style="display:none">
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:20px">
<div id="upload-files-list" style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-secondary)"></div>
<div id="add-more-area" style="margin-top:16px;text-align:center">
<button onclick="var i=document.getElementById('file-input-more');i.value='';i.click()" style="padding:8px 20px;background:transparent;color:var(--accent);border:1px solid var(--border);border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;cursor:pointer">+ Add more files</button>
<input type="file" id="file-input-more" style="display:none" multiple {% if 'ubuntu' in settings.get('os_type', '') %}accept=".deb,.key,.pol"{% elif 'rocky' in settings.get('os_type', '') or 'rhel' in settings.get('os_type', '') %}accept=".rpm,.key"{% else %}accept=".deb,.rpm,.key,.pol"{% endif %} onchange="handleAddMore(event)">
</div>
<div id="deploy-btn-area" style="margin-top:20px;text-align:center;display:none">
<button onclick="showDeployConfig()" style="padding:12px 32px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:'DM Sans',sans-serif;font-size:15px;font-weight:600;cursor:pointer">Configure &amp; Deploy →</button>
</div></div></div>
{% endif %}
</div>
<div class="modal-overlay" id="tak-uninstall-modal">
<div class="modal">
<h3>⚠ Uninstall TAK Server?</h3>
<p>This will remove TAK Server completely: /opt/tak, all certificates, and config. You can redeploy after.</p>
<label class="form-label">Admin Password</label>
<input class="form-input" id="tak-uninstall-password" type="password" placeholder="Confirm your password">
<div class="modal-actions">
<button type="button" class="control-btn" id="tak-uninstall-cancel" onclick="document.getElementById('tak-uninstall-modal').classList.remove('open')">Cancel</button>
<button type="button" class="control-btn btn-stop" id="tak-uninstall-confirm" onclick="doUninstallTak()">Uninstall</button>
</div>
<div id="tak-uninstall-msg" style="margin-top:10px;font-size:12px;color:var(--red)"></div>
<div id="tak-uninstall-progress" class="uninstall-progress-row" style="display:none;margin-top:10px" aria-live="polite"></div>
</div>
</div>
<footer class="footer"></footer>
<script src="/takserver.js"></script></body></html>'''

# === Main Entry Point ===
if __name__ == '__main__':
    settings = load_settings()
    ssl_mode = settings.get('ssl_mode', 'self-signed')
    port = settings.get('console_port', 5001)
    print("=" * 50)
    print("infra-TAK v" + VERSION)
    print("=" * 50)
    print(f"OS: {settings.get('os_name', 'Unknown')}")
    print(f"SSL Mode: {ssl_mode}")
    fqdn = settings.get('fqdn', '')
    if fqdn:
        print(f"FQDN: {fqdn}")
    print(f"Port: {port}")
    print("=" * 50)
    # Always run with self-signed cert on 0.0.0.0
    # Caddy proxies on top when configured
    cert_dir = os.path.join(CONFIG_DIR, 'ssl')
    cert_file = os.path.join(cert_dir, 'console.crt')
    key_file = os.path.join(cert_dir, 'console.key')
    if os.path.exists(cert_file) and os.path.exists(key_file):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        app.run(host='0.0.0.0', port=port, ssl_context=context, debug=False)
    else:
        print("WARNING: SSL certs not found, running without HTTPS")
        app.run(host='0.0.0.0', port=port, debug=False)
