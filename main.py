import time
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="OtoGoal Central API", version="4.0")

# CORS izinleri (Arayüz erişimi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sunucu Belleği (In-Memory Database)
class SystemStore:
    config: Dict[str, Any] = {}
    status: str = "idle"  # idle, running, stopping, error
    match_info: Dict[str, Any] = {"score": "0 - 0", "minute": "0'", "match": "Bekleniyor..."}
    commands: List[str] = []
    logs: List[Dict[str, str]] = []

store = SystemStore()

class ConfigModel(BaseModel):
    iptv_url: str
    takim: str
    delay: int = 105
    bot_token: str
    chat_id: str
    api_id: str
    api_hash: str

class CommandModel(BaseModel):
    command: str  # GOAL, STOP, PAUSE

class LogModel(BaseModel):
    logs: List[str]

class MatchUpdateModel(BaseModel):
    score: str
    minute: str
    match: str

@app.get("/")
def root():
    return {"status": "online", "system": "OtoGoal Core Active"}

@app.post("/api/set-config")
def set_config(data: ConfigModel):
    store.config = data.dict()
    store.status = "running"
    store.commands.append("START")
    return {"status": "success", "message": "Konfigürasyon alındı, Colab bekleniyor."}

@app.get("/api/get-config")
def get_config():
    return {"status": store.status, "config": store.config}

@app.post("/api/send-cmd")
def send_command(data: CommandModel):
    store.commands.append(data.command)
    if data.command == "STOP":
        store.status = "stopping"
    return {"status": "success", "command": data.command}

@app.get("/api/get-cmds")
def get_commands():
    cmds = list(store.commands)
    store.commands.clear()
    return {"commands": cmds}

@app.post("/api/push-logs")
def push_logs(data: LogModel):
    for line in data.logs:
        store.logs.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "message": line
        })
    if len(store.logs) > 300:
        store.logs = store.logs[-300:]
    return {"status": "ok"}

@app.get("/api/get-logs")
def get_logs():
    return {"logs": store.logs}

@app.post("/api/update-match")
def update_match(data: MatchUpdateModel):
    store.match_info = data.dict()
    return {"status": "ok"}

@app.get("/api/get-status")
def get_system_status():
    return {
        "status": store.status,
        "match_info": store.match_info,
        "config_loaded": bool(store.config)
    }
