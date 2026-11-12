#!/usr/bin/env python3
"""Read only Godot's iOS template from the official export-template archive."""
import argparse
import io
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

VERSION = "4.6.3"
URL = (f"https://godot-releases.nbg1.your-objectstorage.com/{VERSION}-stable/"
       f"Godot_v{VERSION}-stable_export_templates.tpz")


class RangeFile(io.RawIOBase):
    def __init__(self, url):
        headers = subprocess.check_output(["curl", "-fsSI", "--max-time", "25", url], text=True)
        lengths = re.findall(r"^content-length:\s*(\d+)", headers, re.I | re.M)
        if not lengths:
            raise OSError("Godot mirror did not provide the template size")
        self.size = int(lengths[-1])
        self.url = url
        self.position = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        base = (0, self.position, self.size)[whence]
        self.position = base + offset
        return self.position

    def read(self, size=-1):
        remaining = max(0, self.size - self.position)
        size = remaining if size < 0 else min(remaining, size)
        if size == 0:
            return b""
        start = self.position
        end = start + size - 1
        # Unique URLs also avoid transparent caches serving a previous range.
        with tempfile.TemporaryDirectory() as directory:
            header_path = Path(directory) / "headers"
            result = subprocess.check_output([
                "curl", "-fsS", "--max-time", "45", "--retry", "1",
                "--range", f"{start}-{end}", "--dump-header", str(header_path),
                f"{self.url}?drenovar-range={start}-{end}",
            ])
            headers = header_path.read_text().lower()
            if f"content-range: bytes {start}-{end}/" not in headers:
                raise OSError("Godot mirror did not return the requested byte range")
        if len(result) != size:
            raise OSError("Truncated Godot export archive range")
        self.position += size
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RangeFile(URL)) as archive:
        item = archive.getinfo("templates/ios.zip")
        print(f"iOS template: {item.file_size:,} bytes", flush=True)
        temp = args.output.with_suffix(".tmp")
        with archive.open(item) as source, temp.open("wb") as target:
            while chunk := source.read(24 * 1024 * 1024):
                target.write(chunk)
        temp.replace(args.output)


if __name__ == "__main__":
    main()
