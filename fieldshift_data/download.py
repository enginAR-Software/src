"""Pinned, checksum-verified HTTPS acquisition with bounded retries."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from .catalog import SOURCES, source_directory
from .tables import digest
from . import __version__


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ValueError("Redirect away from HTTPS refused.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url, headers=None):
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError("Only HTTPS sources are accepted.")
    request = urllib.request.Request(url, headers={"User-Agent": f"FieldShiftData/{__version__} (public research data reader)", **(headers or {})})
    return urllib.request.build_opener(HTTPSRedirect()).open(request, timeout=30)


def request_bytes(url, limit, headers=None):
    for attempt in range(3):
        try:
            with open_url(url, headers) as response:
                raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("Response size limit exceeded.")
            return raw
        except OSError as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(1.1 * (attempt + 1))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".part") as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_file(path, spec):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"File missing: {path}. Run the fetch command first.")
    if path.stat().st_size != spec["size"] or digest(path, "md5") != spec["md5"]:
        raise ValueError(f"File integrity mismatch: {path}. Move the file aside and download again; it was not overwritten.")
    return {"file": spec["name"], "size": path.stat().st_size,
            "md5": spec["md5"], "sha256": digest(path)}


def validate_cache(workspace, key):
    directory = source_directory(workspace, key)
    if not (directory / "metadata.json").is_file():
        raise ValueError(f"{key}: source metadata.json record missing; fetch required.")
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if meta.get("id") != SOURCES[key]["article_id"] or meta.get("version") != SOURCES[key]["version"]:
        raise ValueError(f"{key}: metadata id or version does not match.")
    files = [verify_file(directory / spec["name"], spec) for spec in SOURCES[key]["files"]]
    return {"dataset": key, "version": SOURCES[key]["version"], "doi": SOURCES[key]["doi"],
            "license": meta.get("license"), "metadata_sha256": digest(directory / "metadata.json"), "files": files}


def fetch(workspace, key):
    source = SOURCES[key]
    directory = source_directory(workspace, key)
    directory.mkdir(parents=True, exist_ok=True)
    # Pin the API release instead of silently adopting a new data schema.
    api = f"https://api.figshare.com/v2/articles/{source['article_id']}/versions/{source['version']}"
    raw = request_bytes(api, 4 * 1024 * 1024)
    metadata = json.loads(raw)
    if metadata.get("id") != source["article_id"] or metadata.get("version") != source["version"]:
        raise ValueError("Source version/id differs from what was expected.")
    indexed = {f["id"]: f for f in metadata["files"]}
    transfers = []
    for spec in source["files"]:
        remote = indexed.get(spec["id"], {})
        if (remote.get("name") != spec["name"] or remote.get("size") != spec["size"]
                or remote.get("computed_md5") != spec["md5"] or remote.get("is_link_only")):
            raise ValueError("The source file does not match the pinned catalog; no automatic update was made.")
        path = directory / spec["name"]
        if path.exists():
            verify_file(path, spec)
            transfers.append({"file": spec["name"], "status": "cached", "bytes": spec["size"]})
            continue
        error = None
        for attempt in range(3):
            temporary = None
            try:
                time.sleep(1.1)  # Responsible API access; also avoid tight retry loops.
                with tempfile.NamedTemporaryFile(dir=directory, delete=False, suffix=".part") as stream:
                    temporary = Path(stream.name)
                    with open_url(remote["download_url"]) as response:
                        received = 0
                        while chunk := response.read(1024 * 1024):
                            received += len(chunk)
                            if received > spec["size"]:
                                raise ValueError("Download exceeded the expected file size.")
                            stream.write(chunk)
                verify_file(temporary, spec)
                temporary.replace(path)
                transfers.append({"file": spec["name"], "status": "downloaded", "bytes": received})
                error = None
                break
            except (OSError, ValueError) as failure:
                error = failure
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        if error is not None:
            raise ValueError(f"{spec['name']} indirilemedi: {error}") from error
    # Commit metadata only after every file has been checked.
    atomic_json(directory / "metadata.json", metadata)
    receipt = {"fetched_at_utc": datetime.now(timezone.utc).isoformat(), "api": api,
               "source_version": source["version"], "transfers": transfers,
               "downloaded_count": sum(r["status"] == "downloaded" for r in transfers),
               "cached_count": sum(r["status"] == "cached" for r in transfers)}
    atomic_json(directory / "acquisition.json", receipt)
    return {**validate_cache(workspace, key), "acquisition": receipt}
