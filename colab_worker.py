# ==========================================
# 🚀 OTOGOAL COLAB HEAVY WORKER ENGINE v4.0
# ==========================================
import os
import sys
import time
import glob
import requests
import subprocess
import threading
import datetime
from google.colab import drive

# 🔗 Render API Adresiniz
RENDER_URL = "https://otogoalbot.onrender.com"

print("⏳ Sistem bağımlılıkları ve FFmpeg hazırlanıyor...")
os.system("pip install -q pyrogram tgcrypto requests")
os.system("apt-get update -qq && apt-get install -y ffmpeg -qq")

# Google Drive Bağlantısı
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')

DRIVE_FOLDER = "/content/drive/MyDrive/CanliMac"
LOCAL_BUFFER = "/content/local_buffer"
os.makedirs(DRIVE_FOLDER, exist_ok=True)
os.makedirs(LOCAL_BUFFER, exist_ok=True)

def push_log_to_render(msg):
    """Konsol çıktılarını anlık olarak Render sunucusuna gönderir"""
    now = datetime.datetime.now().strftime('%H:%M:%S')
    log_entry = f"[{now}] {msg}"
    print(log_entry)
    try:
        requests.post(f"{RENDER_URL}/api/push-logs", json={"logs": [log_entry]}, timeout=2)
    except:
        pass

class WorkerState:
    is_running = False
    process = None
    seen_updates = set()
    offset = 0
    last_home = 0
    last_away = 0
    last_goal_time = 0
    config = {}
    local_full_rec = ""

def safe_int(val, default=0):
    try:
        return int(val) if val else default
    except:
        return default

def extract_scorer(ev):
    try:
        incidents = []
        for key in ["In1", "In2", "Incidents", "SubEvents"]:
            if key in ev and isinstance(ev[key], list):
                incidents.extend(ev[key])
        scorers = []
        for inc in incidents:
            player = inc.get("Nm") or inc.get("Pn") or inc.get("Nm1")
            min_val = inc.get("Min") or inc.get("M")
            if player:
                scorers.append(f"{player} ({min_val}')" if min_val else player)
        if scorers:
            return scorers[-1]
    except:
        pass
    return "Bilgi Bekleniyor / Belli Değil"

