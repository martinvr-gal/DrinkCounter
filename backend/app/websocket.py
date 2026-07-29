from fastapi import WebSocket
class ConnectionManager:
    def __init__(self): self.connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket): await ws.accept(); self.connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.connections: self.connections.remove(ws)
    async def broadcast(self, event: dict):
        for connection in self.connections.copy():
            try: await connection.send_json(event)
            except Exception: self.disconnect(connection)
manager = ConnectionManager()
