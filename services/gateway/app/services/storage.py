from __future__ import annotations

import aiobotocore.session

class S3StorageService:
    """S3 Storage Service wrapper."""
    
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket_name: str) -> None:
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.session = aiobotocore.session.get_session()
        self._client = None
        
    async def init(self) -> None:
        """Initialize client and ensure bucket exists."""
        self._client = self.session.create_client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )
        # Attempt to create bucket
        async with self._client as client:
            try:
                await client.create_bucket(Bucket=self.bucket_name)
            except Exception:
                pass # Bucket likely exists

    async def upload_chunk(self, session_id: str, chunk_index: int, data: bytes, content_type: str) -> str:
        """Upload an audio chunk to S3."""
        s3_key = f"{session_id}/chunks/{chunk_index}.raw"
        async with self._client as client:
            await client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=data, ContentType=content_type)
        return s3_key

    async def upload_file(self, session_id: str, filename: str, data: bytes, content_type: str) -> str:
        """Upload a file to S3."""
        s3_key = f"{session_id}/{filename}"
        async with self._client as client:
            await client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=data, ContentType=content_type)
        return s3_key

    async def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL."""
        async with self._client as client:
            url = await client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
        return url

    async def delete(self, s3_key: str) -> None:
        """Delete an object from S3."""
        async with self._client as client:
            await client.delete_object(Bucket=self.bucket_name, Key=s3_key)

    async def close(self) -> None:
        """Cleanup resources."""
        if self._client:
            pass # context manager handles closing typically

__all__ = ["S3StorageService"]
