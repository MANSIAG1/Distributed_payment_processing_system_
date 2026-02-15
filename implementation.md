# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **Fault-Tolerant Distributed Payment Processing System** prototype for an e-commerce platform. The system implements:
- **Raft consensus algorithm** for distributed coordination
- **Multi-node replication** with vector clock synchronization
- **gRPC-based communication** between nodes and clients
- **Failure detection and recovery** mechanisms

## Development Commands

### Starting the System

**Start a single node (development)**:
```powershell
$env:NODE_ENV = ".env.node1"; python server/grpc_server.py
```

**Start multiple nodes for cluster testing**:
```powershell
# Terminal 1 (Node 1)
$env:NODE_ENV = ".env.node1"; python server/grpc_server.py

# Terminal 2 (Node 2) 
$env:NODE_ENV = ".env.node2"; python server/grpc_server.py

# Terminal 3 (Node 3)
$env:NODE_ENV = ".env.node3"; python server/grpc_server.py
```

**Run client**:
```powershell
python client/client.py
```

**Start FastAPI Web Frontend**:
```powershell
./start_frontend.ps1
```

Or manually:
```powershell
python frontend/main.py
```

### Testing

**Run all tests**:
```powershell
python -m pytest test/
```

**Run specific test categories**:
```powershell
python -m pytest test/test_consensus.py    # Raft consensus tests
python -m pytest test/test_replication.py  # Data replication tests
python -m pytest test/test_fault_tolerance.py  # Failure handling tests
python -m pytest test/test_time_sync.py    # Time synchronization tests
```

### Protocol Buffer Compilation

**Regenerate gRPC stubs** (when .proto files change):
```powershell
python -m grpc_tools.protoc --proto_path=proto --python_out=proto --grpc_python_out=proto proto/payment.proto proto/consensus.proto proto/replication.proto
```

### Environment Setup

**Install dependencies**:
```powershell
pip install -r requirements.txt
```

## Architecture Overview

### Multi-Layer Distributed System

The system follows a **layered architecture** with clear separation of concerns:

**Node Layer** (`server/node/`):
- `node_server.py`: Main PaymentService handling client requests
- `heartbeat.py`: TCP-based peer health monitoring 
- `failover.py`: Client request routing and node selection

**Consensus Layer** (`server/consensus/`):
- `raft.py`: Complete Raft implementation with leader election, log replication, and vector clock integration
- `leader_election.py`: Election management utilities
- `state_machine.py`: State transitions and persistence

**Replication Layer** (`server/replication/`):
- `replicator.py`: Transaction propagation between nodes
- `sync_manager.py`: Data synchronization during recovery/startup
- `deduplication.py`: Prevention of duplicate transactions

**Time Synchronization** (`server/time_sync/`):
- `vector_clock.py`: Vector clocks for causally-consistent ordering
- `lamport_clock.py`: Lamport timestamps for event ordering
- `ntp_sync.py`: NTP-based wall-clock synchronization

**Web Frontend** (`frontend/`):
- `main.py`: FastAPI application with REST endpoints and gRPC client integration
- `templates/`: Jinja2 HTML templates with Bootstrap styling
- `static/`: CSS, JavaScript, and other static assets
- Automatic failover between backend nodes with round-robin load balancing

### Key Architectural Patterns

**Consensus Integration**: The system tightly integrates Raft consensus with vector clocks. When nodes propose entries, they include vector timestamps that get propagated through the consensus protocol, ensuring both ordering and causality.

**Failure Handling**: Multi-layered approach using TCP heartbeats for quick failure detection, Raft timeouts for consensus failures, and client-side failover for request routing.

**Configuration-Driven Deployment**: Each node loads environment-specific settings from `.env.nodeX` files, making cluster setup straightforward.

## Important Implementation Notes

### Vector Clock Integration
The Raft implementation includes vector clocks in both `AppendEntries` requests and responses, creating a hybrid ordering system that preserves both consensus ordering and causal relationships.

### Ledger Persistence
Each node maintains a local JSON ledger file (`ledger_nodeX.json`) that persists committed transactions. The ledger format includes vector timestamps for each entry.

### gRPC Service Architecture
Three main services are exposed:
- `PaymentService`: Client-facing payment processing
- `ConsensusService`: Inter-node Raft communication  
- `ReplicationService`: Cross-node data synchronization

### Configuration Management
The `config/config.py` module provides centralized configuration with environment variable overrides. Key settings include node identity, peer discovery, timeouts, and persistence locations.

## Development Environment

**Python Version**: Requires Python 3.7+
**Key Dependencies**: grpcio, protobuf, raftos, SQLAlchemy, pytest, fastapi, uvicorn
**Database**: Supports both SQLite (development) and PostgreSQL (production)
**Logging**: Uses loguru for structured logging with per-node log files
**Web Interface**: FastAPI with Jinja2 templates, available at http://localhost:8000

The system is designed to run on localhost with different ports for multi-node testing, but can be configured for distributed deployment via environment variables.
