import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import shutil
import psutil
import asyncio
from datetime import datetime
import random

TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

vps_logs = {}

def toxic_reply():
    replies = [
        "Ủa sao tạo hoài vậy cha nội? 🐸",
        "Mỗi ngày 2 cái thôi, tạo nữa tao ban á 😤",
        "Nay spam đủ rồi nha cưng, đi ngủ đi mai làm tiếp 😏",
        "Tham vừa thôi chứ, ăn nhiều dễ nghẹn đó 🤭",
        "Tạo VPS kiểu này server tao thành nghĩa địa luôn á 🪦",
        "Đủ quota rồi cha, còn ham gì nữa 🙄",
    ]
    return random.choice(replies)

def success_reply(user):
    replies = [
        f"Được rồi đó <@{user.id}>, tao tạo cho lần này thôi đó 😑",
        f"VPS của mày đây nè, lo mà dùng đi 🤖",
        f"Hên đó <@{user.id}>, tao rảnh nên tao làm cho nè 😏",
        f"Khởi tạo cho mày xong rồi, dùng lẹ lẹ đi đừng hỏi nhiều 😴",
        f"Máy ảo của mày chạy rồi đó, phá banh càng vào đi 💥",
    ]
    return random.choice(replies)

def get_today_date():
    return datetime.utcnow().strftime("%Y-%m-%d")

def count_user_vps_today(user_id):
    today = get_today_date()
    if user_id not in vps_logs:
        return 0
    return sum(1 for date in vps_logs[user_id] if date == today)

def log_user_vps(user_id):
    today = get_today_date()
    if user_id not in vps_logs:
        vps_logs[user_id] = []
    vps_logs[user_id].append(today)

def download_rootfs():
    url = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"
    filename = "ubuntu-rootfs.tar.xz"
    if not os.path.exists("ubuntu-fs"):
        os.makedirs("ubuntu-fs")
    subprocess.run(["wget", "-O", filename, url])
    subprocess.run(["tar", "-xJf", filename, "-C", "ubuntu-fs"])
    os.remove(filename)

def generate_start_script():
    with open("start.sh", "w") as f:
        f.write("""#!/bin/bash
cd ubuntu-fs
unset LD_PRELOAD
proot \\
  -0 -r . \\
  -b /dev -b /proc -b /sys -b /tmp:/tmp \\
  -w /root \\
  /bin/bash -c "echo root@servertipacvn > /etc/hostname && apt update && apt install -y tmate && tmate -F"
""")
    os.chmod("start.sh", 0o755)

@bot.tree.command(name="deploy", description="Khởi tạo VPS Ubuntu trong proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Lệnh này không được dùng ở đây.", ephemeral=True)
        return

    user_id = interaction.user.id
    today_vps = count_user_vps_today(user_id)

    if today_vps >= 2:
        await interaction.response.send_message(
            f"⛔ {toxic_reply()}\n🕛 Mai quay lại sau 0h UTC đi ông nội!",
            ephemeral=True
        )
        return

    session_id = str(uuid.uuid4())[:8]
    folder_name = f"vps_{user_id}_{session_id}"
    os.makedirs(folder_name, exist_ok=True)
    os.chdir(folder_name)

    await interaction.response.send_message(
        f"🛠️ {success_reply(interaction.user)}\n📦 Đang tải Ubuntu cloud image..."
    )

    download_rootfs()
    generate_start_script()
    log_user_vps(user_id)

    await interaction.followup.send("✅ Đã tải xong Ubuntu.\n⏳ Đợi tí tao setup trong 3 giây...")

    for i in range(3, 0, -1):
        await interaction.followup.send(f"🔁 Chuẩn bị nổ máy sau {i}...")
        await asyncio.sleep(1)

    await interaction.followup.send("🚀 VPS đang chạy, chờ lấy SSH tmate nhen...")

    proc = subprocess.Popen(["./start.sh"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    ssh_line = None
    for line in proc.stdout:
        print(line.strip())
        if "ssh " in line and "tmate.io" in line:
            ssh_line = line.strip()
            break

    if ssh_line:
        await interaction.user.send(f"🔗 SSH đây cha: `{ssh_line}`\n👻 Nhớ dùng lẹ kẻo timeout.")
        await interaction.followup.send("✅ Tao gửi SSH qua tin nhắn riêng rồi đó. Xài lẹ lẹ đi 😎")
    else:
        await interaction.followup.send("❌ Bị gì rồi cha nội, lấy SSH không được...")

    os.chdir("..")

@bot.tree.command(name="statusvps", description="Xem tình trạng CPU và RAM VPS")
async def statusvps(interaction: discord.Interaction):
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_usage = ram.used // (1024 * 1024)
    ram_total = ram.total // (1024 * 1024)

    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"**CPU:** {cpu_percent}%\n**RAM:** {ram_usage}MB / {ram_total}MB",
        color=0x00ff00
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")

    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
