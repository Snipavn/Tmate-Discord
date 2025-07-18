import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess
import time
import os
import json
from dotenv import load_dotenv
from datetime import datetime

# Chỉ dùng .env để lấy TOKEN
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Cấu hình giới hạn
CHANNEL_ID = 1378918272812060742  # Thay bằng channel ID của bạn
OWNER_ID = 882844895902040104    # Thay bằng owner ID của bạn

# Khởi tạo bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Tạo file database nếu chưa có
if not os.path.exists("database.txt"):
    with open("database.txt", "w") as f:
        f.write(json.dumps({"sessions": {}, "credits": {}, "cooldown": {}}))

def load_db():
    with open("database.txt", "r") as f:
        return json.load(f)

def save_db(data):
    with open("database.txt", "w") as f:
        json.dump(data, f, indent=4)

# Auto xóa VPS hết hạn mỗi 60 giây
@tasks.loop(seconds=60)
async def auto_remove_vps():
    db = load_db()
    now = int(time.time())
    to_delete = [uid for uid, v in db["sessions"].items() if v["time"] < now]
    for uid in to_delete:
        user = await bot.fetch_user(int(uid))
        try:
            await user.send("⚠️ VPS của bạn đã hết hạn và đã bị xóa.")
        except:
            pass
        del db["sessions"][uid]
    save_db(db)

# Status bot: Đang xem {count} vps
@bot.event
async def on_ready():
    await tree.sync()
    auto_remove_vps.start()
    db = load_db()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(db['sessions'])} VPS đang chạy"
    ))
    print(f"Bot đã sẵn sàng: {bot.user}")

def is_owner(interaction: discord.Interaction):
    return interaction.user.id == OWNER_ID

def check_channel(interaction: discord.Interaction):
    return interaction.channel.id == CHANNEL_ID

# /deploy
@tree.command(name="deploy", description="Tạo VPS dùng tmate")
async def deploy(interaction: discord.Interaction):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong kênh quy định.", ephemeral=True)
        return

    db = load_db()
    uid = str(interaction.user.id)

    if uid in db["sessions"]:
        await interaction.response.send_message("❌ Bạn đã có VPS đang hoạt động.", ephemeral=True)
        return

    if db["credits"].get(uid, 0) < 10:
        await interaction.response.send_message("❌ Bạn cần 10 credit để tạo VPS.", ephemeral=True)
        return

    db["credits"][uid] -= 10
    save_db(db)

    await interaction.response.send_message("⏳ Đang tạo VPS... Vui lòng đợi...", ephemeral=True)

    subprocess.run(["tmate", "-S", "/tmp/tmate.sock", "new-session", "-d"])
    subprocess.run(["tmate", "-S", "/tmp/tmate.sock", "wait", "tmate-ready"])

    ssh = None
    for _ in range(10):
        try:
            ssh_raw = subprocess.check_output(["tmate", "-S", "/tmp/tmate.sock", "display", "-p", "'#{tmate_ssh}'"])
            ssh = ssh_raw.decode().strip().replace("'", "")
            if ssh.startswith("ssh"):
                break
        except:
            time.sleep(1.5)

    if not ssh:
        await interaction.followup.send("❌ Không thể tạo VPS. Vui lòng thử lại sau.", ephemeral=True)
        return

    db = load_db()
    db["sessions"][uid] = {"ssh": ssh, "time": int(time.time()) + 86400}
    save_db(db)

    try:
        await interaction.user.send(f"✅ VPS của bạn đã được tạo:\n`{ssh}`\nSẽ hết hạn sau 24 giờ.")
        await interaction.followup.send("✅ VPS đã gửi qua tin nhắn riêng.", ephemeral=True)
    except:
        await interaction.followup.send(f"✅ VPS của bạn: `{ssh}`", ephemeral=True)

# /timevps
@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    session = db["sessions"].get(uid)
    if not session:
        await interaction.response.send_message("❌ Bạn chưa có VPS nào đang hoạt động.", ephemeral=True)
        return

    remaining = session["time"] - int(time.time())
    if remaining < 0:
        await interaction.response.send_message("❌ VPS của bạn đã hết hạn.", ephemeral=True)
        return

    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    await interaction.response.send_message(f"⏳ VPS còn lại: `{hours} giờ {minutes} phút`", ephemeral=True)

# /getcredit
@tree.command(name="getcredit", description="Nhận 1 credit mỗi 12 giờ")
async def getcredit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    now = int(time.time())

    if uid in db["cooldown"] and now - db["cooldown"][uid] < 43200:
        remaining = 43200 - (now - db["cooldown"][uid])
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        await interaction.response.send_message(f"❌ Bạn cần chờ {hrs} giờ {mins} phút nữa.", ephemeral=True)
        return

    db["credits"][uid] = db["credits"].get(uid, 0) + 1
    db["cooldown"][uid] = now
    save_db(db)

    await interaction.response.send_message("✅ Bạn đã nhận được 1 credit.", ephemeral=True)

# /credit
@tree.command(name="credit", description="Xem số credit bạn đang có")
async def credit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    await interaction.response.send_message(f"💰 Bạn có `{db['credits'].get(uid, 0)}` credit.", ephemeral=True)

# /renew
@tree.command(name="renew", description="Gia hạn VPS thêm 1 ngày (10 credit)")
async def renew(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)

    if uid not in db["sessions"]:
        await interaction.response.send_message("❌ Bạn chưa có VPS để gia hạn.", ephemeral=True)
        return

    if db["credits"].get(uid, 0) < 10:
        await interaction.response.send_message("❌ Bạn cần 10 credit để gia hạn VPS.", ephemeral=True)
        return

    db["sessions"][uid]["time"] += 86400
    db["credits"][uid] -= 10
    save_db(db)

    await interaction.response.send_message("✅ VPS của bạn đã được gia hạn thêm 1 ngày.", ephemeral=True)

# /givecredit (admin)
@tree.command(name="givecredit", description="Tặng credit cho người dùng (owner)")
@app_commands.describe(user="Người nhận", amount="Số lượng credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Lệnh này chỉ dành cho owner.", ephemeral=True)
        return
    db = load_db()
    uid = str(user.id)
    db["credits"][uid] = db["credits"].get(uid, 0) + amount
    save_db(db)
    await interaction.response.send_message(f"✅ Đã tặng `{amount}` credit cho {user.name}.", ephemeral=True)

# /xoacredit (admin)
@tree.command(name="xoacredit", description="Xóa credit của người dùng (owner)")
@app_commands.describe(user="Người bị xóa")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Lệnh này chỉ dành cho owner.", ephemeral=True)
        return
    db = load_db()
    uid = str(user.id)
    db["credits"][uid] = 0
    save_db(db)
    await interaction.response.send_message(f"✅ Đã xóa toàn bộ credit của {user.name}.", ephemeral=True)

bot.run(TOKEN)