def get_live_score(team_name):
    today = datetime.datetime.now().strftime('%Y%m%d')
    url = f"https://prod-public-api.livescore.com/v1/api/app/date/soccer/{today}/0.00"
    headers = {"User-Agent": "LiveScore/8.11.1 (Android 10; Mobile; en-US)"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for stage in data.get("Stages", []):
                for ev in stage.get("Events", []):
                    t1 = ev.get("T1", [{}])[0].get("Nm", "")
                    t2 = ev.get("T2", [{}])[0].get("Nm", "")
                    if team_name.lower() in t1.lower() or team_name.lower() in t2.lower():
                        home_s = safe_int(ev.get("Tr1", "0"))
                        away_s = safe_int(ev.get("Tr2", "0"))
                        minute = ev.get("Eps", "??")
                        match_str = f"{t1} {home_s} - {away_s} {t2}"
                        scorer_name = extract_scorer(ev)
                        return home_s, away_s, match_str, minute, scorer_name
        return 0, 0, f"Maç Bulunamadı ({team_name})", "??", "-"
    except:
        return None, None, "Bağlantı Bekleniyor...", "??", "-"

def clip_worker(caption_html, wait_seconds=105, seg_count=20):
    if wait_seconds > 0:
        push_log_to_render(f"⏳ Yayın gecikmesi bekleniyor ({wait_seconds} sn)...")
        time.sleep(wait_seconds)

    push_log_to_render("🎬 Yayın tampon hafızadan kesilip işleniyor...")
    segments = sorted(glob.glob(f"{LOCAL_BUFFER}/seg_*.ts"))
    target_segments = segments[-seg_count:] if len(segments) >= seg_count else segments

    if not target_segments:
        push_log_to_render("❌ Tampon hafızada yeterli yayın parçası birikmedi!")
        return

    temp_ts = f"/content/temp_{int(time.time())}.ts"
    output_mp4 = f"/content/GOL_KLIP_{int(time.time())}.mp4"
    thumb_jpg = f"/content/THUMB_{int(time.time())}.jpg"

    seg_list_str = " ".join(f"'{s}'" for s in target_segments)
    os.system(f"cat {seg_list_str} > {temp_ts}")

    cut_cmd = f"ffmpeg -hide_banner -loglevel error -y -i {temp_ts} -c copy -bsf:a aac_adtstoasc -movflags +faststart '{output_mp4}'"
    subprocess.run(cut_cmd, shell=True)

    if os.path.exists(temp_ts):
        os.remove(temp_ts)

    if os.path.exists(output_mp4):
        os.system(f"ffmpeg -hide_banner -loglevel error -y -ss 00:00:02 -i '{output_mp4}' -vframes 1 -q:v 2 '{thumb_jpg}'")
        push_log_to_render("🚀 Video Telegram kanalına yükleniyor (Pyrogram)...")

        uploader_script = f"/content/uploader_{int(time.time())}.py"
        with open(uploader_script, "w") as f:
            f.write(f"""
import sys, os
from pyrogram import Client, enums

app = Client(
    "otogoal_session",
    api_id={WorkerState.config.get('api_id')},
    api_hash="{WorkerState.config.get('api_hash')}",
    bot_token="{WorkerState.config.get('bot_token')}"
)

async def main():
    try:
        thumb_path = "{thumb_jpg}" if os.path.exists("{thumb_jpg}") else None
        async with app:
            await app.send_video(
                chat_id="{WorkerState.config.get('chat_id')}",
                video="{output_mp4}",
                caption={repr(caption_html)},
                parse_mode=enums.ParseMode.HTML,
                supports_streaming=True,
                duration=100, width=1920, height=1080, thumb=thumb_path
            )
        print("UPLOAD_SUCCESS")
    except Exception as e:
        print(f"UPLOAD_FAILED: {{e}}")

app.run(main())
""")

        result = subprocess.run(["python", uploader_script], capture_output=True, text=True)
        if "UPLOAD_SUCCESS" in result.stdout:
            push_log_to_render("✅ [TELEGRAM] Gol Klibi Orijinal Kalitede Başarıyla Gönderildi!")
        else:
            push_log_to_render(f"❌ [TELEGRAM HATASI]: {result.stdout}")

        for p in [uploader_script, output_mp4, thumb_jpg]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass

def start_stream_and_logic():
    push_log_to_render("🧹 Tampon hafıza temizleniyor...")
    os.system(f"rm -rf {LOCAL_BUFFER}/*")
    os.system("rm -f /content/*.ts /content/*.mp4 /content/*.jpg /content/uploader_*.py")

    takim = WorkerState.config.get('takim', 'Barcelona')
    iptv_url = WorkerState.config.get('iptv_url')
    delay = int(WorkerState.config.get('delay', 105))

    push_log_to_render(f"🔴 CANLI YAYIN KAYDI COLAB SUNUCUSUNDA BAŞLATILDI ({takim})")
    WorkerState.local_full_rec = f"/content/Tam_Mac_{takim}_{int(time.time())}.ts"

    cmd = [
        "ffmpeg", "-y",
        "-user_agent", "VLC/3.0.18 LibVLC/3.0.18",
        "-headers", "User-Agent: VLC/3.0.18 LibVLC/3.0.18\r\nAccept: */*\r\nRange: bytes=0-\r\n",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
        "-i", iptv_url,
        "-c", "copy", WorkerState.local_full_rec,
        "-c", "copy", "-f", "segment", "-segment_time", "5", "-reset_timestamps", "1",
        f"{LOCAL_BUFFER}/seg_%05d.ts"
    ]

    WorkerState.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    h_score, a_score, init_match, min_val, _ = get_live_score(takim)
    if h_score is not None:
        WorkerState.last_home, WorkerState.last_away = h_score, a_score
        push_log_to_render(f"✅ LiveScore Skor Takibi Aktif: {init_match}")

    while WorkerState.is_running:
        # A) Render'dan Anlık Komut Kontrolü (/goal, /stop)
        try:
            r_cmd = requests.get(f"{RENDER_URL}/api/get-cmds", timeout=2).json()
            for cmd_item in r_cmd.get("commands", []):
                if cmd_item == "GOAL":
                    push_log_to_render("📩 Manuel klip alma isteği işleniyor...")
                    test_cap = f"🛠 <b>MANUEL TEST KLİBİ</b>\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n📢 {WorkerState.config.get('chat_id')}"
                    threading.Thread(target=clip_worker, args=(test_cap, delay)).start()

                elif cmd_item == "STOP":
                    stop_stream_and_save()
                    return
        except:
            pass

        # B) LiveScore Otomatik Gol Kontrolü
        h_score, a_score, current_match, minute, scorer_name = get_live_score(takim)
        if h_score is not None and a_score is not None:
            # Render'a Anlık Skor Güncellemesi Gönder
            try:
                requests.post(f"{RENDER_URL}/api/update-match", json={"score": f"{h_score} - {a_score}", "minute": str(minute), "match": current_match}, timeout=2)
            except:
                pass

            if (h_score > WorkerState.last_home or a_score > WorkerState.last_away) and (time.time() - WorkerState.last_goal_time > 120):
                goal_caption = (
                    "🚨 <b>GOOOOOOOOLLL!</b> 🚨\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                    f"⚽ <b>Maç:</b> {current_match}\n⏱ <b>Dakika:</b> {minute}'\n👤 <b>Golü Atan:</b> {scorer_name}\n\n"
                    f"👉 {WorkerState.config.get('chat_id')}\n"
                )
                push_log_to_render(f"🔥 GOL TESPİT EDİLDİ! Skor: {h_score}-{a_score} | Golü Atan: {scorer_name}")
                threading.Thread(target=clip_worker, args=(goal_caption, delay)).start()

                WorkerState.last_home, WorkerState.last_away = h_score, a_score
                WorkerState.last_goal_time = time.time()

        time.sleep(4)

def stop_stream_and_save():
    WorkerState.is_running = False
    if WorkerState.process:
        try: WorkerState.process.terminate()
        except: pass
    push_log_to_render("⏹️ Yayın kaydı durduruldu.")
    push_log_to_render("📁 Tam maç kaydı Google Drive'a kopyalanıyor...")

    if os.path.exists(WorkerState.local_full_rec):
        drive_target = f"{DRIVE_FOLDER}/Tam_Mac_{WorkerState.config.get('takim')}_{int(time.time())}.ts"
        os.system(f"ffmpeg -hide_banner -loglevel error -y -i {WorkerState.local_full_rec} -c copy '{drive_target}'")
        push_log_to_render(f"✅ Tam maç kaydı Drive'a başarıyla kaydedildi: {drive_target}")

# MAIN POLLING LOOP
push_log_to_render("⚡ Colab Motoru Başlatıldı. Render.com üzerinden emir bekleniyor...")

while True:
    try:
        r = requests.get(f"{RENDER_URL}/api/get-config", timeout=3).json()
        if r.get("status") == "running" and not WorkerState.is_running:
            WorkerState.config = r.get("config", {})
            WorkerState.is_running = True
            threading.Thread(target=start_stream_and_logic, daemon=True).start()
    except:
        pass
    time.sleep(4)
