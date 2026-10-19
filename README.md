# DSA4213 Agent Benchmark

A LangGraph-based multi-agent system for analyzing evidence packets, revising financial reports, verifying claims, and producing trading decisions.

## Requirements

- Python 3.10 or newer
- An OpenRouter API key

## Installation

From the project root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Set up

From the project root, create .env file following the .env.template
Insert API key in .env file

## Running the Agents
From the project root:

```powershell
py src/graph.py
```
