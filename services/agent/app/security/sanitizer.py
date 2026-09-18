import re
from typing import Any

class InputSanitizer:
    @classmethod
    def sanitize(cls, value: Any, field_name: str) -> Any:
        if isinstance(value, str):
            cls._check_patterns(value, field_name)
            return value.replace('\0', '')
        elif isinstance(value, dict):
            return {k: cls.sanitize(v, k) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.sanitize(v, field_name) for v in value]
        return value

    @classmethod
    def _check_patterns(cls, text: str, field_name: str):
        text_upper = text.upper()
        sql_patterns = ['DROP ', 'ALTER ', 'DELETE ', 'UNION SELECT ', '1=1', 'SLEEP(', 'BENCHMARK(']
        for p in sql_patterns:
            if p in text_upper:
                raise ValueError(f"Potential SQL injection detected in {field_name}")

        prompt_inj_patterns = ['IGNORE PREVIOUS', 'SYSTEM:', '<|IM_START|>', '[INST]']
        for p in prompt_inj_patterns:
            if p in text_upper:
                raise ValueError(f"Potential prompt injection detected in {field_name}")

        if '<script' in text.lower() or 'javascript:' in text.lower() or re.search(r'on\w+\s*=', text.lower()):
            raise ValueError(f"Potential XSS detected in {field_name}")
