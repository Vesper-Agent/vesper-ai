## Problem

Building AI agents is easy nowadays, but running them in production needs lot of manual scripts to manage persistent agent memory, quality and eval gates, security, finops and inter-agent communication in agent fleets.
There is no standalone infrastructure for managing AI agent fleets in production. In other words there is no Kubernetes for AI agents.

## Solution

Vesper - An infrastructure to manage AI agent fleets in production. Using Vesper a developer can define the agents and it's configurations in YAML file and use vesper's sdk and decorators to use those agents in there codebases.
Then it handles the agent lifecycle, persistent memory, eval gates, security as code, finops and multi-agent communication.
Vesper is built in these 7 layers:

- Agent Registry Engine
- Agent Lifecycle Engine
- Agent Memory Engine
- Agent Communication Bus
- FinOps Engine
- Quality and Eval Engine
- Security Engine

## Who is this for

Vesper is built for production teams or solo developers to manage and orchestrate their AI agents.

## What are we not building

- No Agentic framework integration such as langgraph
- No cloud agent management service
- No web UI

## Success metric

A developer should be able to define agents and it's configurations in a YAML file and use sdk and @agent and @tool decorator to link the agent's execution function and should be able to embed memory stored by vesper in the agent calls.
