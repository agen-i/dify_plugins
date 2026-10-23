"""Bounded owned child process and per-invocation temporary cleanup."""

import fcntl
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from pdf_core.config import Limits
from pdf_core.formatting import validate_batch
from pdf_core.model import (
    BatchRecord,
    ConversionError,
    DocumentRecord,
    InputPDF,
    PageRecord,
)


def runtime_root() -> Path:
    root = Path(tempfile.gettempdir()) / f"pdf-text-pages-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise ConversionError("CONFIG: private runtime directory required")
    return root


@contextmanager
def execution_slot(limits: Limits) -> Iterator[None]:
    """Linux cross-process admission; contention fails promptly, no unbounded queue."""
    root = runtime_root()
    acquired: int | None = None
    for index in range(limits.concurrency):
        descriptor = os.open(
            root / f"slot-{index}.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = descriptor
            break
        except BlockingIOError:
            os.close(descriptor)
    if acquired is None:
        raise ConversionError("BUSY: conversion capacity reached; retry later")
    try:
        yield
    finally:
        fcntl.flock(acquired, fcntl.LOCK_UN)
        os.close(acquired)


def stop_child(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def convert(
    inputs: list[InputPDF],
    dpi: float,
    limits: Limits,
    deadline: float | None = None,
) -> BatchRecord:
    if not inputs or len(inputs) > limits.max_files:
        raise ConversionError("LIMIT: input file count")
    if (
        any(len(i.data) > limits.input_file_bytes for i in inputs)
        or sum(len(i.data) for i in inputs) > limits.input_total_bytes
    ):
        raise ConversionError("LIMIT: input bytes")
    dpi = limits.dpi(dpi)
    batch_id = "B" + uuid4().hex.upper()
    timeout = limits.process_seconds
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
    if timeout <= 0:
        raise ConversionError("PROCESS_TIMEOUT: request deadline")
    with tempfile.TemporaryDirectory(
        prefix="run-", dir=runtime_root()
    ) as directory:
        root = Path(directory)
        documents = []
        for index, item in enumerate(inputs):
            path = f"input-{index:03d}.pdf"
            (root / path).write_bytes(item.data)
            documents.append(
                {
                    "filename": item.filename,
                    "source_parameter": item.source_parameter,
                    "source_index": item.source_index,
                    "input_path": path,
                }
            )
        request = {
            "batch_id": batch_id,
            "documents": documents,
            "dpi": dpi,
            "limits": asdict(limits),
            "parent_pid": os.getpid(),
        }
        request_path = root / "request.json"
        request_path.write_text(json.dumps(request))
        process = subprocess.Popen(
            [sys.executable, "-m", "pdf_core.worker", str(request_path)],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                position = "INPUT"
                if (root / "progress.json").exists():
                    try:
                        position = json.loads(
                            (root / "progress.json").read_text()
                        )["position"]
                    except Exception:
                        pass
                raise ConversionError(
                    f"{position}: PROCESS_TIMEOUT: child terminated"
                ) from None
            if returncode != 0 or not (root / "result.json").is_file():
                position = "INPUT"
                if (root / "progress.json").exists():
                    position = json.loads(
                        (root / "progress.json").read_text()
                    )["position"]
                raise ConversionError(
                    f"{position}: PROCESS_EXIT: memory/native/worker failure"
                )
            raw = json.loads((root / "result.json").read_text())
            if "error" in raw:
                raise ConversionError(raw["error"])
            docs = []
            for doc in raw["documents"]:
                pages = []
                for page in doc.pop("pages"):
                    image_path = page.pop("image_path")
                    pages.append(
                        PageRecord(
                            **page, png=(root / image_path).read_bytes()
                        )
                    )
                docs.append(DocumentRecord(**doc, pages=pages))
            batch = BatchRecord(raw["batch_id"], docs)
            validate_batch(batch)
            return batch
        finally:
            stop_child(process)
