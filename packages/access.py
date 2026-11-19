"""Verified identities shared by the gateway and agent."""

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, HTTPException, WebSocketException
from starlette.requests import HTTPConnection


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: UUID
    role: str = "member"
    device_id: str | None = None


@lru_cache(maxsize=1)
def _credentials(config: str) -> tuple[tuple[str, Principal], ...]:
    return tuple(
        (digest, Principal(
            item["user_id"], UUID(item["workspace_id"]), item.get("role", "member"),
            item.get("device_id"),
        ))
        for digest, item in json.loads(config).items()
    )


def authenticate(token: str) -> Principal | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
        return None
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    for expected, principal in _credentials(os.getenv("PROHUMAN_CREDENTIALS") or "{}"):
        if hmac.compare_digest(digest, expected):
            if principal.role in {"admin", "member"} or (
                principal.role == "device" and principal.device_id
            ):
                return principal
            return None
    return None


def require_principal(connection: HTTPConnection) -> Principal:
    scheme, _, token = connection.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer":
        token = ""
    is_socket = connection.scope["type"] == "websocket"
    if is_socket and not token:
        token = next(
            (protocol.removeprefix("bearer.") for protocol in connection.scope["subprotocols"]
             if protocol.startswith("bearer.")),
            "",
        )
    principal = authenticate(token)
    if principal:
        return principal
    if is_socket:
        raise WebSocketException(code=1008, reason="Authentication required")
    raise HTTPException(
        status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"}
    )


def require_member(principal: Principal = Depends(require_principal)) -> Principal:
    if principal.role not in {"admin", "member"}:
        raise HTTPException(status_code=403, detail="Workspace membership required")
    return principal


def require_admin(principal: Principal = Depends(require_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal
