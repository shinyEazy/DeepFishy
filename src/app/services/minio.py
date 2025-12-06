"""MinIO S3-compatible storage service."""

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any

from minio import Minio
from minio.error import S3Error

from app.core.logging import logger


class MinioService:
    """Service for interacting with MinIO object storage."""

    def __init__(self):
        """Initialize MinIO client."""
        self.endpoint = os.getenv("MINIO_URL")
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        self.secure = os.getenv("MINIO_SECURE").lower() == "true"

        # Remove http:// or https:// from endpoint if present
        self.endpoint = self.endpoint.replace("http://", "").replace("https://", "")

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """
        Ensure bucket exists, create if not.

        Args:
            bucket_name: Name of the bucket

        Returns:
            True if bucket exists or was created
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error ensuring bucket {bucket_name}: {e}")
            return False

    def upload_json(
        self,
        bucket_name: str,
        object_name: str,
        data: Dict[str, Any],
    ) -> bool:
        """
        Upload JSON data to MinIO.

        Args:
            bucket_name: Name of the bucket
            object_name: Path/name of the object in bucket
            data: Dictionary to save as JSON

        Returns:
            True if successful
        """
        try:
            # Ensure bucket exists
            if not self.ensure_bucket_exists(bucket_name):
                return False

            # Convert dict to JSON bytes
            json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            json_buffer = BytesIO(json_bytes)

            # Upload to MinIO
            self.client.put_object(
                bucket_name,
                object_name,
                json_buffer,
                length=len(json_bytes),
                content_type="application/json",
            )

            logger.info(f"Uploaded {object_name} to {bucket_name}")
            return True

        except S3Error as e:
            logger.error(f"Error uploading {object_name}: {e}")
            return False

    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_path: Path,
    ) -> bool:
        """
        Upload file to MinIO.

        Args:
            bucket_name: Name of the bucket
            object_name: Path/name of the object in bucket
            file_path: Local file path to upload

        Returns:
            True if successful
        """
        try:
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False

            # Ensure bucket exists
            if not self.ensure_bucket_exists(bucket_name):
                return False

            # Upload file
            self.client.fput_object(
                bucket_name,
                object_name,
                str(file_path),
            )

            logger.info(f"Uploaded file {file_path} to {bucket_name}/{object_name}")
            return True

        except S3Error as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            return False

    def download_json(
        self,
        bucket_name: str,
        object_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Download and parse JSON from MinIO.

        Args:
            bucket_name: Name of the bucket
            object_name: Path/name of the object in bucket

        Returns:
            Parsed JSON dict or None if error
        """
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = json.loads(response.read().decode("utf-8"))
            logger.info(f"Downloaded {object_name} from {bucket_name}")
            return data

        except S3Error as e:
            logger.error(f"Error downloading {object_name}: {e}")
            return None

    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
    ) -> list:
        """
        List objects in bucket.

        Args:
            bucket_name: Name of the bucket
            prefix: Filter by prefix

        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Error listing objects: {e}")
            return []

    def delete_object(
        self,
        bucket_name: str,
        object_name: str,
    ) -> bool:
        """
        Delete object from MinIO.

        Args:
            bucket_name: Name of the bucket
            object_name: Path/name of the object

        Returns:
            True if successful
        """
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted {object_name} from {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting {object_name}: {e}")
            return False
