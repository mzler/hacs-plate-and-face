"""Face database management – store and retrieve known face encodings."""
from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from homeassistant.core import HomeAssistant

from .const import FACES_SUBDIR

_LOGGER = logging.getLogger(__name__)


class FaceManager:
    """
    Manages the database of known faces.

    Faces are stored as a pickle file in the HA config directory under
    ``<config>/plate_face_recognition/known_faces.pkl``.

    The in-memory representation is:
        {
            "Alice":  [encoding1, encoding2, ...],
            "Bob":    [encoding1],
            ...
        }
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._db_path = Path(hass.config.config_dir) / FACES_SUBDIR / "known_faces.pkl"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._faces: dict[str, list[np.ndarray]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load face database from disk."""
        if not self._db_path.exists():
            self._faces = {}
            return
        try:
            with open(self._db_path, "rb") as f:
                self._faces = pickle.load(f)
            _LOGGER.info(
                "Loaded %d known face(s) from %s", len(self._faces), self._db_path
            )
        except Exception as exc:
            _LOGGER.error("Could not load face database: %s", exc)
            self._faces = {}

    def _save(self) -> None:
        """Persist face database to disk."""
        try:
            with open(self._db_path, "wb") as f:
                pickle.dump(self._faces, f)
            _LOGGER.debug("Face database saved (%d names).", len(self._faces))
        except Exception as exc:
            _LOGGER.error("Could not save face database: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def known_names(self) -> list[str]:
        """Return sorted list of registered names."""
        return sorted(self._faces.keys())

    def flat_encodings_and_names(self) -> tuple[list[np.ndarray], list[str]]:
        """
        Return a flat list of encodings and a parallel list of names.

        Each encoding maps to the name at the same index.
        """
        encodings: list[np.ndarray] = []
        names: list[str] = []
        for name, enc_list in self._faces.items():
            for enc in enc_list:
                encodings.append(enc)
                names.append(name)
        return encodings, names

    def add_face(self, name: str, encodings: list[np.ndarray]) -> int:
        """
        Add *encodings* for *name*.  Existing encodings for that name are kept.

        Returns the total number of encodings stored for this name.
        """
        name = name.strip()
        if not name:
            raise ValueError("Name must not be empty.")
        if not encodings:
            raise ValueError("No face encodings provided.")

        existing = self._faces.get(name, [])
        existing.extend(encodings)
        self._faces[name] = existing
        self._save()
        _LOGGER.info(
            "Registered %d encoding(s) for '%s' (total: %d).",
            len(encodings),
            name,
            len(existing),
        )
        return len(existing)

    def delete_face(self, name: str) -> bool:
        """
        Remove all encodings for *name*.

        Returns True if the name was found and removed.
        """
        if name in self._faces:
            del self._faces[name]
            self._save()
            _LOGGER.info("Deleted face '%s' from database.", name)
            return True
        _LOGGER.warning("Face '%s' not found in database.", name)
        return False

    def rename_face(self, old_name: str, new_name: str) -> bool:
        """Rename a face entry."""
        if old_name not in self._faces:
            return False
        self._faces[new_name] = self._faces.pop(old_name)
        self._save()
        return True

    def face_count(self) -> dict[str, int]:
        """Return mapping of name → number of training images."""
        return {name: len(encs) for name, encs in self._faces.items()}
