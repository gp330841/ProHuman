import asyncio
import time
import uuid
import os
import shutil
import tempfile
import hashlib
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class InfrastructureReport:
    """Aggregates stats from all mocks."""
    db_queries: int = 0
    db_query_time_ms: float = 0.0
    redis_ops: int = 0
    s3_uploads: int = 0
    s3_downloads: int = 0
    s3_bytes_uploaded: int = 0
    s3_bytes_downloaded: int = 0
    celery_tasks_queued: int = 0
    celery_tasks_executed: int = 0
    celery_task_execution_time_ms: float = 0.0
    queue_counts: Dict[str, int] = field(default_factory=dict)
    
    def generate_summary(self) -> Dict[str, Any]:
        return {
            "database": {
                "queries": self.db_queries,
                "avg_query_time_ms": self.db_query_time_ms / max(1, self.db_queries)
            },
            "redis": {
                "operations": self.redis_ops
            },
            "s3": {
                "uploads": self.s3_uploads,
                "downloads": self.s3_downloads,
                "bytes_uploaded": self.s3_bytes_uploaded,
                "bytes_downloaded": self.s3_bytes_downloaded
            },
            "celery": {
                "tasks_queued": self.celery_tasks_queued,
                "tasks_executed": self.celery_tasks_executed,
                "avg_task_time_ms": self.celery_task_execution_time_ms / max(1, self.celery_tasks_executed),
                "queues": self.queue_counts
            }
        }

