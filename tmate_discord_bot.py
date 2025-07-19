import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import subprocess
import os
import random
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Config
OWNER_ID = 123456789012345678  # Thay bằng ID của bạn
ALLOWED_CHANNEL_ID = 123456789012345678  # Thay bằng ID kênh bot được phép hoạt động
CREDIT_FILE = "credits.json"
CONFIG_FILE = "user_configs.json"
VPS_DIR = "vps"

if not os.path.exists(CREDIT_FILE):
    with open(CREDIT_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(VPS_DIR):
    os.makedirs(VPS_DIR)

def load_credits():
    with open(CREDIT_FILE) as f:
        return json.load(f)

def save_credits(data):
    with open(CREDIT_FILE, "w") as f:
        json.dump(data, f)

def load_configs():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_configs(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def get_expiry_time():
    return (datetime.utcnow() + timedelta(days=1)).isoformat()

def get_session_path(user_id):
    return os.path.join(VPS_DIR, str(user_id))

def get_tmate_script(user_id):
    folder = get_session_path(user_id)
    return f"""
rm -rf {folder}
mkdir -p {folder}
cd {folder}
apt update -y && apt install -y wget curl proot tar
wget https://raw.githubusercontent.com/proot-me/proot-static-build/master/static/proot -O proot
chmod +x proot
wget https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.4-base-amd64.tar.gz
mkdir rootfs
./proot -S rootfs tar -xzf ubuntu-base-22.04.4-base-amd64.tar.gz
tmate -S {folder}/tmate.sock new-session -d
tmate -S {folder}/tmate.sock wait tmate-ready
tmate -S {folder}/tmate.sock display -p '#{{tmate_ssh}}'
"""

async def send_dm(user, msg):
    try:
        await user.send(msg)
    except:
        pass

@tree.command(name="getcredit", description="Nhận credit mỗi 12 giờ")
async def getcredit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit_data = load_credits()
    now = datetime.utcnow()

    last_time = credit_data.get(user_id, {}).get("last", "1970-01-01T00:00:00")
    last = datetime.fromisoformat(last_time)

    if now - last < timedelta(hours=12):
        await interaction.response.send_message("⏳ Mỗi 12 tiếng mới được xin credit. Đợi tiếp đi thằng ngu.")
        return

    credit_data.setdefault(user_id, {"credit": 0})
    credit_data[user_id]["credit"] += 1
    credit_data[user_id]["last"] = now.isoformat()
    save_credits(credit_data)

    await interaction.response.send_message("💰 Cho mày 1 credit nữa nè, tiêu cho khôn.")

@tree.command(name="credit", description="Xem credit hiện tại")
async def credit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit_data = load_credits()
    credit = credit_data.get(user_id, {}).get("credit", 0)
    await interaction.response.send_message(f"💸 Mày còn {credit} credit ngu.")

@tree.command(name="givecredit", description="Tăng credit (OWNER)")
async def givecredit(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Cút. Không đủ tuổi.", ephemeral=True)
        return
    user_id = str(member.id)
    credit_data = load_credits()
    credit_data.setdefault(user_id, {"credit": 0})
    credit_data[user_id]["credit"] += amount
    save_credits(credit_data)
    await interaction.response.send_message(f"Đã tăng {amount} credit cho thằng {member.display_name}.")

@tree.command(name="xoacredit", description="Xóa sạch credit (OWNER)")
async def xoacredit(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Mày là cái thá gì?", ephemeral=True)
        return
    user_id = str(member.id)
    credit_data = load_credits()
    if user_id in credit_data:
        del credit_data[user_id]
    save_credits(credit_data)
    await interaction.response.send_message(f"Xoá mẹ sạch credit của thằng {member.display_name} rồi.")

@tree.command(name="shopping", description="Mua cấu hình VPS")
async def shopping(interaction: discord.Interaction):
    configs = {
        "2GB RAM, 2 core": 20,
        "4GB RAM, 4 core": 40,
        "8GB RAM, 8 core": 80,
        "12GB RAM, 12 core": 120,
        "16GB RAM, 16 core": 160
    }
    msg = "**🛒 Cửa hàng VPS:**\n"
    for name, cost in configs.items():
        msg += f"- {name} = {cost} credit\n"
    await interaction.response.send_message(msg)

@tree.command(name="setcauhinh", description="Chọn cấu hình VPS để deploy")
async def setcauhinh(interaction: discord.Interaction, ram_cpu: str):
    configs = {
        "2": 20,
        "4": 40,
        "8": 80,
        "12": 120,
        "16": 160
    }
    if ram_cpu not in configs:
        await interaction.response.send_message("Cấu hình ngu. Chọn 2, 4, 8, 12, hoặc 16.", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    data = load_configs()
    data[user_id] = ram_cpu
    save_configs(data)
    await interaction.response.send_message(f"✅ Cấu hình VPS của mày đã được set thành {ram_cpu}GB RAM, {ram_cpu} core.")

@tree.command(name="deploy", description="Tạo VPS (tốn 10 credit/ngày)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Cút về channel quy định.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    credit_data = load_credits()
    config_data = load_configs()

    if user_id not in config_data:
        await interaction.response.send_message("Chưa set cấu hình. Dùng /setcauhinh trước.", ephemeral=True)
        return

    if credit_data.get(user_id, {}).get("credit", 0) < 10:
        await interaction.response.send_message("Mày không đủ credit, về cày tiếp đi.", ephemeral=True)
        return

    folder = get_session_path(user_id)
    os.makedirs(folder, exist_ok=True)
    script = get_tmate_script(user_id)

    with open(f"{folder}/setup.sh", "w") as f:
        f.write(script)

    proc = await asyncio.create_subprocess_shell(
        f"bash {folder}/setup.sh",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    ssh_link = stdout.decode().strip().splitlines()[-1]

    credit_data[user_id]["credit"] -= 10
    credit_data[user_id]["expire"] = get_expiry_time()
    save_credits(credit_data)

    await send_dm(interaction.user, f"🖥️ VPS mày đây: `{ssh_link}`")
    await interaction.response.send_message("✅ Đã gửi link VPS qua tin nhắn riêng. Cút qua đó mà dùng.")

@tree.command(name="timevps", description="Xem thời gian còn lại VPS")
async def timevps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit_data = load_credits()
    expire = credit_data.get(user_id, {}).get("expire")
    if not expire:
        await interaction.response.send_message("Mày chưa có VPS đâu con gà.")
        return
    expire_time = datetime.fromisoformat(expire)
    remaining = expire_time - datetime.utcnow()
    if remaining.total_seconds() <= 0:
        await interaction.response.send_message("VPS mày hết hạn lâu rồi, xài ké hả?")
    else:
        await interaction.response.send_message(f"⏳ VPS còn sống {str(remaining).split('.')[0]}.")

@tree.command(name="renew", description="Gia hạn VPS (10 credit)")
async def renew(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit_data = load_credits()

    if credit_data.get(user_id, {}).get("credit", 0) < 10:
        await interaction.response.send_message("Mày không đủ credit để gia hạn, bốc c.!", ephemeral=True)
        return

    expire_time = datetime.fromisoformat(credit_data[user_id].get("expire", get_expiry_time()))
    credit_data[user_id]["credit"] -= 10
    credit_data[user_id]["expire"] = (expire_time + timedelta(days=1)).isoformat()
    save_credits(credit_data)

    await interaction.response.send_message("✅ Gia hạn VPS xong rồi đó thằng ngu.")

@tree.command(name="stopvps", description="Xoá VPS")
async def stopvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    folder = get_session_path(user_id)
    if os.path.exists(folder):
        subprocess.run(["rm", "-rf", folder])
    await interaction.response.send_message("🛑 Xoá sạch VPS rồi đó thằng ngu.")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã online với tên: {bot.user}")
