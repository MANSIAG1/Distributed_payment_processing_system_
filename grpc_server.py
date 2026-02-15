# server/grpc_server.py
import grpc
import time
from concurrent import futures

from config import config
from common import utils

# gRPC generated stubs
from proto import payment_pb2_grpc
from proto import consensus_pb2_grpc
from proto import replication_pb2_grpc

# Service implementations
from server.consensus.raft import RaftNode
from server.replication.sync_manager import ReplicationService
from server.node.node_server import PaymentService
from server.node.heartbeat import HeartbeatMonitor

def serve():
    """
    Starts the gRPC server and registers all services.
    """
    utils.log_event(f"Starting gRPC server for {config.NODE_ID} "
                    f"on {config.SERVER_HOST}:{config.SERVER_PORT}")

    # Thread pool for handling multiple RPC calls
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Initialize Raft node and Replication service
    raft_node = RaftNode()
    replicator = ReplicationService()
    heartbeat_monitor = HeartbeatMonitor()
    heartbeat_monitor.start()

    # Initialize PaymentService with references to Raft node and Replicator
    payment_service = PaymentService(raft_node=raft_node, replicator=replicator)

    # Register gRPC services
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(payment_service, server)
    consensus_pb2_grpc.add_ConsensusServiceServicer_to_server(raft_node, server)
    replication_pb2_grpc.add_ReplicationServiceServicer_to_server(replicator, server)

    # Bind host and port
    server.add_insecure_port(f"{config.SERVER_HOST}:{config.SERVER_PORT}")
    server.start()
    utils.log_event("gRPC server started successfully and waiting for requests.")

    try:
        while True:
            time.sleep(10)  # Keep process alive
    except KeyboardInterrupt:
        utils.log_event("Shutting down gRPC server...")
        server.stop(0)


if __name__ == "__main__":
    serve()