class MockDatabase:
    """In-memory database mock."""
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {
            "sessions": {},
            "audio_chunks": {},
            "transcript_segments": {},
            "feature_results": {}
        }
        self._lock = asyncio.Lock()
        self.query_count = 0
        self.query_time_ms = 0.0

    async def _track_query(self, start_time: float):
        self.query_count += 1
        self.query_time_ms += (time.time() - start_time) * 1000

    def _check_constraints(self, table: str, record: Dict[str, Any]):
        if table == "audio_chunks":
            # Check unique index constraints conceptually
            session_id = record.get("session_id")
            for r in self._storage["audio_chunks"].values():
                if r.get("id") != record.get("id") and r.get("session_id") == session_id:
                    if r.get("index") == record.get("index"):
                        raise ValueError("uq_chunk_session_index constraint violated")
                    if r.get("checksum") == record.get("checksum"):
                        raise ValueError("uq_chunk_session_checksum constraint violated")
                        
        if table == "feature_results":
            for r in self._storage["feature_results"].values():
                if r.get("id") != record.get("id") and r.get("session_id") == record.get("session_id"):
                    if r.get("name") == record.get("name") and r.get("version") == record.get("version"):
                        raise ValueError("uq_feature_session_name_version constraint violated")
                        
        if "start_time" in record and "end_time" in record:
            if record["start_time"] is not None and record["end_time"] is not None:
                if record["end_time"] < record["start_time"]:
                    raise ValueError("Check constraint end_time >= start_time violated")

    async def create(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        async with self._lock:
            if table not in self._storage:
                self._storage[table] = {}
            
            record_id = record.get("id", str(uuid.uuid4()))
            new_record = {
                **record,
                "id": record_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            self._check_constraints(table, new_record)
            self._storage[table][record_id] = new_record
            await self._track_query(start_time)
            return dict(new_record)

    async def get(self, table: str, id: str) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        async with self._lock:
            result = self._storage.get(table, {}).get(id)
            await self._track_query(start_time)
            return dict(result) if result else None

    async def list(self, table: str, filters: Dict[str, Any] = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        start_time = time.time()
        async with self._lock:
            records = list(self._storage.get(table, {}).values())
            if filters:
                filtered = []
                for r in records:
                    match = True
                    for k, v in filters.items():
                        if r.get(k) != v:
                            match = False
                            break
                    if match:
                        filtered.append(r)
                records = filtered
            
            result = [dict(r) for r in records[offset:offset+limit]]
            await self._track_query(start_time)
            return result

    async def update(self, table: str, id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        async with self._lock:
            if table not in self._storage or id not in self._storage[table]:
                await self._track_query(start_time)
                return None
                
            record = self._storage[table][id]
            updated_record = {**record, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
            
            self._check_constraints(table, updated_record)
            self._storage[table][id] = updated_record
            
            await self._track_query(start_time)
            return dict(updated_record)

    async def delete(self, table: str, id: str) -> bool:
        start_time = time.time()
        async with self._lock:
            if table in self._storage and id in self._storage[table]:
                del self._storage[table][id]
                await self._track_query(start_time)
                return True
            await self._track_query(start_time)
            return False

    async def count(self, table: str, filters: Dict[str, Any] = None) -> int:
        start_time = time.time()
        async with self._lock:
            records = self._storage.get(table, {}).values()
            if filters:
                count = sum(1 for r in records if all(r.get(k) == v for k, v in filters.items()))
            else:
                count = len(records)
            await self._track_query(start_time)
            return count

class MockRedis:
    """In-memory Redis mock."""
    
    def __init__(self):
        self._kv: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}
        self._sets: Dict[str, Set[str]] = {}
        self._lists: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
        self.operations_count = 0

    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, v in self._expires.items() if v < now]
        for k in expired:
            self._kv.pop(k, None)
            self._sets.pop(k, None)
            self._lists.pop(k, None)
            del self._expires[k]

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int = None) -> bool:
        async with self._lock:
            self.operations_count += 1
            self._kv[key] = value
            if ex:
                self._expires[key] = time.time() + ex
            return True

    async def setnx(self, key: str, value: str, ex: int = None) -> bool:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            if key in self._kv:
                return False
            self._kv[key] = value
            if ex:
                self._expires[key] = time.time() + ex
            return True

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            self.operations_count += 1
            count = 0
            for k in keys:
                if k in self._kv or k in self._sets or k in self._lists:
                    self._kv.pop(k, None)
                    self._sets.pop(k, None)
                    self._lists.pop(k, None)
                    self._expires.pop(k, None)
                    count += 1
            return count

    async def exists(self, key: str) -> bool:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            return key in self._kv or key in self._sets or key in self._lists

    async def expire(self, key: str, ex: int) -> bool:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            if key in self._kv or key in self._sets or key in self._lists:
                self._expires[key] = time.time() + ex
                return True
            return False
            
    async def ttl(self, key: str) -> int:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            if key not in self._expires:
                return -1 if (key in self._kv or key in self._sets or key in self._lists) else -2
            return max(0, int(self._expires[key] - time.time()))

    async def incr(self, key: str) -> int:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            val = self._kv.get(key, "0")
            new_val = int(val) + 1
            self._kv[key] = str(new_val)
            return new_val

    async def decr(self, key: str) -> int:
        async with self._lock:
            self.operations_count += 1
            self._cleanup_expired()
            val = self._kv.get(key, "0")
            new_val = int(val) - 1
            self._kv[key] = str(new_val)
            return new_val

    async def lpush(self, key: str, *values: str) -> int:
        async with self._lock:
            self.operations_count += 1
            if key not in self._lists:
                self._lists[key] = []
            for v in values:
                self._lists[key].insert(0, v)
            return len(self._lists[key])

    async def rpush(self, key: str, *values: str) -> int:
        async with self._lock:
            self.operations_count += 1
            if key not in self._lists:
                self._lists[key] = []
            self._lists[key].extend(values)
            return len(self._lists[key])

    async def lpop(self, key: str) -> Optional[str]:
        async with self._lock:
            self.operations_count += 1
            if key in self._lists and self._lists[key]:
                return self._lists[key].pop(0)
            return None

    async def rpop(self, key: str) -> Optional[str]:
        async with self._lock:
            self.operations_count += 1
            if key in self._lists and self._lists[key]:
                return self._lists[key].pop()
            return None

    async def llen(self, key: str) -> int:
        async with self._lock:
            self.operations_count += 1
            return len(self._lists.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        async with self._lock:
            self.operations_count += 1
            if key not in self._lists:
                return []
            if end == -1:
                return list(self._lists[key][start:])
            return list(self._lists[key][start:end+1])

    async def sadd(self, key: str, *values: str) -> int:
        async with self._lock:
            self.operations_count += 1
            if key not in self._sets:
                self._sets[key] = set()
            added = 0
            for v in values:
                if v not in self._sets[key]:
                    self._sets[key].add(v)
                    added += 1
            return added

    async def srem(self, key: str, *values: str) -> int:
        async with self._lock:
            self.operations_count += 1
            if key not in self._sets:
                return 0
            removed = 0
            for v in values:
                if v in self._sets[key]:
                    self._sets[key].remove(v)
                    removed += 1
            return removed

    async def smembers(self, key: str) -> Set[str]:
        async with self._lock:
            self.operations_count += 1
            return set(self._sets.get(key, set()))

    async def sismember(self, key: str, value: str) -> bool:
        async with self._lock:
            self.operations_count += 1
            return value in self._sets.get(key, set())

class MockS3:
    """Mock MinIO S3 object storage."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mock_s3_")
        self.uploads = 0
        self.downloads = 0
        self.bytes_uploaded = 0
        self.bytes_downloaded = 0
        self._lock = asyncio.Lock()

    def __del__(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_path(self, bucket: str, key: str) -> str:
        bucket_dir = os.path.join(self.temp_dir, bucket)
        os.makedirs(bucket_dir, exist_ok=True)
        return os.path.join(bucket_dir, key.replace("/", "_"))

    async def put_object(self, bucket: str, key: str, data: bytes) -> Dict[str, Any]:
        async with self._lock:
            path = self._get_path(bucket, key)
            with open(path, 'wb') as f:
                f.write(data)
            
            self.uploads += 1
            self.bytes_uploaded += len(data)
            
            return {
                "ETag": f'"{hashlib.md5(data).hexdigest()}"',
                "VersionId": "null"
            }

    async def get_object(self, bucket: str, key: str) -> bytes:
        async with self._lock:
            path = self._get_path(bucket, key)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Object {key} not found in bucket {bucket}")
                
            with open(path, 'rb') as f:
                data = f.read()
                
            self.downloads += 1
            self.bytes_downloaded += len(data)
            return data

    async def delete_object(self, bucket: str, key: str) -> bool:
        async with self._lock:
            path = self._get_path(bucket, key)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False

    async def list_objects(self, bucket: str, prefix: str = "") -> List[Dict[str, Any]]:
        async with self._lock:
            bucket_dir = os.path.join(self.temp_dir, bucket)
            if not os.path.exists(bucket_dir):
                return []
                
            results = []
            safe_prefix = prefix.replace("/", "_")
            for filename in os.listdir(bucket_dir):
                if filename.startswith(safe_prefix):
                    filepath = os.path.join(bucket_dir, filename)
                    stat = os.stat(filepath)
                    # Reconstruct original key heuristically if needed, here just use filename
                    original_key = filename.replace("_", "/") if "_" in filename else filename
                    results.append({
                        "Key": original_key,
                        "Size": stat.st_size,
                        "LastModified": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                    })
            return results

    async def generate_presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        return f"https://mock-s3.local/{bucket}/{key}?expires={expires}"

    async def head_object(self, bucket: str, key: str) -> Dict[str, Any]:
        async with self._lock:
            path = self._get_path(bucket, key)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Object {key} not found in bucket {bucket}")
                
            stat = os.stat(path)
            return {
                "ContentLength": stat.st_size,
                "LastModified": datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                "ContentType": "application/octet-stream"
            }

class MockCeleryBroker:
    """In-memory Mock Celery Broker."""
    
    def __init__(self, delay_ms: int = 10):
        self.delay_ms = delay_ms
        self.tasks_queued = 0
        self.tasks_executed = 0
        self.task_execution_time_ms = 0.0
        self.queue_counts: Dict[str, int] = {}
        self.results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        
    async def send_task(self, name: str, args: tuple = (), kwargs: dict = None, queue: str = "default") -> str:
        if kwargs is None:
            kwargs = {}
            
        task_id = str(uuid.uuid4())
        
        async with self._lock:
            self.tasks_queued += 1
            self.queue_counts[queue] = self.queue_counts.get(queue, 0) + 1
            
        # Simulate background execution directly for testing purposes
        asyncio.create_task(self._execute_task(task_id, name, args, kwargs, queue))
        return task_id
        
    async def _execute_task(self, task_id: str, name: str, args: tuple, kwargs: dict, queue: str):
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
            
        start_time = time.time()
        
        # Simulate result based on task name
        result = {"status": "success", "task": name}
        
        async with self._lock:
            self.tasks_executed += 1
            self.task_execution_time_ms += (time.time() - start_time) * 1000
            self.results[task_id] = result
            
    async def get_task_result(self, task_id: str, timeout: int = 5) -> Any:
        start_time = time.time()
        while time.time() - start_time < timeout:
            async with self._lock:
                if task_id in self.results:
                    return self.results[task_id]
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Task {task_id} result not ready")
