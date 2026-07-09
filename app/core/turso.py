"""Cliente minimo para o Turso/libSQL via API HTTP (Hrana v2 pipeline).

Python puro (urllib) — sem dependencia nativa, funciona em qualquer SO.
Usado para: (1) contas de usuario e (2) backup/restauracao dos bancos
por usuario. Dialeto e SQLite, entao o SQL e o mesmo do sqlite3.
"""
from __future__ import annotations

import base64
import json
import urllib.request
from typing import Any


class TursoError(RuntimeError):
    pass


class TursoClient:
    def __init__(self, url: str, auth_token: str, timeout: int = 30) -> None:
        # aceita libsql://, https:// ou wss:// e normaliza para https
        host = url.replace("libsql://", "https://").replace("wss://", "https://")
        self.endpoint = host.rstrip("/") + "/v2/pipeline"
        self.token = auth_token
        self.timeout = timeout

    @staticmethod
    def _encode_arg(value: Any) -> dict[str, Any]:
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "integer", "value": str(int(value))}
        if isinstance(value, int):
            return {"type": "integer", "value": str(value)}
        if isinstance(value, float):
            return {"type": "float", "value": value}
        if isinstance(value, (bytes, bytearray)):
            return {"type": "blob", "base64": base64.b64encode(bytes(value)).decode()}
        return {"type": "text", "value": str(value)}

    @staticmethod
    def _decode_value(cell: dict[str, Any]) -> Any:
        kind = cell.get("type")
        if kind == "null":
            return None
        if kind == "integer":
            return int(cell["value"])
        if kind == "float":
            return float(cell["value"])
        if kind == "blob":
            b64 = cell.get("base64", "")
            b64 += "=" * (-len(b64) % 4)  # Turso pode omitir o padding
            return base64.b64decode(b64)
        return cell.get("value")

    def execute(self, sql: str, args: list[Any] | None = None) -> dict[str, Any]:
        """Executa uma instrucao e retorna {rows, last_insert_rowid, affected}."""
        stmt = {"sql": sql, "args": [self._encode_arg(a) for a in (args or [])]}
        payload = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)

        first = data["results"][0]
        if first.get("type") != "ok":
            raise TursoError(str(first.get("error") or "erro desconhecido no Turso"))
        result = first["response"]["result"]
        cols = [c["name"] for c in result["cols"]]
        rows = [
            {cols[i]: self._decode_value(cell) for i, cell in enumerate(row)}
            for row in result["rows"]
        ]
        return {
            "rows": rows,
            "last_insert_rowid": int(result["last_insert_rowid"]) if result.get("last_insert_rowid") else None,
            "affected": result.get("affected_row_count", 0),
        }

    def ping(self) -> bool:
        try:
            self.execute("SELECT 1")
            return True
        except Exception:
            return False
