import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

class ProfileManager:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.profiles_path = self.data_dir / "profiles.json"
        self.ha_users_path = self.data_dir / "ha_users.json"
        self.profiles: Dict[str, Dict] = {}
        self.ha_users: List[Dict] = []
        self.load()

    def load(self):
        if self.profiles_path.exists():
            try:
                with open(self.profiles_path, "r") as f:
                    self.profiles = json.load(f)
            except Exception as e:
                _LOGGER.error(f"Error loading profiles: {e}")
                self.profiles = {}
        if self.ha_users_path.exists():
            try:
                with open(self.ha_users_path, "r") as f:
                    self.ha_users = json.load(f)
            except Exception as e:
                _LOGGER.error(f"Error loading ha_users: {e}")
                self.ha_users = []

    def save(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.profiles_path, "w") as f:
                json.dump(self.profiles, f, indent=4)
        except Exception as e:
            _LOGGER.error(f"Error saving profiles: {e}")

    def save_ha_users(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.ha_users_path, "w") as f:
                json.dump(self.ha_users, f, indent=4)
        except Exception as e:
            _LOGGER.error(f"Error saving ha_users: {e}")

    def get_profiles(self) -> List[Dict]:
        return [
            {"name": name, "plates": data.get("plates", []), "user_id": data.get("user_id")}
            for name, data in self.profiles.items()
        ]

    def update_profile(self, name: str, plates: List[str] = None, user_id: str = None):
        if name not in self.profiles:
            self.profiles[name] = {"plates": [], "user_id": None}
        
        if plates is not None:
            self.profiles[name]["plates"] = plates
        if user_id is not None:
            self.profiles[name]["user_id"] = user_id if user_id else None
            
        self.save()

    def delete_profile(self, name: str):
        if name in self.profiles:
            del self.profiles[name]
            self.save()

    def get_name_by_plate(self, plate: str) -> Optional[str]:
        for name, data in self.profiles.items():
            if plate in data.get("plates", []):
                return name
        return None

    def get_ha_users(self) -> List[Dict]:
        return self.ha_users

    def set_ha_users(self, users: List[Dict]):
        self.ha_users = users
        self.save_ha_users()
