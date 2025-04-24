import time
import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from test import main
import json
from typing import Optional
import  uuid
app = FastAPI()
import os

from groq import Groq

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    content: str
    githubAccount: str
    repository: str
    llmModel: str
    firstTime: bool
import asyncio
import httpx


async def handle_outbound_logic():
    # Step 1: Call
    async with httpx.AsyncClient() as client:
        response = await client.post("https://0609-36-255-84-98.ngrok-free.app/outbound-call", json={"number": "+919343282801"})
        call_sid = response.json()["callSid"]

    print(f"Waiting for transcript of call {call_sid}...")

    # Step 2: Setup event
    call_transcript_events[call_sid] = asyncio.Event()

    # Step 3: Check if transcript already came
    if call_sid in call_transcripts:
        print("Transcript already received early.")
        call_transcript_events[call_sid].set()

    # Step 4: Wait for event to be set
    await call_transcript_events[call_sid].wait()

    transcript = call_transcripts.get(call_sid)
    print(f"✅ Received transcript for {call_sid}: {transcript}")

    # Clean up
    del call_transcript_events[call_sid]
    del call_transcripts[call_sid]

    return transcript


active_connections: list[WebSocket] = []
permission_response_event = asyncio.Event()
permission_response_value = None
async def broadcast_status(message: Optional[str]=None, type: Optional[str]="status", title: Optional[str]= None, progress:  Optional[str]= "todo",id: Optional[uuid]= uuid.uuid4() ) -> None:
    global permission_response_event, permission_response_value
    if type == "task":
        for connection in active_connections:
            await connection.send_text(json.dumps({"type": "task", "message": {
                "id": str(id),
                "title": title,
                "content": message,
                "progress": progress # todo, inprogress, completed

            }}))
        return id
    elif type == "permission":
        # Clear any previous event
        permission_response_event.clear()
        permission_response_value = None

        for connection in active_connections:
            await connection.send_text(json.dumps({
                "type": "permission",
                "message": {
                    "reason": title,  # reason
                    "action": message  # action required
                }
            }))

        # Wait for response from frontend
        await permission_response_event.wait()
        return permission_response_value

    else:
        for connection in active_connections:
            await connection.send_text(json.dumps({"type": "status", "message": message}))

call_transcript_events = {}
call_transcripts = {}


@app.websocket("/ws/transcript")
async def receive_transcript(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            print("Raw WebSocket data:", data)

            data = json.loads(data)
            sid = data.get("sid")
            transcript = data.get("transcript")

            if sid:
                call_transcripts[sid] = transcript

                if sid in call_transcript_events:
                    print(f"SID matched: {sid}. Setting event.")
                    call_transcript_events[sid].set()
                else:
                    print(f"SID {sid} not in call_transcript_events yet. Stored transcript for later.")

    except WebSocketDisconnect:
        print("Transcript WebSocket disconnected")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global permission_response_value, permission_response_event
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            json_data = json.loads(data)

            if json_data.get("type") == "permission_response":
                permission_response_value = json_data.get("response")
                permission_response_event.set()

    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def wait():
    await asyncio.sleep(1)

@app.post("/api/query")
async def handle_query(query: Query):
    try:
        # Send initial status
        response = await main(query.content,broadcast_status,handle_outbound_logic)


        await broadcast_status(message="Done")
    except Exception as e:
        await broadcast_status(message=f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=7000)