import grpc
import sys
from common import utils
from proto import payment_pb2
from proto import payment_pb2_grpc


def run():
    """
    Client to send payment requests to the distributed payment server.
    """

    # Load server address from env/config
    server_address = utils.get_config("SERVER_ADDRESS", "localhost:50051")

    # Establish channel
    channel = grpc.insecure_channel(server_address)
    stub = payment_pb2_grpc.PaymentServiceStub(channel)

    print("--- Payment Client ---")
    print("Connected to server:", server_address)

    while True:
        try:
            # Ask user for payment input
            user_id = input("Enter User ID (or 'exit' to quit): ")
            if user_id.lower() == "exit":
                break

            amount = float(input("Enter Payment Amount: "))

            # Create request
            request = payment_pb2.PaymentRequest(
                user_id=user_id,
                amount=amount
            )

            # Send request to server
            response = stub.ProcessPayment(request)
            print(f"[SERVER RESPONSE] Status: {response.status}, Message: {response.message}")

        except grpc.RpcError as e:
            print(f"[ERROR] gRPC error: {e.code()} - {e.details()}")
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    run()
