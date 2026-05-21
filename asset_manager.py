"""
AssetManager — plug-and-play cosmetic asset system for Pip.

Assets live in ~/.config/pip-companion/items/<item_id>/
Each folder contains:
  manifest.json  — metadata (id, name, category, anchor, frames)
  sprite.json    — pixel rectangles list

equipped.json at ~/.config/pip-companion/equipped.json tracks which
item is currently worn per category (hat, accessory, palette…).
"""
import json
import logging
import shutil
import zipfile
from pathlib import Path

log = logging.getLogger("pip.assets")


class AssetManager:
    ITEMS_DIR    = Path.home() / ".config" / "pip-companion" / "items"
    EQUIPPED_FILE = Path.home() / ".config" / "pip-companion" / "equipped.json"

    def __init__(self):
        # Ensure the items directory exists
        self.ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Catalog ───────────────────────────────────────────────────────────────

    def load_catalog(self) -> list[dict]:
        """Scan ITEMS_DIR for valid asset folders and return their manifests."""
        catalog: list[dict] = []
        if not self.ITEMS_DIR.exists():
            return catalog
        for item_dir in sorted(self.ITEMS_DIR.iterdir()):
            if not item_dir.is_dir():
                continue
            manifest_path = item_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["_path"] = str(item_dir)
                catalog.append(manifest)
            except Exception as exc:
                log.warning("Failed to load manifest at %s: %s", manifest_path, exc)
        return catalog

    # ── Equipped state ────────────────────────────────────────────────────────

    def get_equipped(self) -> dict:
        """Return the equipped.json dict, e.g. {"hat": "hat_witch", "palette": None}."""
        if not self.EQUIPPED_FILE.exists():
            return {}
        try:
            return json.loads(self.EQUIPPED_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to read equipped.json: %s", exc)
            return {}

    def equip(self, category: str, item_id: str | None):
        """Equip (or unequip with item_id=None) an item in a given category."""
        equipped = self.get_equipped()
        if item_id is None:
            equipped.pop(category, None)
        else:
            equipped[category] = item_id
        try:
            self.EQUIPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.EQUIPPED_FILE.write_text(
                json.dumps(equipped, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            log.error("Failed to save equipped.json: %s", exc)

    # ── Overlay loading ───────────────────────────────────────────────────────

    def get_overlay(self, category: str) -> dict | None:
        """
        Return the combined overlay dict for the currently equipped item in *category*,
        or None if nothing is equipped / item is missing.

        Returned dict shape:
            {
                "anchor_x": int,
                "anchor_y": int,
                "pixels": [{"x", "y", "w", "h", "color"}, ...],
            }
        """
        equipped = self.get_equipped()
        item_id = equipped.get(category)
        if not item_id:
            return None

        item_dir = self.ITEMS_DIR / item_id
        manifest_path = item_dir / "manifest.json"
        sprite_path   = item_dir / "sprite.json"

        if not manifest_path.exists() or not sprite_path.exists():
            log.debug("Overlay files missing for %s/%s", category, item_id)
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sprite   = json.loads(sprite_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to load overlay for %s: %s", item_id, exc)
            return None

        anchor = manifest.get("anchor", {})
        return {
            "anchor_x": anchor.get("offset_x", 0),
            "anchor_y": anchor.get("offset_y", -6),
            "pixels":   sprite.get("pixels", []),
        }

    # ── Installation helpers ──────────────────────────────────────────────────

    def install_from_zip(self, zip_path: str) -> bool:
        """
        Extract a .zip asset pack into ITEMS_DIR.

        The zip may contain a single top-level folder (the asset id) or the
        manifest.json directly at the root; both layouts are handled.
        Returns True on success.
        """
        zip_path_obj = Path(zip_path)
        if not zip_path_obj.exists():
            log.error("install_from_zip: file not found: %s", zip_path)
            return False

        try:
            with zipfile.ZipFile(zip_path_obj, "r") as zf:
                names = zf.namelist()
                if not names:
                    log.warning("install_from_zip: empty zip: %s", zip_path)
                    return False

                # Detect if there is a common top-level folder
                top_dirs = {n.split("/")[0] for n in names if "/" in n}
                has_root_manifest = "manifest.json" in names

                if has_root_manifest:
                    # Flat layout: derive item_id from the zip filename
                    item_id = zip_path_obj.stem
                    dest = self.ITEMS_DIR / item_id
                    dest.mkdir(parents=True, exist_ok=True)
                    for member in names:
                        if member.endswith("/"):
                            continue
                        data = zf.read(member)
                        out = dest / Path(member).name
                        out.write_bytes(data)
                elif len(top_dirs) == 1:
                    # Single subfolder layout: extract preserving that subfolder
                    zf.extractall(self.ITEMS_DIR)
                else:
                    # Multiple top-level folders: extract all as-is
                    zf.extractall(self.ITEMS_DIR)

            log.info("Installed asset from zip: %s", zip_path)
            return True
        except Exception as exc:
            log.error("install_from_zip failed for %s: %s", zip_path, exc)
            return False

    def install_from_folder(self, folder_path: str) -> bool:
        """
        Copy an asset folder into ITEMS_DIR.  The folder must contain a
        manifest.json; the destination name is taken from the manifest's "id"
        field (falling back to the folder's basename).
        Returns True on success.
        """
        src = Path(folder_path)
        if not src.is_dir():
            log.error("install_from_folder: not a directory: %s", folder_path)
            return False

        manifest_path = src / "manifest.json"
        if not manifest_path.exists():
            log.error("install_from_folder: no manifest.json in %s", folder_path)
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            item_id  = manifest.get("id") or src.name
        except Exception:
            item_id = src.name

        dest = self.ITEMS_DIR / item_id
        if dest.exists():
            shutil.rmtree(dest)
        try:
            shutil.copytree(str(src), str(dest))
            log.info("Installed asset from folder: %s → %s", folder_path, dest)
            return True
        except Exception as exc:
            log.error("install_from_folder failed: %s", exc)
            return False
