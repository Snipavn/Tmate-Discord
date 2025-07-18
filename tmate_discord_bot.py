import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import asyncio
import random
import string
import subprocess
from dotenv import load_dotenv
# ===== CẤU HÌNH BỐ LÁO =====
load_dotenv()
TOKEN = os.getenv("TOKEN")  # đổi thành token của bạn
OWNER_ID = 882844895902040104     # ID của ông chủ
ALLOWED_CHANNEL_ID = 1378918272812060742  # Chỉ kênh này dùng được /deploy

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== DATABASE =====
DB_FILE = "tmate_db.json"

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"credits": {}, "sessions": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ===== TMATE =====
async def create_tmate_session():
    try:
        proc = await asyncio.create_subprocess_shell(
            "tmate -S /tmp/tmate.sock new-session -d && "
            "tmate -S /tmp/tmate.sock wait tmate-ready && "
            "tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
    except Exception as e:
        print("Tmate error:", e)
    return None

def generate_id(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# ===== /DEPLOY =====
@tree.command(name="deploy", description="🚀 Triệu hồi 1 con VPS bố đời (tốn 10 credit)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Cút về đúng channel đi thg rác 😤", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    db = load_db()
    uid = str(interaction.user.id)
    db["credits"].setdefault(uid, 0)

    if db["credits"][uid] < 10:
        await interaction.followup.send("💸 Không đủ 10 credit thì về xin ăn rồi quay lại 😹", ephemeral=True)
        return

    ssh = await create_tmate_session()
    if not ssh:
        await interaction.followup.send("❌ Tạo VPS lỗi, số m sao đen thế 😵", ephemeral=True)
        return

    expire = int(time.time()) + 86400
    vps_id = generate_id()
    db["credits"][uid] -= 10
    db["sessions"].setdefault(uid, []).append({"ssh": ssh, "time": expire, "id": vps_id})
    save_db(db)

    embed = discord.Embed(title="✅ Mày có con VPS mới 😎", color=0x00ff00)
    embed.add_field(name="SSH:", value=f"```{ssh}```", inline=False)
    embed.add_field(name="ID:", value=f"`{vps_id}`", inline=True)
    embed.add_field(name="Hết hạn:", value=f"<t:{expire}:R>", inline=True)
    await interaction.user.send(embed=embed)
    await interaction.followup.send("Gửi DM rồi đó thg gà, check lẹ đi 😏")

# ===== /TIMEVPS =====
@tree.command(name="timevps", description="⏰ Xem thời gian sống sót còn lại của lũ VPS của mày")
async def timevps(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db["sessions"] or not db["sessions"][uid]:
        await interaction.response.send_message("Mày có con VPS nào đâu mà đòi xem? Cút 😤", ephemeral=True)
        return

    text = ""
    for vps in db["sessions"][uid]:
        left = vps["time"] - int(time.time())
        if left < 0:
            text += f"`{vps['id']}`: 💀 Hết hạn rồi - xếp xó!\n"
        else:
            text += f"`{vps['id']}`: còn **{left//3600}h {left%3600//60}m** <t:{vps['time']}:R>\n"
    await interaction.response.send_message(f"🧠 Thời gian lũ VPS của mày:\n{text}")

# ===== /LISTVPS =====
@tree.command(name="listvps", description="📋 Liệt kê toàn bộ lũ VPS chó nhà mày")
async def listvps(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db["sessions"] or not db["sessions"][uid]:
        await interaction.response.send_message("Không có con VPS nào luôn á? Gà 😭", ephemeral=True)
        return

    embed = discord.Embed(title="📋 Danh sách VPS của mày", color=0xffcc00)
    for vps in db["sessions"][uid]:
        embed.add_field(name=f"ID: {vps['id']}", value=f"```{vps['ssh']}```\nHết hạn: <t:{vps['time']}:R>", inline=False)
    await interaction.response.send_message(embed=embed)

# ===== /RENEWVPS =====
@tree.command(name="renewvps", description="🔁 Kéo dài tuổi thọ cho con VPS ngu của mày (10 credit)")
@app_commands.describe(vps_id="ID của con VPS muốn kéo dài")
async def renewvps(interaction: discord.Interaction, vps_id: str):
    db = load_db()
    uid = str(interaction.user.id)

    if db["credits"].get(uid, 0) < 10:
        await interaction.response.send_message("M nghèo vkl, không đủ 10 credit đâu 😤", ephemeral=True)
        return

    if uid not in db["sessions"]:
        await interaction.response.send_message("Có VPS đâu mà đòi kéo dài? Tự ảo tưởng hả? 😡", ephemeral=True)
        return

    for vps in db["sessions"][uid]:
        if vps["id"] == vps_id:
            vps["time"] += 86400
            db["credits"][uid] -= 10
            save_db(db)
            await interaction.response.send_message(f"✅ VPS `{vps_id}` được kéo dài thêm 1 ngày 😎", ephemeral=False)
            return

    await interaction.response.send_message("❌ Không thấy con VPS nào có ID đó. Nhìn cho kĩ lại đi đồ gà 😒", ephemeral=True)

# ===== /STOPVPS =====
@tree.command(name="stopvps", description="🛑 Kết liễu 1 con VPS bất tài vô dụng")
@app_commands.describe(vps_id="ID con VPS cần cho ra chuồng gà")
async def stopvps(interaction: discord.Interaction, vps_id: str):
    db = load_db()
    uid = str(interaction.user.id)

    if uid not in db["sessions"]:
        await interaction.response.send_message("Không có VPS nào luôn á? M đang tấu hài hả? 😒", ephemeral=True)
        return

    before = len(db["sessions"][uid])
    db["sessions"][uid] = [vps for vps in db["sessions"][uid] if vps["id"] != vps_id]

    if len(db["sessions"][uid]) == before:
        await interaction.response.send_message("❌ Không tìm thấy VPS nào có ID đó, xạo l* à? 😡", ephemeral=True)
        return

    if not db["sessions"][uid]:
        del db["sessions"][uid]

    save_db(db)
    await interaction.response.send_message(f"🗑️ Đã xử đẹp con VPS `{vps_id}`. Khỏi cảm ơn 😎", ephemeral=False)

# ===== /CREDIT =====
@tree.command(name="credit", description="💸 Kiểm tra credit ngu của m")
async def credit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    credit = db["credits"].get(uid, 0)
    await interaction.response.send_message(f"🧾 Mày còn `{credit}` credit. Xài cho cẩn thận, nghèo thì đừng deploy bừa 😎")

# ===== /GETCREDIT =====
@tree.command(name="getcredit", description="🎁 Xin 1 credit như thg ăn mày (mỗi 12h)")
async def getcredit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    now = int(time.time())

    last = db.get("last_claim", {}).get(uid, 0)
    if now - last < 43200:
        left = 43200 - (now - last)
        await interaction.response.send_message(f"🚫 Đợi {left//3600}h {left%3600//60}m nữa rồi quay lại xin tiếp 😹", ephemeral=True)
        return

    db["credits"][uid] = db["credits"].get(uid, 0) + 1
    db.setdefault("last_claim", {})[uid] = now
    save_db(db)
    await interaction.response.send_message("🎉 Cho m 1 credit rồi đó. Xài khôn khéo vào nha thg lú 😈")

# ===== /GIVECREDIT =====
@tree.command(name="givecredit", description="💰 Ban phát credit như thần tài (admin only)")
@app_commands.describe(user="Người nhận", amount="Số credit cho")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Cút, lệnh này cho thg chủ bot thôi 😤", ephemeral=True)
        return

    db = load_db()
    db["credits"][str(user.id)] = db["credits"].get(str(user.id), 0) + amount
    save_db(db)
    await interaction.response.send_message(f"✅ Đã nhét `{amount}` credit vào mặt {user.mention}")

# ===== /XOACREDIT =====
@tree.command(name="xoacredit", description="🧨 Xoá sạch credit thg nào đó cho bõ tức (admin only)")
@app_commands.describe(user="Thằng cần reset credit")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Mơ đi, đây là sân chơi của chủ bot 😏", ephemeral=True)
        return

    db = load_db()
    db["credits"][str(user.id)] = 0
    save_db(db)
    await interaction.response.send_message(f"🧹 Đã cào sạch credit của {user.mention}")

# ===== AUTO REMOVE VPS HẾT HẠN =====
@tasks.loop(minutes=1)
async def remove_expired_vps():
    db = load_db()
    now = int(time.time())
    changed = False
    for uid in list(db["sessions"].keys()):
        new_list = [vps for vps in db["sessions"][uid] if vps["time"] > now]
        if len(new_list) != len(db["sessions"][uid]):
            db["sessions"][uid] = new_list
            if not new_list:
                del db["sessions"][uid]
            changed = True
    if changed:
        save_db(db)

@bot.event
async def on_ready():
    await tree.sync()
    remove_expired_vps.start()
    print(f"Bot đã sẵn sàng dưới ID: {bot.user.id}")

bot.run(TOKEN)
