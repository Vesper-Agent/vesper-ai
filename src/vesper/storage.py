from abc import ABC, abstractmethod
from typing import List, Dict, Any
from vesper.models import VesperManifest

class VesperDatabase(ABC):
    """This is a blueprint of Vesper's internal Database."""
    
    @abstractmethod
    def setup_tables(slef) -> None:
        """Creates agent table if not exists."""
        pass
    
    @abstractmethod
    def save_agent_spec(self, manifest: VesperManifest) -> None:
        """Saves a manifest in the database."""  
    
    