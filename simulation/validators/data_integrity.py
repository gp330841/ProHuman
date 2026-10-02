from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

@dataclass
class IntegrityViolation:
    constraint_name: str
    violation_type: str
    details: str
    affected_records: List[str]

@dataclass
class IntegrityResult:
    is_valid: bool = True
    violations: List[IntegrityViolation] = field(default_factory=list)
    checked_constraints: int = 0
    passed_constraints: int = 0
    
    def add_violation(self, violation: IntegrityViolation) -> None:
        self.violations.append(violation)
        self.is_valid = False

class DataIntegrityValidator:
    def validate_session_lifecycle(self, session_records: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        valid_transitions = {
            "CREATED": {"RECORDING", "FAILED"},
            "RECORDING": {"PROCESSING", "FAILED"},
            "PROCESSING": {"TRANSCRIBING", "FAILED"},
            "TRANSCRIBING": {"TRANSCRIBED", "FAILED"},
            "TRANSCRIBED": {"INDEXING", "FAILED"},
            "INDEXING": {"INDEXED", "FAILED"},
            "INDEXED": {"EXTRACTING", "FAILED"},
            "EXTRACTING": {"COMPLETED", "FAILED"},
            "COMPLETED": set(),
            "FAILED": set()
        }
        
        for record in session_records:
            history = record.get("status_history", [])
            for i in range(len(history) - 1):
                result.checked_constraints += 1
                curr = history[i]
                nxt = history[i+1]
                if nxt not in valid_transitions.get(curr, set()):
                    result.add_violation(IntegrityViolation(
                        "valid_status_transition",
                        "invalid_transition",
                        f"Invalid transition from {curr} to {nxt}",
                        [record.get("session_id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
                    
        return result

    def validate_transcript_continuity(self, segments: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        segments_by_session = {}
        for seg in segments:
            segments_by_session.setdefault(seg.get("session_id"), []).append(seg)
            
        for session_id, segs in segments_by_session.items():
            segs.sort(key=lambda x: x.get("segment_index", 0))
            for i, seg in enumerate(segs):
                result.checked_constraints += 1
                if seg.get("segment_index") != i:
                    result.add_violation(IntegrityViolation(
                        "sequential_index",
                        "gap_found",
                        f"Expected index {i}, got {seg.get('segment_index')}",
                        [seg.get("segment_id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
                    
                if i > 0:
                    prev = segs[i-1]
                    result.checked_constraints += 1
                    if seg.get("start_time", 0) < prev.get("start_time", 0):
                        result.add_violation(IntegrityViolation(
                            "monotonic_time",
                            "time_reversal",
                            f"Start time decreased from {prev.get('start_time')} to {seg.get('start_time')}",
                            [seg.get("segment_id", "unknown")]
                        ))
                    else:
                        result.passed_constraints += 1
                        
                    result.checked_constraints += 1
                    if seg.get("start_time", 0) < prev.get("end_time", 0) and seg.get("speaker_label") == prev.get("speaker_label"):
                         result.add_violation(IntegrityViolation(
                            "no_speaker_overlap",
                            "overlapping_segments",
                            f"Overlapping segments for same speaker",
                            [seg.get("segment_id", "unknown"), prev.get("segment_id", "unknown")]
                        ))
                    else:
                        result.passed_constraints += 1
        return result

    def validate_feature_versioning(self, feature_records: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        groups = {}
        for f in feature_records:
            k = (f.get("session_id"), f.get("feature_name"))
            groups.setdefault(k, []).append(f)
            
        for k, records in groups.items():
            records.sort(key=lambda x: x.get("version", 0))
            for i, rec in enumerate(records):
                result.checked_constraints += 1
                expected_v = i + 1
                if rec.get("version") != expected_v:
                    result.add_violation(IntegrityViolation(
                        "sequential_versions",
                        "version_gap",
                        f"Expected version {expected_v}, got {rec.get('version')}",
                        [rec.get("id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
        return result

    def validate_referential_integrity(self, db_snapshot: Dict[str, List[Dict]]) -> IntegrityResult:
        result = IntegrityResult()
        sessions = {s.get("session_id") for s in db_snapshot.get("sessions", []) if s.get("session_id")}
        
        tables_with_fks = ["audio_chunks", "transcript_segments", "feature_results"]
        for table in tables_with_fks:
            records = db_snapshot.get(table, [])
            for rec in records:
                result.checked_constraints += 1
                sid = rec.get("session_id")
                if sid not in sessions:
                    result.add_violation(IntegrityViolation(
                        "foreign_key_valid",
                        "missing_parent",
                        f"Invalid session_id {sid} in {table}",
                        [rec.get("id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
        return result

    def validate_search_index_completeness(self, segments: List[Dict], embeddings: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        segment_ids = {s.get("segment_id") for s in segments if s.get("segment_id")}
        embedded_ids = {e.get("segment_id") for e in embeddings if e.get("segment_id")}
        
        result.checked_constraints += 1
        missing = segment_ids - embedded_ids
        if missing:
            result.add_violation(IntegrityViolation(
                "index_completeness",
                "missing_embeddings",
                f"{len(missing)} segments missing embeddings",
                list(missing)[:10]
            ))
        else:
            result.passed_constraints += 1
            
        result.checked_constraints += 1
        orphaned = embedded_ids - segment_ids
        if orphaned:
             result.add_violation(IntegrityViolation(
                "index_completeness",
                "orphaned_embeddings",
                f"{len(orphaned)} orphaned embeddings",
                list(orphaned)[:10]
            ))
        else:
            result.passed_constraints += 1
            
        return result

    def validate_audio_chunk_integrity(self, chunks: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        session_chunks = {}
        for c in chunks:
            session_chunks.setdefault(c.get("session_id"), []).append(c)
            
        for sid, chks in session_chunks.items():
            chks.sort(key=lambda x: x.get("chunk_index", 0))
            checksums = set()
            for i, c in enumerate(chks):
                result.checked_constraints += 1
                if c.get("chunk_index") != i:
                    result.add_violation(IntegrityViolation(
                        "sequential_chunks",
                        "chunk_gap",
                        f"Expected chunk {i}, got {c.get('chunk_index')}",
                        [c.get("id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
                    
                result.checked_constraints += 1
                csum = c.get("checksum")
                if csum in checksums:
                    result.add_violation(IntegrityViolation(
                        "unique_checksum",
                        "duplicate_checksum",
                        f"Duplicate checksum found: {csum}",
                        [c.get("id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
                    checksums.add(csum)
                    
                result.checked_constraints += 1
                key = c.get("s3_key")
                if not key or not isinstance(key, str) or len(key) < 5:
                     result.add_violation(IntegrityViolation(
                        "valid_s3_key",
                        "invalid_key",
                        f"Invalid S3 key: {key}",
                        [c.get("id", "unknown")]
                    ))
                else:
                    result.passed_constraints += 1
                    
        return result

    def validate_idempotency(self, operations_log: List[Dict]) -> IntegrityResult:
        result = IntegrityResult()
        ops = {}
        for op in operations_log:
            k = (op.get("operation"), op.get("input_hash"))
            ops.setdefault(k, []).append(op)
            
        for k, op_group in ops.items():
            if len(op_group) > 1:
                base_out = op_group[0].get("output_hash")
                for other in op_group[1:]:
                    result.checked_constraints += 1
                    if other.get("output_hash") != base_out:
                        result.add_violation(IntegrityViolation(
                            "idempotency",
                            "divergent_outputs",
                            f"Operation {k[0]} produced divergent outputs for same input",
                            [other.get("id", "unknown")]
                        ))
                    else:
                        result.passed_constraints += 1
        return result
