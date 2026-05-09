"""
Benchmark API router for dagent.

Provides endpoints for the benchmark controller to trigger agent execution.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


from dagent.benchmark.runner import run_benchmark_agent
from dagent.benchmark.generator import generate_benchmark_config
from dagent.benchmark.config import AgentMode, AgentStructure

logger = logging.getLogger(__name__)

benchmark_router = APIRouter(prefix="/benchmark", tags=["benchmark"])


class SolveTaskRequest(BaseModel):
    """Request to solve a benchmark task."""
    # Complete task definition (new - contains everything)
    task_definition: Optional[Dict[str, Any]] = None
    
    # Individual fields (backwards compatibility)
    task_id: str
    description: str
    nodes: List[str]
    properties: List[Dict[str, Any]]
    mcp_url: str
    turn_limit: int = 50
    time_limit: float = 600.0
    
    # Agent configuration
    agent_mode: str = "single"        # "single" or "multi"
    provider: str = "openai"          # "openai", "ollama", "anthropic", "gemini"
    model: Optional[str] = None       # e.g., "gpt-4o", "qwen2.5:7b"
    structure: str = "sequential"     # "sequential"
    context_length: Optional[int] = None
    
    # Provider-specific
    api_key: Optional[str] = None
    host: Optional[str] = None


class GenerateTaskRequest(BaseModel):
    """Request to generate configuration (one-shot)."""
    task_id: str
    description: str
    nodes: List[str]
    links: List[Dict[str, Any]] = []  # Topology links with endpoints
    properties: List[Dict[str, Any]]
    platform: str = "frr"  # Network platform for command syntax
    
    # Agent configuration
    agent_mode: str = "single"        # "single" or "multi"
    structure: str = "sequential"     # "sequential", "concurrent", "debate", "group_chat"
    
    # Provider configuration
    provider: str = "openai"
    model: Optional[str] = None
    api_key: Optional[str] = None
    host: Optional[str] = None


class SolveTaskResponse(BaseModel):
    """Response from solving a benchmark task."""
    success: bool
    task_id: str
    turns_used: int
    commands_executed: int
    model_version: str
    error: Optional[str] = None
    actions: List[Dict[str, Any]] = []
    reasoning_trace: List[Dict[str, Any]] = []
    # New tracking fields
    token_usage: Optional[Dict[str, int]] = None
    tool_usage: Optional[Dict[str, int]] = None
    agent_conversations: Optional[List[Dict[str, Any]]] = None


@benchmark_router.post("/solve", response_model=SolveTaskResponse)
async def solve_task(request: SolveTaskRequest) -> SolveTaskResponse:
    """
    Solve a benchmark task.
    """
    logger.info(f"Received solve request for task: {request.task_id}")
    logger.info(f"Config: mode={request.agent_mode}, provider={request.provider}")
    
    try:
        # Prepare agent config
        agent_config = {
            "mode": request.agent_mode,
            "provider": request.provider,
            "structure": request.structure,
            "api_key": request.api_key,
            "host": request.host,
            "context_length": request.context_length,
        }
        if request.model:
            agent_config["model"] = request.model
            
        # Run the benchmark agent
        # Use complete task_definition if provided, otherwise use individual fields
        if request.task_definition:
            task_dict = {
                **request.task_definition,  # Complete task
                # Override with any runtime-specific values
                "turn_limit": request.turn_limit,
                "time_limit": request.time_limit,
            }
        else:
            # Backwards compatibility: construct from individual fields
            task_dict = {
                "task_id": request.task_id,
                "description": request.description,
                "nodes": request.nodes,
                "properties": request.properties,
                "turn_limit": request.turn_limit,
                "time_limit": request.time_limit,
            }
            
        result = await run_benchmark_agent(
            mcp_url=request.mcp_url,
            task_dict=task_dict,
            agent_config=agent_config,
        )
        
        logger.info(f"Agent completed: success={result['success']}, turns={result['turns_used']}")
        
        actions = result.get("actions_executed", [])
        
        return SolveTaskResponse(
            success=result["success"],
            task_id=request.task_id,
            turns_used=result["turns_used"],
            commands_executed=len(actions),
            model_version=f"{request.provider}:{request.model or 'default'}",
            error=result.get("error"),
            actions=actions,
            reasoning_trace=result.get("reasoning_trace", []),
            # New tracking fields
            token_usage=result.get("token_usage"),
            tool_usage=result.get("tool_usage"),
            agent_conversations=result.get("agent_conversations"),
        )
        
    except Exception as e:
        logger.error(f"Error solving task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@benchmark_router.post("/generate", response_model=SolveTaskResponse)
async def generate_task(request: GenerateTaskRequest) -> SolveTaskResponse:
    """
    Generate configurations for a benchmark task (one-shot).
    """
    logger.info(f"Received generate request for task: {request.task_id}")
    
    try:
        # Prepare agent config
        agent_config = {
            "provider": request.provider,
            "api_key": request.api_key,
            "host": request.host,
            "mode": request.agent_mode,
            "structure": request.structure,
        }
        if request.model:
            agent_config["model"] = request.model
            
        # Run generator
        result = await generate_benchmark_config(
            task_dict={
                "task_id": request.task_id,
                "description": request.description,
                "nodes": request.nodes,
                "links": request.links,
                "platform": request.platform,
                "properties": request.properties,
            },
            agent_config=agent_config,
        )
        
        return SolveTaskResponse(
            success=result["success"],
            task_id=request.task_id,
            turns_used=1,
            commands_executed=len(result.get("actions", [])),
            model_version=result.get("model_version", "unknown"),
            error=result.get("error"),
            actions=result.get("actions", []),
        )
        
    except Exception as e:
        logger.error(f"Error generating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@benchmark_router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "netagentbench-agent-harness"}
