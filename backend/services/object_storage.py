"""Object storage abstraction for generated presentations and preview assets."""

from __future__ import annotations

import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from config import settings


_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_OBJECT_STORAGE = None


@dataclass
class StoredObject:
    key: str
    url: str
    content_type: str
    size: int


def _build_public_url(key: str) -> str:
    base = settings.OBJECT_STORAGE_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{quote(key, safe='/')}"


def _guess_content_type(key: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    guessed, _ = mimetypes.guess_type(key)
    return guessed or "application/octet-stream"


def _resolve_local_root() -> Path:
    root = Path(settings.OBJECT_STORAGE_LOCAL_ROOT)
    if root.is_absolute():
        return root
    return (_BACKEND_ROOT / root).resolve()


class LocalObjectStorage:
    def __init__(self, root: Path):
        self.root = root

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_file(self, local_path: str | Path, key: str, content_type: str | None = None) -> StoredObject:
        src = Path(local_path)
        if not src.exists():
            raise FileNotFoundError(f"Object source file not found: {src}")

        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return StoredObject(
            key=key,
            url=_build_public_url(key),
            content_type=_guess_content_type(key, content_type),
            size=dest.stat().st_size,
        )

    def upload_bytes(self, payload: bytes, key: str, content_type: str | None = None) -> StoredObject:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        return StoredObject(
            key=key,
            url=_build_public_url(key),
            content_type=_guess_content_type(key, content_type),
            size=len(payload),
        )

    def read_object(self, key: str) -> tuple[bytes, str]:
        path = self.root / key
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes(), _guess_content_type(key)

    def delete_object(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()


class S3ObjectStorage:
    def __init__(self) -> None:
        endpoint_url = settings.OBJECT_STORAGE_ENDPOINT_URL or None
        self.bucket = settings.OBJECT_STORAGE_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY,
            region_name=settings.OBJECT_STORAGE_REGION,
            use_ssl=settings.OBJECT_STORAGE_SECURE,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def init(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            create_args = {"Bucket": self.bucket}
            if settings.OBJECT_STORAGE_REGION != "us-east-1":
                create_args["CreateBucketConfiguration"] = {
                    "LocationConstraint": settings.OBJECT_STORAGE_REGION
                }
            self.client.create_bucket(**create_args)

    def upload_file(self, local_path: str | Path, key: str, content_type: str | None = None) -> StoredObject:
        src = Path(local_path)
        if not src.exists():
            raise FileNotFoundError(f"Object source file not found: {src}")

        resolved_content_type = _guess_content_type(key, content_type)
        self.client.upload_file(
            str(src),
            self.bucket,
            key,
            ExtraArgs={"ContentType": resolved_content_type},
        )
        return StoredObject(
            key=key,
            url=_build_public_url(key),
            content_type=resolved_content_type,
            size=src.stat().st_size,
        )

    def upload_bytes(self, payload: bytes, key: str, content_type: str | None = None) -> StoredObject:
        resolved_content_type = _guess_content_type(key, content_type)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ContentType=resolved_content_type,
        )
        return StoredObject(
            key=key,
            url=_build_public_url(key),
            content_type=resolved_content_type,
            size=len(payload),
        )

    def read_object(self, key: str) -> tuple[bytes, str]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise FileNotFoundError(f"Object not found: {key}") from exc

        return (
            response["Body"].read(),
            response.get("ContentType") or _guess_content_type(key),
        )

    def delete_object(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise FileNotFoundError(f"Object not found: {key}") from exc


def create_object_storage():
    backend = settings.OBJECT_STORAGE_BACKEND.lower()
    if backend == "s3":
        return S3ObjectStorage()
    return LocalObjectStorage(_resolve_local_root())


def get_object_storage():
    global _OBJECT_STORAGE
    if _OBJECT_STORAGE is None:
        _OBJECT_STORAGE = create_object_storage()
    return _OBJECT_STORAGE


def init_object_storage() -> None:
    get_object_storage().init()


def reset_object_storage() -> None:
    global _OBJECT_STORAGE
    _OBJECT_STORAGE = None
