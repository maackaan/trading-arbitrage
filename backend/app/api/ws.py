from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.container import AppContainer

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    container: AppContainer = websocket.app.state.container
    manager = container.realtime
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
