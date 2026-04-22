"""Kill-switch router — every outbound send is rewritten to the sink when unset.

Default: disabled → recipient rewritten to `config.killswitch.sink_email` /
`sink_shortcode`. Audit log is append-only with a running SHA-256 hash.

See __specs/16-data-handling-and-kill-switch.md.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()


class KillSwitch:
    def __init__(
        self,
        *,
        enabled: bool,
        sink_email: str,
        sink_shortcode: str,
        audit_log_path: str,
        require_real_outbound_env: bool,
        env_flag: bool,
    ) -> None:
        self.enabled = enabled and (env_flag or not require_real_outbound_env)
        self.sink_email = sink_email
        self.sink_shortcode = sink_shortcode
        self.audit_log_path = pathlib.Path(audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #

    def route_email(self, to: str, trace_id: str) -> str:
        if not self.enabled:
            self._audit("email", intended=to, routed=self.sink_email, trace_id=trace_id)
            return self.sink_email
        self._audit("email", intended=to, routed=to, trace_id=trace_id)
        return to

    def route_sms(self, to_number: str, trace_id: str) -> str:
        if not self.enabled:
            self._audit("sms", intended=to_number, routed=self.sink_shortcode, trace_id=trace_id)
            return self.sink_shortcode
        self._audit("sms", intended=to_number, routed=to_number, trace_id=trace_id)
        return to_number

    # ------------------------------------------------------------------ #
    # Audit — Merkle-chain-style
    # ------------------------------------------------------------------ #

    def _audit(self, channel: str, *, intended: str, routed: str, trace_id: str) -> None:
        with _LOCK:
            prev_hash = self._last_hash()
            rec: dict[str, Any] = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "channel": channel,
                "intended_to": intended,
                "routed_to": routed,
                "trace_id": trace_id,
                "switch_enabled": self.enabled,
                "prev_hash": prev_hash,
            }
            payload = json.dumps(rec, sort_keys=True)
            rec["hash"] = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
            with self.audit_log_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")

    def _last_hash(self) -> str:
        if not self.audit_log_path.exists():
            return "genesis"
        last = ""
        for line in self.audit_log_path.read_text().splitlines():
            if line.strip():
                last = line
        if not last:
            return "genesis"
        try:
            return json.loads(last).get("hash", "genesis")
        except json.JSONDecodeError:
            return "genesis"


def from_config(cfg, secrets) -> KillSwitch:  # type: ignore[no-untyped-def]
    ks_cfg = cfg.get("killswitch", default={}) or {}
    return KillSwitch(
        enabled=bool(ks_cfg.get("enabled", False)),
        sink_email=ks_cfg.get("sink_email", "sink+convergine@staff-sandbox.tenacious.invalid"),
        sink_shortcode=ks_cfg.get("sink_shortcode", "22222"),
        audit_log_path=ks_cfg.get("audit_log_path", "data/killswitch_audit.jsonl"),
        require_real_outbound_env=bool(ks_cfg.get("require_real_outbound_env", True)),
        env_flag=bool(secrets.convergine_enable_real_outbound),
    )
