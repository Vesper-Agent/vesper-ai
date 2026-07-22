from abc import ABC, abstractmethod
from typing import List, Tuple
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
        pass
    
    @abstractmethod
    def get_resources(self) -> List[Tuple[str, str, int]]:
        """Returns all active resources (agents and fleets) from the database."""
        pass

    @abstractmethod
    def get_history(self, name: str) -> List[Tuple[int, str]]:
        """Returns history of a resource (agent or agent-fleet)"""
        pass