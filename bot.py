import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import uuid
import shutil
import time
import asyncio
from dotenv import load_dotenv
import psutil

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_vps_counter = {}

@bot.event
async def on_ready():
    print(f"Bot đã đăng nhập với tên: {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi khi đồng bộ lệnh slash: {e}")

def create_vps_folder(user_id):
    folder = f"vps_{user_id}_{uuid.uuid4().hex[:6]}"
    path = os.path.join("vps_data", folder)
    os.makedirs(path, exist_ok=True)
    return path

def get_cpu_ram():
    cpu_percent = psutil.cpu_percent(interval=1)
    ram_percent = psutil.virtual_memory().percent
    return cpu_percent, ram_percent

@tree.command(name="statusvps", description="Xem tình trạng VPS (CPU & RAM %)")
async def statusvps(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Lệnh này chỉ dùng trong kênh được cho phép.", ephemeral=True)

    cpu, ram = get_cpu_ram()
    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"<:RAM:1147501868264722442> RAM: `{ram}%`\n<:cpu:1147496245766668338> CPU: `{cpu}%`",
        color=discord.Color.green()
    )
    embed.set_footer(text="Tham gia Discord: https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed)

@tree.command(name="deploy", description="Tạo VPS Ubuntu cloud image (2 VPS/ngày)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Lệnh này chỉ dùng trong kênh được cho phép.", ephemeral=True)

    user_id = interaction.user.id
    today = time.strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    user_vps_counter[key] = user_vps_counter.get(key, 0)

    if user_vps_counter[key] >= 2:
        return await interaction.response.send_message("⚠️ Bạn chỉ được tạo tối đa 2 VPS mỗi ngày.", ephemeral=True)

    await interaction.response.send_message("🚀 Đang tải Ubuntu cloud image...", ephemeral=True)

    folder_path = create_vps_folder(user_id)
    os.chdir(folder_path)

    url = "https://cloud-images.ubuntu.com/releases/current/arm64/ubuntu-24.04-server-cloudimg-arm64-root.tar.xz"
    subprocess.run(f"wget '{url}' -O ubuntu.tar.xz --no-check-certificate", shell=True)

    subprocess.run("tar -xf ubuntu.tar.xz", shell=True)

    countdown = 5
    for i in range(countdown, 0, -1):
        await interaction.followup.send(f"⏳ Chuẩn bị chạy VPS sau {i}s...", ephemeral=True)
        time.sleep(1)

    with open("start.sh", "w") as f:
        f.write(f"""#!/bin/bash
proot -0 -r . -b /dev -b /proc -b /sys -b /data/data/com.termux/files/home:/host-root -w /root /usr/bin/env -i HOME=/root TERM=$TERM PS1='[root@servertipacvn \\W]# ' PATH=/bin:/usr/bin:/sbin:/usr/sbin:/usr/local/bin:/usr/local/sbin hostname=root@servertipacvn /bin/bash --login -c "apt update && apt install -y tmate && tmate -F > ssh.txt"
""")
    subprocess.run("chmod +x start.sh", shell=True)

    subprocess.Popen(["bash", "start.sh"])

    await interaction.followup.send("✅ VPS đã khởi chạy! Chờ vài giây để nhận SSH qua tin nhắn riêng.", ephemeral=True)

    ssh_path = os.path.join(folder_path, "ssh.txt")
    for _ in range(30):
        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh_link = f.read().strip()
            try:
                await interaction.user.send(f"🔐 SSH VPS của bạn:\n```{ssh_link}```")
            except:
                await interaction.followup.send("❌ Không thể gửi tin nhắn riêng. Hãy bật tin nhắn từ server.", ephemeral=True)
            break
        time.sleep(2)
    else:
        await interaction.followup.send("⚠️ Không tìm thấy SSH sau 60s. VPS có thể đã lỗi.", ephemeral=True)

@tree.command(name="chat", description="Nói chuyện bố láo với bot 🤖")
@app_commands.describe(message="Nội dung bạn muốn bot phản hồi")
async def chat(interaction: discord.Interaction, message: str):
    responses = [
        "Ủa rồi sao? 😎", "Tao không quan tâm nha 😏", "Hỏi chi lắm vậy trời 🤡",
        "Thứ như mày mà cũng đòi hỏi à 🤭", "Bị ngu à? Hỏi gì kỳ cục vậy?",
        "Đang bận gõ lệnh, để sau đi ông nội 🙄"
    ]
    import random
    await interaction.response.send_message(random.choice(responses), ephemeral=False)

bot.run(TOKEN)
