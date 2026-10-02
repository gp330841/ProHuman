import re
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

@dataclass
class ValidationError:
    field: str
    error_type: str
    message: str
    expected: Any
    actual: Any

@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    field_coverage: float = 0.0
    
    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)
        self.is_valid = False

class ContractValidator:
    def _is_valid_uuid(self, val: str) -> bool:
        try:
            uuid.UUID(str(val), version=4)
            return True
        except ValueError:
            return False

    def _is_valid_datetime(self, val: str) -> bool:
        try:
            datetime.fromisoformat(val.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False

    def _check_required(self, data: dict, fields: List[str], result: ValidationResult):
        for f in fields:
            if f not in data or data[f] is None:
                result.add_error(ValidationError(
                    field=f,
                    error_type="missing_required",
                    message=f"Missing required field: {f}",
                    expected="Present",
                    actual="Missing"
                ))

    def _calculate_coverage(self, data: dict, required: List[str], optional: List[str]) -> float:
        if not optional:
            return 100.0
        present = sum(1 for f in optional if data.get(f) is not None)
        return (present / len(optional)) * 100.0

    def validate_session_create(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        if not isinstance(data, dict):
            result.add_error(ValidationError("", "invalid_type", "Data must be dict", dict, type(data)))
            return result
            
        req = ["device_id", "audio_format", "sample_rate"]
        opt = ["language", "metadata"]
        self._check_required(data, req, result)
        
        if "device_id" in data and not str(data["device_id"]).strip():
            result.add_error(ValidationError("device_id", "constraint_violation", "device_id must be non-empty", "> 0 chars", 0))
            
        valid_formats = {"wav", "mp3", "flac", "ogg", "aac", "m4a", "webm"}
        if "audio_format" in data and data["audio_format"] not in valid_formats:
            result.add_error(ValidationError("audio_format", "invalid_type", "Invalid audio format", valid_formats, data.get("audio_format")))
            
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_session_response(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["id", "status", "device_id"]
        opt = ["created_at", "updated_at", "audio_format", "duration_seconds", "sample_rate", "s3_key", "metadata"]
        self._check_required(data, req, result)
        
        if "id" in data and not self._is_valid_uuid(data["id"]):
            result.add_error(ValidationError("id", "invalid_format", "Must be UUID4", "UUID4", data["id"]))
            
        valid_statuses = {"CREATED", "RECORDING", "PROCESSING", "TRANSCRIBING", "TRANSCRIBED", "INDEXING", "INDEXED", "EXTRACTING", "COMPLETED", "FAILED"}
        if "status" in data and data["status"] not in valid_statuses:
            result.add_error(ValidationError("status", "invalid_type", "Invalid status", valid_statuses, data.get("status")))
            
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_transcript_segment(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["segment_index", "start_time", "end_time", "text", "speaker_label"]
        opt = ["confidence", "language", "words", "word_timestamps", "embedding", "session_id", "id"]
        self._check_required(data, req, result)
        
        if "start_time" in data and "end_time" in data:
            if isinstance(data.get("start_time"), (int, float)) and isinstance(data.get("end_time"), (int, float)):
                if data["start_time"] < 0:
                    result.add_error(ValidationError("start_time", "out_of_range", "Must be >= 0", ">= 0", data["start_time"]))
                if data["end_time"] < data["start_time"]:
                    result.add_error(ValidationError("end_time", "out_of_range", "Must be >= start_time", f">= {data['start_time']}", data["end_time"]))
            else:
                 result.add_error(ValidationError("times", "invalid_type", "Times must be numbers", "float/int", type(data.get("start_time"))))

        if "confidence" in data and data["confidence"] is not None:
            if not (0 <= data["confidence"] <= 1):
                result.add_error(ValidationError("confidence", "out_of_range", "Confidence must be 0-1", "0-1", data["confidence"]))
                
        # Check words or word_timestamps
        words_data = data.get("words") or data.get("word_timestamps")
        if words_data and isinstance(words_data, list):
            for i, w in enumerate(words_data):
                if isinstance(w, dict):
                    w_res = self.validate_word_timestamp(w)
                    for err in w_res.errors:
                        err.field = f"words[{i}].{err.field}"
                        result.add_error(err)

        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result
        
    def validate_transcription_result(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["session_id", "segments", "status"]
        opt = ["language", "speakers_count"]
        self._check_required(data, req, result)
        
        if "segments" in data and isinstance(data["segments"], list):
            for i, s in enumerate(data["segments"]):
                s_res = self.validate_transcript_segment(s)
                for err in s_res.errors:
                    err.field = f"segments[{i}].{err.field}"
                    result.add_error(err)
        
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_word_timestamp(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        # Accept both "start"/"end" (contract) and "start_time"/"end_time" (DB)
        req = ["word"]
        opt = ["start", "end", "start_time", "end_time", "confidence", "speaker"]
        self._check_required(data, req, result)
        
        start = data.get("start") or data.get("start_time")
        end = data.get("end") or data.get("end_time")
        
        if start is not None and end is not None:
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                if start < 0:
                    result.add_error(ValidationError("start", "out_of_range", "Must be >= 0", ">= 0", start))
                if end < start:
                    result.add_error(ValidationError("end", "out_of_range", "Must be >= start", f">= {start}", end))
        
        conf = data.get("confidence")
        if conf is not None:
            if not (0 <= conf <= 1):
                result.add_error(ValidationError("confidence", "out_of_range", "Confidence must be 0-1", "0-1", conf))

        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_summary_result(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["title", "executive_summary", "key_topics", "participant_count"]
        opt = []
        self._check_required(data, req, result)
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_mom_result(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["attendees", "agenda_items", "decisions", "action_items", "executive_summary"]
        opt = ["follow_ups"]
        self._check_required(data, req, result)
        
        if "action_items" in data and isinstance(data["action_items"], list):
            for i, ai in enumerate(data["action_items"]):
                ai_res = self.validate_action_item(ai)
                for err in ai_res.errors:
                    err.field = f"action_items[{i}].{err.field}"
                    result.add_error(err)
                    
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_action_item(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["description", "assignee", "priority"]
        opt = ["source_quotes", "confidence", "due_date"]
        self._check_required(data, req, result)
        
        valid_priorities = {"critical", "high", "medium", "low"}
        if "priority" in data and data["priority"] not in valid_priorities:
            result.add_error(ValidationError("priority", "invalid_type", "Invalid priority", valid_priorities, data.get("priority")))
            
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_sentiment_result(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["overall_sentiment", "speaker_sentiments", "notable_moments", "trend"]
        opt = []
        self._check_required(data, req, result)
        
        valid_sentiments = {"positive", "negative", "neutral", "mixed"}
        if "overall_sentiment" in data and data["overall_sentiment"] not in valid_sentiments:
            result.add_error(ValidationError("overall_sentiment", "invalid_type", "Invalid sentiment", valid_sentiments, data.get("overall_sentiment")))
            
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_search_request(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["query", "mode"]
        opt = ["limit", "filters"]
        self._check_required(data, req, result)
        
        if "query" in data and isinstance(data["query"], str):
            if not (2 <= len(data["query"]) <= 500):
                result.add_error(ValidationError("query", "constraint_violation", "Query length must be 2-500", "2-500", len(data["query"])))
                
        valid_modes = {"vector", "text", "hybrid"}
        if "mode" in data and data["mode"] not in valid_modes:
            result.add_error(ValidationError("mode", "invalid_type", "Invalid mode", valid_modes, data.get("mode")))
            
        if "limit" in data and data["limit"] is not None:
            if not isinstance(data["limit"], int) or not (1 <= data["limit"] <= 50):
                result.add_error(ValidationError("limit", "out_of_range", "Limit must be 1-50", "1-50", data["limit"]))
                
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_search_result_item(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["segment_id", "session_id", "text", "rrf_score", "speaker_label", "start_time", "end_time"]
        opt = ["session_title", "speaker_name", "vector_rank", "text_rank", "session_date"]
        self._check_required(data, req, result)
        
        if "rrf_score" in data:
            score = data["rrf_score"]
            if not isinstance(score, (int, float)) or score < 0:
                result.add_error(ValidationError("rrf_score", "out_of_range", "RRF score must be non-negative", ">= 0", score))
        
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_feature_result(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["session_id", "feature_name", "data", "version"]
        opt = ["processing_time_ms", "provider_model", "id", "name"]
        self._check_required(data, req, result)
        
        if "version" in data:
            v = data["version"]
            if not isinstance(v, int) or v < 1:
                result.add_error(ValidationError("version", "out_of_range", "Version must be >= 1", ">= 1", v))
        
        if "feature_name" in data:
            valid_names = {"summary", "mom", "action_items", "sentiment", "follow_up"}
            if data["feature_name"] not in valid_names:
                result.add_error(ValidationError("feature_name", "invalid_type", f"Invalid feature name", valid_names, data["feature_name"]))
            
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result

    def validate_audio_chunk_meta(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        req = ["chunk_index", "session_id", "s3_key", "checksum", "size_bytes"]
        opt = ["duration_seconds"]
        self._check_required(data, req, result)
        
        if "checksum" in data and isinstance(data["checksum"], str):
            if not re.match(r'^[a-fA-F0-9]{64}$', data["checksum"]):
                 result.add_error(ValidationError("checksum", "invalid_format", "Checksum must be 64-char hex", "SHA-256 hex string", data["checksum"]))
                 
        result.field_coverage = self._calculate_coverage(data, req, opt)
        return result
