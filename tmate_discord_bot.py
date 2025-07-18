import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import json
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# --- Cấu hình ---
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104  # Thay bằng Discord ID của bạn
CHANNEL_ID = 1378918272812060742  # Kênh cố định dùng lệnh

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Database ---
def load_db():
    with open("database.txt", "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open("database.txt", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

if not os.path.exists("database.txt"):
    with open("database.txt", "w") as f:
        json.dump({"sessions": {}, "credits": {}, "last_claim": {}}, f)

# --- Tạo session mới ---
async def create_tmate_session():
    process = await asyncio.create_subprocess_shell(
        "tmate -S /tmp/tmate.sock new-session -d && tmate -S /tmp/tmate.sock wait tmate-ready && tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}'",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    return stdout.decode().strip()

# --- Update status bot ---
@tasks.loop(seconds=60)
async def update_status():
    db = load_db()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"Đang xem {len(db['sessions'])} VPS TMATE"
    ))

# --- Xoá VPS hết hạn ---
@tasks.loop(seconds=60)
async def cleanup_expired():
    db = load_db()
    now = int(time.time())
    expired = [uid for uid, s in db["sessions"].items() if s["time"] < now]
    for uid in expired:
        del db["sessions"][uid]
    if expired:
        save_db(db)

# --- Slash Commands ---
@tree.command(name="deploy", description="Tạo vps debian free 🤓👆 (10 credit)")
async def deploy(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = interaction.user
    db = load_db()

    uid = str(user.id)
    db["credits"].setdefault(uid, 0)

    if db["credits"][uid] < 10:
        await interaction.followup.send("Mày cần ít nhất 10 credit để tạo VPS.")
        return

    ssh = await create_tmate_session()
    expire = int(time.time()) + 86400

    db["credits"][uid] -= 10
    db["sessions"][uid] = {"ssh": ssh, "time": expire}
    save_db(db)

    embed = discord.Embed(title="✅ VPS của mày đã chạy!", color=0x00ff00)
    embed.add_field(name="SSH:", value=f"```{ssh}```", inline=False)
    embed.add_field(name="Thời gian hết hạn:", value=f"<t:{expire}:R>", inline=False)
    await user.send(embed=embed)
    await interaction.followup.send("Đã gửi thông tin VPS vào tin nhắn riêng.")

@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid in db["sessions"]:
        expire = db["sessions"][uid]["time"]
        remain = expire - int(time.time())
        if remain > 0:
            await interaction.response.send_message(
                f"⏳ VPS của m sẽ hết <t:{expire}:R>", ephemeral=False
            )
        else:
            await interaction.response.send_message("⛔ VPS của m đã hết hạn xin tao để được coin.", ephemeral=True)
    else:
        await interaction.response.send_message("M chưa có vps hả!! thg kia 😡😡.", ephemeral=True)

@tree.command(name="getcredit", description="Nhận 1 credit/12 giờ")
async def getcredit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    now = int(time.time())
    last = db["last_claim"].get(uid, 0)
    if now - last < 43200:
        wait = 43200 - (now - last)
        await interaction.response.send_message(f"⏳ Bạn cần đợi thêm <t:{now+wait}:R> để nhận tiếp.", ephemeral=True)
        return

    db["credits"].setdefault(uid, 0)
    db["credits"][uid] += 1
    db["last_claim"][uid] = now
    save_db(db)
    await interaction.response.send_message("✅ Bạn đã nhận được 1 credit.", ephemeral=False)

@tree.command(name="balance", description="Xem credit của m")
async def credit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    credit = db["credits"].get(uid, 0)
    await interaction.response.send_message(f"💰 M có **{credit} credit**.", ephemeral=False)

@tree.command(name="renew", description="Gia hạn VPS (10 credit)")
async def renew(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db["sessions"]:
        await interaction.response.send_message("Thg kia m chx có vps mà đòi renew thg khùng 😡.", ephemeral=True)
        return

    if db["credits"].get(uid, 0) < 10:
        await interaction.response.send_message("❌ M cần 10 credit để renew.", ephemeral=True)
        return

    db["sessions"][uid]["time"] += 86400
    db["credits"][uid] -= 10
    save_db(db)
    await interaction.response.send_message("✅ VPS của m đã được renew thêm 1 ngày.", ephemeral=False)

@tree.command(name="givecredit", description="Chỉ có tao mới dùng được lệnh này")
@app_commands.describe(user="User", amount="Số credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Lệnh này chỉ dành cho owner.", ephemeral=True)
        return
    db = load_db()
    uid = str(user.id)
    db["credits"].setdefault(uid, 0)
    db["credits"][uid] += amount
    save_db(db)
    await interaction.response.send_message(f"✅ Đã cộng {amount} credit cho {user.mention}", ephemeral=False)

@tree.command(name="xoacredit", description="(Admin) Xoá credit chúng nó")
@app_commands.describe(user="Những thg sẽ bị xoá credit")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Lệnh này chỉ dành cho owner.", ephemeral=True)
        return
    db = load_db()
    uid = str(user.id)
    if uid in db["credits"]:
        del db["credits"][uid]
    save_db(db)
    await interaction.response.send_message(f"✅ Đã xoá credit của {user.mention}", ephemeral=True)

@tree.command(name="cointop", description="Xem bảng xếp hạng credit")
async def cointop(interaction: discord.Interaction):
    db = load_db()
    credit_data = db["credits"]
    top = sorted(credit_data.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = ""
    for i, (uid, amount) in enumerate(top, 1):
        user = await bot.fetch_user(int(uid))
        msg += f"**{i}.** {user.mention} — `{amount} credit`\n"
    embed = discord.Embed(title="🏆 Bảng xếp hạng credit", description=msg or "Chưa có ai!", color=0xffd700)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Khởi động bot ---
@bot.event
async def on_ready():
    await tree.sync()
    update_status.start()
    cleanup_expired.start()
    print(f"🤖 Bot đã đăng nhập: {bot.user}")

bot.run(TOKEN)
