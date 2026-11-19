"""Module for storage.py."""
from __future__ import annotations

from tempfile import SpooledTemporaryFile

import aiobotocore.session
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError

class S3StorageService:
    """S3 Storage Service wrapper."""
    
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket_name: str) -> None:
        """Method documentation."""
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.session = aiobotocore.session.get_session()
        
    async def init(self) -> None:
        """Initialize client and ensure bucket exists."""
        async with self._create_client() as client:
            try:
                await client.create_bucket(Bucket=self.bucket_name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in {
                    "BucketAlreadyExists",
                    "BucketAlreadyOwnedByYou",
                }:
                    raise

    def _create_client(self):
        """Method documentation."""
        return self.session.create_client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    async def upload_chunk(self, session_id: str, chunk_index: int, data: bytes, content_type: str) -> str:
        """Upload an audio chunk to S3."""
        s3_key = f"{session_id}/chunks/{chunk_index}.raw"
        async with self._create_client() as client:
            await client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=data, ContentType=content_type)
        return s3_key

    async def upload_file(self, session_id: str, filename: str, data: bytes, content_type: str) -> str:
        """Upload a file to S3."""
        s3_key = f"{session_id}/{filename}"
        async with self._create_client() as client:
            await client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=data, ContentType=content_type)
        return s3_key

    async def assemble_recording(self, session_id: str, filename: str, chunks: list[str], mime_type: str) -> str:
        key = f"{session_id}/{filename}"
        async with self._create_client() as client:
            with SpooledTemporaryFile(max_size=2 * 1024 * 1024) as recording:
                for chunk in chunks:
                    obj = await client.get_object(Bucket=self.bucket_name, Key=chunk)
                    async with obj["Body"] as body:
                        recording.write(await body.read())
                length = recording.tell()
                recording.seek(0)
                await client.put_object(
                    Bucket=self.bucket_name, Key=key, Body=recording,
                    ContentType=mime_type, ContentLength=length,
                )
        return key

    async def playback_response(self, key: str, byte_range: str | None):
        client_context = self._create_client()
        client = await client_context.__aenter__()
        try:
            options = {"Range": byte_range} if byte_range else {}
            obj = await client.get_object(Bucket=self.bucket_name, Key=key, **options)
        except BaseException as error:
            await client_context.__aexit__(None, None, None)
            if isinstance(error, ClientError) and error.response["Error"]["Code"] == "InvalidRange":
                raise HTTPException(status_code=416, detail="Requested range unavailable") from error
            raise

        async def stream():
            try:
                async with obj["Body"] as body:
                    async for chunk in body.iter_chunks():
                        yield chunk
            finally:
                await client_context.__aexit__(None, None, None)

        headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, no-store",
                   "X-Content-Type-Options": "nosniff", "Content-Length": str(obj["ContentLength"])}
        if "ContentRange" in obj:
            headers["Content-Range"] = obj["ContentRange"]
        media = obj.get("ContentType", "")
        if not media.startswith("audio/"):
            media = "application/octet-stream"
        return StreamingResponse(
            stream(), status_code=206 if "ContentRange" in obj else 200,
            media_type=media, headers=headers,
        )

    async def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL."""
        async with self._create_client() as client:
            url = await client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
        return url

    async def delete(self, s3_key: str) -> None:
        """Delete an object from S3."""
        async with self._create_client() as client:
            await client.delete_object(Bucket=self.bucket_name, Key=s3_key)

    async def delete_recording(self, session_id: str) -> None:
        """Remove only objects stored under this recording's prefix."""
        async with self._create_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=f"{session_id}/"):
                objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
                if objects:
                    response = await client.delete_objects(
                        Bucket=self.bucket_name, Delete={"Objects": objects}
                    )
                    if response.get("Errors"):
                        raise RuntimeError("Some recording objects could not be deleted")

    async def close(self) -> None:
        """Cleanup resources."""
        return

__all__ = ["S3StorageService"]
