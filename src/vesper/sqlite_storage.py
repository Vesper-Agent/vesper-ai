import sqlite3, uuid, os
from typing import Tuple
from vesper.models import VesperManifest
from vesper.storage import VesperDatabase
from vesper.exceptions import NoChangeDetectedError

class SQLiteVesperDatabase(VesperDatabase):
    def __init__(self, db_path: str = "./vesper.db"):
        self.db_path = os.path.expanduser(db_path)
        self.setup_tables()
        

    def _get_connection(self):
        """Helper method to get a configured database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def setup_tables(self) -> None:
        """Creates 'resources' and 'manifests' tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    active_version_id TEXT
                )               
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manifests (
                    id TEXT PRIMARY KEY,
                    resource_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    FOREIGN KEY (resource_name) REFERENCES resources (name) ON DELETE CASCADE,
                    UNIQUE (resource_name, version)
                )               
            """)
            
        
    def save_agent_spec(self, manifest: VesperManifest) -> Tuple[str, int]:
        """Saves the manifest into the database."""
        
        new_json = manifest.model_dump_json()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT active_version_id FROM resources WHERE name = ?", (manifest.name, ))
            resource_row = cursor.fetchone()
            
            if resource_row:
                active_version_id = resource_row['active_version_id']
                
                cursor.execute("SELECT version, content_json FROM manifests WHERE id = ?", (active_version_id, ))
                manifest_row = cursor.fetchone()
                
                if manifest_row:
                    current_json = manifest_row['content_json']
                    current_version = manifest_row['version']
                    
                    if current_json == new_json:
                        raise NoChangeDetectedError(
                            f"State unchanged. '{manifest.name}' is already running version {current_version}."
                        )
                    
                    new_version = current_version + 1
                    
                else:
                    new_version = 1
                    
                new_id = uuid.uuid4().hex
                
                cursor.execute(
                    "INSERT INTO manifests (id, resource_name, version, content_json) VALUES (?, ?, ?, ?)",
                    (new_id, manifest.name, new_version, new_json)
                )
                cursor.execute(
                    "UPDATE resources SET active_version_id = ? WHERE name = ?",
                    (new_id, manifest.name)
                )
                
                return new_id, new_version
            
            else:    
                new_id = uuid.uuid4().hex
                new_version = 1
                
                cursor.execute(
                    "INSERT INTO resources (name, kind, active_version_id) VALUES (?, ?, ?)",
                    (manifest.name, manifest.kind, new_id)
                )
                cursor.execute(
                    "INSERT INTO manifests (id, resource_name, version, content_json) VALUES (?, ?, ?, ?)",
                    (new_id, manifest.name, new_version, new_json)
                )
                
                return new_id, new_version