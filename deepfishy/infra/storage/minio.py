"""MinIO S3-compatible storage service."""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from minio import Minio
from minio.error import S3Error

from deepfishy.infra.config.settings import settings
from deepfishy.shared.logging import logger


class MinioService:
    """Service for interacting with MinIO object storage."""

    def __init__(self):
        """Initialize MinIO client."""
        endpoint = settings.MINIO_URL
        if not endpoint:
            raise ValueError("MINIO_URL is not configured")

        self.endpoint = endpoint.replace("http://", "").replace("https://", "")
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.secure = settings.MINIO_SECURE

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def ensure_bucket_exists(self, bucket_name: str) -> bool:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
            return True
        except S3Error as exc:
            logger.error(f"Error ensuring bucket {bucket_name}: {exc}")
            return False

    def upload_json(
        self,
        bucket_name: str,
        object_name: str,
        data: dict[str, Any],
    ) -> bool:
        try:
            if not self.ensure_bucket_exists(bucket_name):
                return False

            json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            json_buffer = BytesIO(json_bytes)

            self.client.put_object(
                bucket_name,
                object_name,
                json_buffer,
                length=len(json_bytes),
                content_type="application/json",
            )

            logger.info(f"Uploaded {object_name} to {bucket_name}")
            return True

        except S3Error as exc:
            logger.error(f"Error uploading {object_name}: {exc}")
            return False

    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_path: Path,
    ) -> bool:
        try:
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False

            if not self.ensure_bucket_exists(bucket_name):
                return False

            self.client.fput_object(
                bucket_name,
                object_name,
                str(file_path),
            )

            logger.info(f"Uploaded file {file_path} to {bucket_name}/{object_name}")
            return True

        except S3Error as exc:
            logger.error(f"Error uploading file {file_path}: {exc}")
            return False

    def download_json(
        self,
        bucket_name: str,
        object_name: str,
    ) -> dict[str, Any] | None:
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = json.loads(response.read().decode("utf-8"))
            logger.info(f"Downloaded {object_name} from {bucket_name}")
            return data

        except S3Error as exc:
            logger.error(f"Error downloading {object_name}: {exc}")
            return None

    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
    ) -> list[str]:
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as exc:
            logger.error(f"Error listing objects: {exc}")
            return []

    def delete_object(
        self,
        bucket_name: str,
        object_name: str,
    ) -> bool:
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted {object_name} from {bucket_name}")
            return True
        except S3Error as exc:
            logger.error(f"Error deleting {object_name}: {exc}")
            return False
