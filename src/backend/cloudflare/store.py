import json
import os
from pathlib import Path


class TunnelStateStorage:
    """
    JSON state:
    {
      "api_token": "...",
      "tunnels": {
        "pve-main": {
          "id": "...",
          "token": "...",
          "zones": ["example.com"]
        }
      }
    }
    """

    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        """
        Safe load state file.

        Любое повреждение файла -> fallback на пустое состояние.
        """
        if not self.path.exists():
            return {"api_token": None, "tunnels": {}}

        try:
            raw = self.path.read_text().strip()
            if not raw:
                raise ValueError("Empty state file")

            data = json.loads(raw)

            # минимальная валидация структуры
            if not isinstance(data, dict):
                raise ValueError("State is not a dict")

            data.setdefault("api_token", None)
            data.setdefault("tunnels", {})

            if not isinstance(data["tunnels"], dict):
                data["tunnels"] = {}

            return data

        except Exception:
            # ⚠️ state повреждён — лечим
            clean = {"api_token": None, "tunnels": {}}
            self.save(clean)
            return clean

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            # Best-effort on platforms that don't support chmod fully.
            pass

    # ---------- API token ----------

    def get_api_token(self) -> str | None:
        return self.load().get("api_token")

    def set_api_token(self, token: str) -> None:
        data = self.load()
        data["api_token"] = token
        self.save(data)

    # ---------- tunnels ----------

    def get_tunnel(self, name: str) -> dict | None:
        return self.load().get("tunnels", {}).get(name)

    def upsert_tunnel(
        self,
        *,
        name: str,
        tunnel_id: str,
        tunnel_token: str | None,
        zone: str | None = None,
    ) -> None:
        data = self.load()
        tunnels = data.setdefault("tunnels", {})
        entry = tunnels.setdefault(
            name,
            {"id": tunnel_id, "token": tunnel_token, "zones": []},
        )

        entry["id"] = tunnel_id
        if tunnel_token:
            entry["token"] = tunnel_token
        if zone and zone not in entry["zones"]:
            entry["zones"].append(zone)

        self.save(data)

    def remove_tunnel(self, name: str) -> None:
        data = self.load()
        if name in data.get("tunnels", {}):
            del data["tunnels"][name]
            self.save(data)
