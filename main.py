import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, 
    allow_methods=["*"], allow_headers=["*"]
)

# ==========================================
# 🗄️ MÜŞTERİ VERİTABANI (YÖNETİM PANELİN)
# ==========================================
# Yeni müşteri eklemek, banlamak veya plan değiştirmek için sadece burayı düzenleyeceksin.
USERS_DB = {
    "barafella": {"key": "barafella2026", "plan": "pro", "active": True},
    "musteri1": {"key": "123456", "plan": "normal", "active": True},
    "banli_adam": {"key": "9999", "plan": "pro", "active": False}
}

# ==========================================
# 🧠 SİSTEM HAFIZASI (Colab - Masaüstü Köprüsü)
# ==========================================
store = {
    "config": {},
    "status": "idle",
    "commands": [],
    "logs": []
}

class LoginModel(BaseModel):
    user: str
    key: str

@app.post("/api/login")
def login(data: LoginModel):
    user_info = USERS_DB.get(data.user)
    if user_info and user_info["key"] == data.key:
        if user_info["active"]:
            return {"success": True, "plan": user_info["plan"]}
        return {"success": False, "message": "Hesabınız yönetici tarafından askıya alınmıştır!"}
    return {"success": False, "message": "Kullanıcı adı veya lisans anahtarı hatalı!"}

@app.post("/api/set-config")
def set_config(data: dict):
    store["config"] = data
    store["status"] = "running"
    store["commands"].append("START")
    return {"status": "success"}

@app.get("/api/get-config")
def get_config():
    return {"status": store["status"], "config": store["config"]}

@app.post("/api/send-cmd")
def send_cmd(data: dict):
    cmd = data.get("command")
    if cmd:
        store["commands"].append(cmd)
        if cmd == "STOP":
            store["status"] = "idle"
    return {"status": "success"}

@app.get("/api/get-cmds")
def get_cmds():
    cmds = list(store["commands"])
    store["commands"].clear()
    return {"commands": cmds}

@app.post("/api/push-logs")
def push_logs(data: dict):
    new_logs = data.get("logs", [])
    store["logs"].extend(new_logs)
    if len(store["logs"]) > 300:
        store["logs"] = store["logs"][-300:]
    return {"status": "ok"}

@app.get("/api/get-logs")
def get_logs():
    return {"logs": store["logs"]}
