from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import grpc
from typing import Optional
from datetime import datetime

# Import gRPC generated code
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from proto import payment_pb2
from proto import payment_pb2_grpc

app = FastAPI(title="Distributed Payment System", description="Web interface for the distributed payment processing system")

# Mount static files and templates
current_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

class PaymentGRPCClient:
    """gRPC client wrapper for connecting to the SecureTransfer banking backend"""
    
    def __init__(self):
        self.server_addresses = [
            "localhost:50051",  # node1
            "localhost:50052",  # node2
            "localhost:50053"   # node3
        ]
        self.current_server_index = 0
    
    def get_next_server(self):
        """Round-robin server selection with failover"""
        server = self.server_addresses[self.current_server_index]
        self.current_server_index = (self.current_server_index + 1) % len(self.server_addresses)
        return server
    
    async def process_payment(self, user_id: str, amount: float):
        """Process payment with automatic failover"""
        last_exception = None
        
        # Try all servers
        for _ in range(len(self.server_addresses)):
            server_address = self.get_next_server()
            
            try:
                channel = grpc.insecure_channel(server_address)
                stub = payment_pb2_grpc.PaymentServiceStub(channel)
                
                request = payment_pb2.PaymentRequest(
                    user_id=user_id,
                    amount=amount
                )
                
                response = stub.ProcessPayment(request, timeout=10)
                channel.close()
                
                return {
                    "status": response.status,
                    "message": response.message,
                    "timestamp": response.timestamp,
                    "server": server_address
                }
                
            except Exception as e:
                last_exception = e
                if channel:
                    channel.close()
                continue
        
        # All servers failed
        raise HTTPException(
            status_code=503, 
            detail=f"All payment servers unavailable. Last error: {str(last_exception)}"
        )
    
    async def get_history(self, user_id: str):
        """Get transaction history with automatic failover and merging results from all nodes"""
        last_exception = None
        all_transactions = []
        servers_queried = []
        transaction_ids = set()  # To track unique transactions

        # Try all servers and merge results
        for _ in range(len(self.server_addresses)):
            server_address = self.get_next_server()
            servers_queried.append(server_address)
            
            try:
                channel = grpc.insecure_channel(server_address)
                stub = payment_pb2_grpc.PaymentServiceStub(channel)
                
                request = payment_pb2.HistoryRequest(user_id=user_id)
                response = stub.GetHistory(request, timeout=10)
                channel.close()
                
                for tx in response.transactions:
                    # Create a unique ID for the transaction (based on timestamp + user_id)
                    tx_unique_id = f"{tx.timestamp}:{tx.user_id}:{tx.amount}"
                    
                    # Only add if we haven't seen this transaction before
                    if tx_unique_id not in transaction_ids:
                        transaction_ids.add(tx_unique_id)
                        all_transactions.append({
                            "user_id": tx.user_id,
                            "amount": tx.amount,
                            "status": tx.status,
                            "timestamp": tx.timestamp,
                            "node_id": server_address.split(":")[-1]  # Extract port number
                        })
                
            except Exception as e:
                print(f"Error querying {server_address}: {e}")
                last_exception = e
                if channel:
                    channel.close()
                continue
        
        # Return merged results from all servers
        if all_transactions or not last_exception:
            return {
                "transactions": all_transactions,
                "server": ", ".join(servers_queried)
            }
        else:
            # All servers failed
            raise HTTPException(
                status_code=503,
                detail=f"All payment servers unavailable. Last error: {str(last_exception)}"
            )
        
        # All servers failed
        raise HTTPException(
            status_code=503, 
            detail=f"All payment servers unavailable. Last error: {str(last_exception)}"
        )

# Global gRPC client instance
payment_client = PaymentGRPCClient()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with payment form"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process-payment")
async def process_payment_endpoint(
    user_id: str = Form(...),
    amount: float = Form(...)
):
    """Process a payment transaction"""
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        result = await payment_client.process_payment(user_id, amount)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")

@app.get("/history/{user_id}")
async def get_transaction_history(user_id: str):
    """Get transaction history for a user"""
    try:
        result = await payment_client.get_history(user_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, user_id: Optional[str] = None):
    """History page"""
    transactions = []
    error_message = None
    
    if user_id:
        try:
            print(f"DEBUG: Requesting history for user_id={user_id}")
            result = await payment_client.get_history(user_id)
            print(f"DEBUG: Received {len(result['transactions'])} transactions")
            for tx in result["transactions"]:
                print(f"DEBUG: Transaction: user={tx['user_id']}, amount={tx['amount']}, status={tx['status']}")
            transactions = result["transactions"]
        except HTTPException as e:
            error_message = e.detail
            print(f"DEBUG: HTTPException: {error_message}")
        except Exception as e:
            error_message = f"Failed to fetch history: {str(e)}"
            print(f"DEBUG: Exception: {error_message}")
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "user_id": user_id,
        "transactions": transactions,
        "error_message": error_message
    })

@app.get("/api/servers")
async def server_status():
    """Check status of backend servers"""
    servers_status = []
    
    for address in payment_client.server_addresses:
        try:
            channel = grpc.insecure_channel(address)
            stub = payment_pb2_grpc.PaymentServiceStub(channel)
            
            # Try a simple health check by getting empty history
            request = payment_pb2.HistoryRequest(user_id="__health_check__")
            stub.GetHistory(request, timeout=2)
            
            servers_status.append({
                "address": address,
                "status": "healthy"
            })
            channel.close()
            
        except Exception:
            servers_status.append({
                "address": address,
                "status": "unhealthy"
            })
    
    return {"servers": servers_status}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
