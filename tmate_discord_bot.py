import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import uuid
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Khai báo trực tiếp không cần .env
TOKEN = os.getenv("TOKEN")
OWNER_ID = 
ALLOWED_CHANNEL_ID = 

DB_FILE = "db.json"
CREDIT_PER_DEPLOY = 10

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def get_credit(user_id):
    db = load_db()
    return db.get(str(user_id), {}).get("credit", 0)

def add_credit(user_id, amount):
    db = load_db()
    user = db.setdefault(str(user_id), {})
    user["credit"] = user.get("credit", 0) + amount
    save_db(db)

def set_next_claim(user_id, next_time):
    db = load_db()
    user = db.setdefault(str(user_id), {})
    user["next_claim"] = next_time.timestamp()
    save_db(db)

def can_claim(user_id):
    db = load_db()
    now = datetime.utcnow().timestamp()
    next_time = db.get(str(user_id), {}).get("next_claim", 0)
    return now >= next_time

def get_sessions(user_id):
    db = load_db()
    return db.get(str(user_id), {}).get("sessions", [])

def save_session(user_id, session_id, ssh, expire_time):
    db = load_db()
    user = db.setdefault(str(user_id), {})
    sessions = user.setdefault("sessions", [])
    sessions.append({
        "id": session_id,
        "ssh": ssh,
        "expires_at": expire_time.timestamp()
    })
    save_db(db)

def remove_session(user_id, session_id):
    db = load_db()
    user = db.get(str(user_id), {})
    sessions = user.get("sessions", [])
    user["sessions"] = [s for s in sessions if s["id"] != session_id]
    save_db(db)

@tree.command(name="deploy", description="Tạo VPS chơi cho vui (10 coin/lần)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Thg kia, lệnh này chỉ xài trong kênh quy định. Cút!", ephemeral=True)

    user_id = interaction.user.id
    if get_credit(user_id) < CREDIT_PER_DEPLOY:
        return await interaction.response.send_message("Không đủ coin, nghèo mà bày đặt deploy?", ephemeral=True)

    await interaction.response.send_message("Đợi xíu tao dựng con VPS cho mày...")

    session_id = str(uuid.uuid4())[:8]
    socket_path = f"/tmp/tmate_{session_id}.sock"

    proc = await asyncio.create_subprocess_shell(
        f"tmate -S {socket_path} new-session -d && "
        f"tmate -S {socket_path} wait tmate-ready && "
        f"tmate -S {socket_path} display -p '#{{tmate_ssh}}'",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    ssh = stdout.decode().strip()

    if not ssh:
        return await interaction.followup.send("Tạo VPS lỗi, chắc tại mày xui.", ephemeral=True)

    expire_time = datetime.utcnow() + timedelta(days=1)
    save_session(user_id, session_id, ssh, expire_time)
    add_credit(user_id, -CREDIT_PER_DEPLOY)

    await interaction.user.send(
        f"✅ SSH nè thg gà: `{ssh}`\n"
        f"🆔 ID: `{session_id}`\n"
        f"🕒 Hết hạn: `{expire_time.strftime('%Y-%m-%d %H:%M:%S')} UTC`"
    )
    await interaction.followup.send("Gửi session rồi đó, check DM đi thg kia!", ephemeral=True)

@tree.command(name="credit", description="Xem coin của mày còn bao nhiêu")
async def credit(interaction: discord.Interaction):
    user_id = interaction.user.id
    await interaction.response.send_message(f"Mày còn {get_credit(user_id)} coin.")

@tree.command(name="getcredit", description="Nhận coin mỗi 12h, xin hoài =))")
async def getcredit(interaction: discord.Interaction):
    user_id = interaction.user.id
    if not can_claim(user_id):
        return await interaction.response.send_message("12 tiếng mới xin coin 1 lần. Đợi đi thằng háu ăn.", ephemeral=True)
    
    add_credit(user_id, 1)
    set_next_claim(user_id, datetime.utcnow() + timedelta(hours=12))
    await interaction.response.send_message("Rồi, cho mày 1 coin đấy. Liếm lẹ.")

@tree.command(name="givecredit", description="(Owner) Tặng coin cho đứa khác")
@app_commands.describe(user="Đứa nhận", amount="Số coin")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày éo có quyền. Cút!", ephemeral=True)
    add_credit(user.id, amount)
    await interaction.response.send_message(f"Đã tặng {amount} coin cho {user.mention}")

@tree.command(name="xoacredit", description="(Owner) Xoá sạch coin đứa nào đó")
@app_commands.describe(user="Đứa bị xoá")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày là ai mà đòi xoá?", ephemeral=True)
    db = load_db()
    db[str(user.id)]["credit"] = 0
    save_db(db)
    await interaction.response.send_message(f"Xoá sạch coin của {user.mention}")

@tree.command(name="timevps", description="Xem thời gian còn lại của các con VPS")
async def timevps(interaction: discord.Interaction):
    sessions = get_sessions(interaction.user.id)
    if not sessions:
        return await interaction.response.send_message("Mày có con VPS nào đâu mà đòi xem thời gian?", ephemeral=True)

    now = datetime.utcnow()
    text = ""
    for s in sessions:
        remaining = datetime.fromtimestamp(s["expires_at"]) - now
        text += f"🆔 `{s['id']}` | ⏳ Còn lại: `{str(remaining).split('.')[0]}`\n"
    await interaction.response.send_message(text)

@tree.command(name="renewvps", description="Gia hạn thêm 1 ngày cho VPS")
@app_commands.describe(id="ID của VPS")
async def renewvps(interaction: discord.Interaction, id: str):
    sessions = get_sessions(interaction.user.id)
    for s in sessions:
        if s["id"] == id:
            if get_credit(interaction.user.id) < 10:
                return await interaction.response.send_message("Không đủ coin để gia hạn. Khóc tiếp đi.", ephemeral=True)
            s["expires_at"] = (datetime.fromtimestamp(s["expires_at"]) + timedelta(days=1)).timestamp()
            add_credit(interaction.user.id, -10)
            save_db(load_db())
            return await interaction.response.send_message("Gia hạn xong. Lạy luôn vì xài hoài không hết 😮‍💨")
    await interaction.response.send_message("Không tìm thấy VPS nào với ID đó, đồ ngu.")

@tree.command(name="stopvps", description="Xoá VPS (không hoàn coin đâu nha)")
@app_commands.describe(id="ID VPS cần xoá")
async def stopvps(interaction: discord.Interaction, id: str):
    remove_session(interaction.user.id, id)
    await interaction.response.send_message("Đã xoá VPS. Khóc đi.")

@tree.command(name="listvps", description="Liệt kê toàn bộ con VPS đang xài")
async def listvps(interaction: discord.Interaction):
    sessions = get_sessions(interaction.user.id)
    if not sessions:
        return await interaction.response.send_message("Mày chưa có con VPS nào, lêu lêu.", ephemeral=True)

    now = datetime.utcnow()
    msg = ""
    for s in sessions:
        expire = datetime.fromtimestamp(s["expires_at"])
        remaining = str(expire - now).split(".")[0]
        msg += f"🆔 `{s['id']}` | 🧵 `{s['ssh']}`\n⏳ Còn lại: `{remaining}`\n\n"
    await interaction.response.send_message(msg)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Đã đăng nhập: {bot.user}")

bot.run(TOKEN)
