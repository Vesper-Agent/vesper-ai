from typing import Literal, List, Optional
from pydantic import BaseModel, Field, TypeAdapter, ConfigDict

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class MemoryConfig(StrictBaseModel):
    scope: str
    retentionDays: int
    strategy: Optional[str] = None

class BudgetConfig(StrictBaseModel):
    maxCostPerRun: Optional[float] = None
    alertAt: Optional[float] = None

class AgentSpec(StrictBaseModel):
    name: str
    model: str
    entryPoint: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    memory: Optional[MemoryConfig] = None
    budget: Optional[BudgetConfig] = None

class AgentManifest(AgentSpec):
    apiVersion: Literal["vesper/v1"]
    kind: Literal["Agent"]

VesperManifest = AgentManifest
manifest_adapter = TypeAdapter(VesperManifest)
