"""
Runtime procedure retrieval from canonical TSS (Test Support System).

This module implements a runtime-only fetcher that retrieves authoritative
procedures from a TSS server, verifies integrity (HMAC-SHA256), caches results
in memory for a short TTL, and records audit metadata (not procedure content).

Behavior:
- If `TSS_URL` is not set, the store will be a no-op and return None.
- Procedures are never written to disk; only metadata (id, timestamp, requester,
  status) may be appended to an audit log.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from procedures import Procedure, ProcedureStep

logger = logging.getLogger(__name__)


class ProcedureStore:
    def __init__(self,
                 tss_url: Optional[str] = None,
                 hmac_secret: Optional[str] = None,
                 cache_ttl: int = 300,
                 audit_log_path: Optional[str] = None):
        self.tss_url = tss_url
        self.hmac_secret = hmac_secret.encode() if hmac_secret else None
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Any] = {}
        self._cache_times: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.audit_log_path = audit_log_path

    def _audit(self, proc_id: str, requester: str, status: str, reason: Optional[str] = None):
        # Only record metadata; do NOT store procedure content
        entry = {
            "ts": int(time.time()),
            "proc_id": proc_id,
            "requester": requester,
            "status": status,
            "reason": reason,
        }
        line = json.dumps(entry)
        logger.info(f"Procedure audit: {line}")
        if self.audit_log_path:
            try:
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                logger.warning(f"Failed to write audit log: {e}")

    def _is_cache_valid(self, proc_id: str) -> bool:
        t = self._cache_times.get(proc_id)
        if t is None:
            return False
        return (time.time() - t) < self.cache_ttl

    def _parse_procedure(self, payload: Dict[str, Any]) -> Optional[Procedure]:
        # Expect payload to contain 'name', 'description', 'mission_phase', 'steps' list
        try:
            steps = []
            for s in payload.get("steps", []):
                steps.append(ProcedureStep(
                    number=int(s.get("number")),
                    action=str(s.get("action")),
                    target=str(s.get("target", "")),
                    wait_condition=s.get("wait_condition"),
                    notes=s.get("notes"),
                ))
            proc = Procedure(
                name=payload.get("name", "unknown"),
                description=payload.get("description", ""),
                mission_phase=payload.get("mission_phase", ""),
                steps=steps,
            )
            return proc
        except Exception as e:
            logger.exception(f"Failed to parse procedure payload: {e}")
            return None

    def fetch_procedure(self, proc_id: str, requester: str = "local") -> Optional[Procedure]:
        """Fetch a procedure by id from the TSS and verify HMAC signature.

        Returns a `Procedure` instance on success, otherwise None.
        """
        if not self.tss_url:
            logger.debug("TSS_URL not configured; skipping remote fetch")
            self._audit(proc_id, requester, "tss_unconfigured")
            return None

        # Cache check
        with self._lock:
            if proc_id in self._cache and self._is_cache_valid(proc_id):
                logger.debug(f"Procedure {proc_id} served from cache")
                self._audit(proc_id, requester, "cache_hit")
                return self._cache[proc_id]

        url = f"{self.tss_url.rstrip('/')}/procedures/{proc_id}"
        try:
            import requests

            r = requests.get(url, timeout=5)
            r.raise_for_status()
            payload = r.json()

            # Expect payload: {"procedure": { ... }, "signature": "hex"}
            proc_json = payload.get("procedure")
            signature = payload.get("signature")
            if not proc_json:
                self._audit(proc_id, requester, "no_procedure_in_response")
                return None

            # Verify HMAC if secret present
            if self.hmac_secret:
                if not signature:
                    self._audit(proc_id, requester, "missing_signature")
                    return None
                computed = hmac.new(self.hmac_secret, json.dumps(proc_json, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(computed, signature):
                    self._audit(proc_id, requester, "invalid_signature")
                    logger.warning("Procedure signature mismatch")
                    return None

            proc = self._parse_procedure(proc_json)
            if proc is None:
                self._audit(proc_id, requester, "parse_failed")
                return None

            with self._lock:
                self._cache[proc_id] = proc
                self._cache_times[proc_id] = time.time()

            self._audit(proc_id, requester, "fetched_remote")
            return proc

        except Exception as e:
            logger.exception(f"Failed to fetch procedure {proc_id} from TSS: {e}")
            self._audit(proc_id, requester, "fetch_error", reason=str(e))
            return None


# Module-level singleton configured from env
TSS_URL = os.getenv("TSS_URL")
HMAC_SECRET = os.getenv("PROCEDURE_HMAC_SECRET")
AUDIT_LOG = os.getenv("PROCEDURE_AUDIT_LOG", os.path.join(os.getcwd(), "procedure_requests.log"))

store = ProcedureStore(tss_url=TSS_URL, hmac_secret=HMAC_SECRET, cache_ttl=int(os.getenv("PROCEDURE_CACHE_TTL", "300")), audit_log_path=AUDIT_LOG)


def get_procedure(proc_id: str, requester: str = "local", fallback: Optional[Procedure] = None) -> Optional[Procedure]:
    """Public helper: try TSS first, return fallback if provided and remote unavailable."""
    p = store.fetch_procedure(proc_id, requester=requester)
    if p:
        return p
    return fallback
