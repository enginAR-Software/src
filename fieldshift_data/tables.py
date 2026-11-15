"""Loss-aware CSV reading, safe archive access and descriptive profiling."""

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import zipfile


MISSING = {"", "na", "n/a", "nan", "null"}
MAX_EXPANDED = 128 * 1024 * 1024


def is_missing(value):
    return value is None or str(value).strip().casefold() in MISSING


def numeric(value):
    if is_missing(value):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


@dataclass
class Table:
    name: str
    headers: list
    rows: list
    encoding: str = "utf-8-sig"


def read_csv(raw, name):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"{name}: cannot be read as UTF-8/Windows-1252.")
    parsed = csv.reader(io.StringIO(text, newline=""))
    try:
        headers = [cell.strip() for cell in next(parsed)]
    except StopIteration as error:
        raise ValueError(f"{name}: empty CSV.") from error
    if not all(headers) or len(headers) != len(set(headers)):
        raise ValueError(f"{name}: empty or duplicate column name.")
    rows = []
    for line, cells in enumerate(parsed, 2):
        if not cells or not any(cells):
            continue
        if len(cells) != len(headers):
            raise ValueError(f"{name}:{line}: {len(cells)} columns, expected {len(headers)}.")
        rows.append(dict(zip(headers, (cell.strip() for cell in cells))))
    return Table(name, headers, rows, encoding)


def read_zip_csv(path):
    tables = {}
    with zipfile.ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED:
            raise ValueError("Unpacked ZIP size exceeds the 128 MiB limit.")
        for info in archive.infolist():
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts or ":" in str(member):
                raise ValueError("Unsafe file path inside the ZIP.")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symbolic links inside the ZIP are not accepted.")
            if info.is_dir() or member.suffix.casefold() != ".csv":
                continue
            if member.stem in tables:
                raise ValueError("Two CSV tables with the same name inside the ZIP.")
            # Read in memory; never extract arbitrary paths onto the filesystem.
            tables[member.stem] = read_csv(archive.read(info), member.name)
    return tables


def require(table, columns):
    absent = set(columns) - set(table.headers)
    if absent:
        raise ValueError(f"{table.name}: expected columns missing: {sorted(absent)}")


def unique_index(table, key):
    require(table, [key])
    output = {}
    for row in table.rows:
        value = row[key]
        if is_missing(value) or value in output:
            raise ValueError(f"{table.name}: {key} empty or duplicated ({value}).")
        output[value] = row
    return output


def profile(table):
    columns = []
    for header in table.headers:
        nonempty = [r[header] for r in table.rows if not is_missing(r[header])]
        numbers = [n for v in nonempty if (n := numeric(v)) is not None]
        column = {"name": header, "missing": len(table.rows) - len(nonempty),
                  "nonmissing": len(nonempty), "distinct": len(set(nonempty)),
                  "numeric_count": len(numbers), "nonnumeric_count": len(nonempty) - len(numbers),
                  "examples": list(dict.fromkeys(nonempty))[:4]}
        if numbers:
            column.update(min=min(numbers), max=max(numbers), mean=statistics.fmean(numbers))
        columns.append(column)
    return {"name": table.name, "row_count": len(table.rows), "column_count": len(table.headers),
            "encoding": table.encoding, "columns": columns}


def write_csv(path, rows, headers=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = headers or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path, algorithm="sha256"):
    result = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()
