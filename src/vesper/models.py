from typing import Literal, List, Dict, Optional, Union, Annotated
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
    maxCostPerFleetRun: Optional[float] = None

class EvalConfig(StrictBaseModel):
    dataset: str
    passThreshold: float
    ciGate: bool

class TaskConfig(StrictBaseModel):
    agent: str
    dependsOn: List[str] = Field(default_factory=list)

class AgentSpec(StrictBaseModel):
    name: str
    model: str
    entryPoint: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    memory: Optional[MemoryConfig] = None
    budget: Optional[BudgetConfig] = None
    guardrails: Optional[str] = None 
    eval: Optional[EvalConfig] = None

class AgentManifest(AgentSpec):
    apiVersion: Literal["vesper/v1"]
    kind: Literal["Agent"] 

class AgentFleetManifest(StrictBaseModel):
    apiVersion: Literal["vesper/v1"]
    kind: Literal["AgentFleet"]  
    name: str
    agents: List[AgentSpec]    
    taskGraph: Dict[str, TaskConfig]
    budget: Optional[BudgetConfig] = None

VesperManifest = Annotated[
    Union[AgentManifest, AgentFleetManifest], 
    Field(discriminator="kind")
]
manifest_adapter = TypeAdapter(VesperManifest)