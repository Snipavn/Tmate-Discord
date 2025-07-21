import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import shutil
import time
import psutil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    print(f"Bot đã sẵn sàng dưới tên {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi sync: {e}")

def get_user_folder(user_id):
    return f"debian_{user_id}"

@tree.command(name="deploy", description="Tạo VPS Debian qua proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("⛔ Lệnh này không dùng được ở đây.", ephemeral=True)
        return

    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    rootfs = "debian-rootfs.tar.gz"
    debian_url = "https://deb.debian.org/debian/dists/bookworm/main/installer-amd64/current/images/netboot/debian-installer/amd64/root.tar.gz"

    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)

    await interaction.response.send_message("🔧 Đang khởi tạo VPS Debian...")

    try:
        if not os.path.exists(rootfs):
            subprocess.run(["curl", "-Lo", rootfs, debian_url], check=True)

        subprocess.run(["tar", "-xzf", rootfs, "-C", folder], check=True)

        # Đặt hostname
        with open(f"{folder}/etc/hostname", "w") as f:
            f.write("root@servertipacvn\n")

        # start.sh
        startup_script = """
apt update
apt install -y tmate openssh-server sudo neofetch
tmate -S /tmp/tmate.sock new-session -d
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/ssh.txt
tail -f /dev/null
"""
        with open(f"{folder}/start.sh", "w") as f:
            f.write(startup_script)
        os.chmod(f"{folder}/start.sh", 0o755)

        session_id = str(uuid.uuid4())[:8]
        with open(f"{folder}/.session_id", "w") as f:
            f.write(session_id)

        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/bash /start.sh"
        subprocess.Popen(command, shell=True)

        ssh_path = f"{folder}/tmp/ssh.txt"
        for _ in range(30):
            if os.path.exists(ssh_path):
                time.sleep(1)
                break
            time.sleep(1)

        embed = discord.Embed(
            title="✅ VPS Debian đã sẵn sàng!",
            description=f"🆔 ID VPS: `{session_id}`\n📬 SSH đã gửi vào DM của bạn.",
            color=0x00ff00
        )
        embed.set_footer(text="Tham gia Discord: https://dsc.gg/servertipacvn")

        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh_link = f.read().strip()

            try:
                await interaction.user.send(f"🔐 VPS của bạn:\n`{ssh_link}`")
                await interaction.followup.send(embed=embed)
            except discord.Forbidden:
                embed.description += "\n⚠️ Không thể gửi DM. Hãy bật tin nhắn riêng!"
                await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("✅ VPS đã chạy nhưng chưa có SSH. Hãy thử lại sau vài giây.")

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi tạo VPS: {e}")

@tree.command(name="stopvps", description="Xoá VPS của bạn")
async def stopvps(interaction: discord.Interaction):
    folder = get_user_folder(interaction.user.id)
    if os.path.exists(folder):
        shutil.rmtree(folder)
        await interaction.response.send_message("🛑 VPS đã bị xoá.")
    else:
        await interaction.response.send_message("❗ Bạn chưa có VPS nào đang chạy.")

@tree.command(name="renewvps", description="Khởi chạy lại VPS nếu bị lỗi")
async def renewvps(interaction: discord.Interaction):
    folder = get_user_folder(interaction.user.id)
    if os.path.exists(f"{folder}/start.sh"):
        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/bash /start.sh"
        subprocess.Popen(command, shell=True)
        await interaction.response.send_message("🔁 VPS đã được khởi chạy lại.")
    else:
        await interaction.response.send_message("❗ Không tìm thấy VPS để restart.")

@tree.command(name="statusvps", description="Xem trạng thái CPU & RAM máy thật")
async def statusvps(interaction: discord.Interaction):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_used = ram.used // (1024 * 1024)
    ram_total = ram.total // (1024 * 1024)
    ram_percent = ram.percent

    embed = discord.Embed(
        title="📊 Trạng thái VPS (máy chủ)",
        description=f"**CPU:** {cpu}%\n**RAM:** {ram_used}MB / {ram_total}MB ({ram_percent}%)",
        color=0x3498db
    )
    embed.set_footer(text="Tham gia Discord: https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
