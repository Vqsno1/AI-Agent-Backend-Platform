"""Build with existing proxy routing/trust; never disable TLS or persist credentials.

Run from the repository root. Normal local builds can use docker compose build.
"""

import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

config = Path("/workspace/.agentflow-docker")
config.mkdir(exist_ok=True)
environment = dict(os.environ, DOCKER_CONFIG=str(config))
args = ["docker", "build"]
hosts = set()
for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
    if os.getenv(name):
        args += ["--build-arg", name]
        if name != "NO_PROXY":
            host = urlparse(os.environ[name]).hostname
            if host and host not in hosts:
                args += ["--add-host", f"{host}:{socket.gethostbyname(host)}"]
                hosts.add(host)
ca = os.getenv("SSL_CERT_FILE")
if ca and Path(ca).is_file():
    args += ["--secret", f"id=ca_bundle,src={ca}"]
args += ["-t", "agentflow:local", "."]
subprocess.run(args, env=environment, check=True)
