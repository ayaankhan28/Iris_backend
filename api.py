import time
import asyncio

from fastapi import FastAPI, HTTPException, WebSocket
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

active_connections: list[WebSocket] = []

async def broadcast_status(message: Optional[str]=None, type: Optional[str]="status", title: Optional[str]= None, progress:  Optional[str]= "todo",id: Optional[uuid]= uuid.uuid4() ) -> None:
    if type == "task":
        for connection in active_connections:
            await connection.send_text(json.dumps({"type": "task", "message": {
                "id": str(id),
                "title": title,
                "content": message,
                "progress": progress # todo, inprogress, completed

            }}))
        return id
    else:
        for connection in active_connections:
            await connection.send_text(json.dumps({"type": "status", "message": message}))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        active_connections.remove(websocket)

async def wait():
    await asyncio.sleep(1)

@app.post("/api/query")
async def handle_query(query: Query):
    try:
        # Send initial status
        if query.firstTime:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """You are a agent who tells about the availability about the software engineer Alex in a fun way.
                        E.g phrase. 'Let me check if developer is not sleeping'
                        'let see if developer is having coffee or not',
                        'found your engineer he was playing fornite, let me just power off the playstation'
                        Like above generate very randome phrease about like above but do not give above keep very random but funny more.
                        keep phrase under 20 words and more importantly funny sarcastic 
                        you can add some popular developer coding memes
                        give repsonse according to what user asked for the developer
                        You are only task is to give a p=humourso phrase of finding the dev do not give other than like exceuted code or something
                        """
                    },
                    {
                        "role": "user",
                        "content":query.content,

                    }
                ],
                model="llama-3.1-8b-instant",
            )

            a = chat_completion.choices[0].message.content
            await broadcast_status(message=a)
        await wait()
        # response = await main(query.content,broadcast_status)
        await broadcast_status(message="Done")
    except Exception as e:
        await broadcast_status(message=f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)