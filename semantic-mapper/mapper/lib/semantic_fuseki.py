import base64
import time
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from lib.semantic_files import read_all


class FusekiClient:
    def __init__(self, data_url: str, ping_url: str, username: str, password: str):
        self.data_url = data_url
        self.ping_url = ping_url
        self.username = username
        self.password = password

    def headers(self, content_type: str) -> Dict[str, str]:
        result = {"Content-Type": content_type}
        if self.password:
            credentials = f"{self.username}:{self.password}".encode("utf-8")
            token = base64.b64encode(credentials).decode("ascii")
            result["Authorization"] = f"Basic {token}"
        return result

    def wait_until_ready(self, attempts: int = 30, delay: float = 2.0) -> None:
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                with urlopen(self.ping_url, timeout=5) as response:
                    if 200 <= response.status < 500:
                        print(f"Ready: {self.ping_url}")
                        return
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
            print(f"Waiting for {self.ping_url} ({attempt}/{attempts})")
            time.sleep(delay)
        raise RuntimeError(f"Timed out waiting for {self.ping_url}: {last_error}")

    def put_named_graph(self, label: str, files: List[Path], graph_iri: str) -> None:
        if not files:
            print(f"No {label} files found; skipping graph upload")
            return

        body = read_all(files).encode("utf-8")
        url = f"{self.data_url}?graph={quote(graph_iri, safe='')}"
        request = Request(url, data=body, method="PUT", headers=self.headers("text/turtle"))
        with urlopen(request, timeout=30) as response:
            print(f"Uploaded {len(files)} {label} file(s) to {graph_iri}: HTTP {response.status}")
