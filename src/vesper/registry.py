import yaml
from pathlib import Path
from pydantic import ValidationError
from typing import Tuple, List
from vesper.models import manifest_adapter, VesperManifest
from vesper.exceptions import InvalidAgentSpecError
from vesper.storage import VesperDatabase

class AgentRegistry:
    def __init__(self, db: VesperDatabase):
        self.db = db
        
    def validate_manifest(self, file_path: str) -> VesperManifest:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Error: File not found at {file_path}")
            
        with open(path, "r") as f:
            raw_data = yaml.safe_load(f)
            
        try:
            manifest = manifest_adapter.validate_python(raw_data)
        except ValidationError as e:
            error_msgs = []
            for err in e.errors():
                loc = ".".join([str(loc) for loc in err['loc']])
                msg = err['msg']
                error_msgs.append(f"  - {loc}: {msg}")
            
            clean_error_str = "\n".join(error_msgs)
            raise InvalidAgentSpecError(f"Error: YAML structure is invalid\n{clean_error_str}")
                    
        return manifest

    def apply_manifest(self, file_path: str) -> Tuple[VesperManifest, str, int]:
        """Validates the YAML and saves it to the database."""

        manifest = self.validate_manifest(file_path)
        new_id, new_version = self.db.save_agent_spec(manifest)
        
        return manifest, new_id, new_version
    
    def get_all_resources(self) -> List[Tuple[str, str, int]]:
        """Returns all active resources (agents and fleets) from the database."""
        
        return self.db.get_resources()        
    
    def get_history(self, name: str) -> List[Tuple[int, str]]:
        """Returns history of a resource."""
        return self.db.get_history(name)