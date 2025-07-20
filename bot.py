import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import shutil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104  # sửa lại ID owner
ALLOWED_CHANNEL_ID = 1378918272812060742  # sửa lại ID kênh

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

def get_user_folder(user_id):
    return f"alpine_{user_id}"

@tree.command(name="deploy", description="Tạo VPS Alpine Linux qua proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Lệnh này không được phép ở đây.", ephemeral=True)
        return

    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    rootfs = "alpine-minirootfs.tar.gz"
    alpine_url = "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz"

    if os.path.exists(folder):
        shutil.rmtree(folder)

    os.makedirs(folder, exist_ok=True)

    await interaction.response.send_message("🔧 Đang cài đặt VPS Alpine...")

    try:
        if not os.path.exists(rootfs):
            subprocess.run(["curl", "-Lo", rootfs, alpine_url], check=True)

        result = subprocess.run(["tar", "-tzf", rootfs], capture_output=True)
        if result.returncode != 0:
            raise Exception("❌ File tar.gz bị lỗi hoặc tải sai!")

        subprocess.run(["tar", "-xzf", rootfs, "-C", folder], check=True)

        hostname_script = f"echo 'root@servertipacvn' > {folder}/etc/hostname"
        subprocess.run(hostname_script, shell=True)

        # Auto install tmate bên trong proot
        startup_script = f"""
        echo 'http://dl-cdn.alpinelinux.org/alpine/v3.19/main' > /etc/apk/repositories &&
        apk update &&
        apk add tmate openssh &&
        tmate -S /tmp/tmate.sock new-session -d &&
        tmate -S /tmp/tmate.sock wait tmate-ready &&
        tmate -S /tmp/tmate.sock display -p '#{{tmate_ssh}}' > /tmp/ssh.txt &&
        tail -f /dev/null
        """

        with open(f"{folder}/start.sh", "w") as f:
            f.write(startup_script)
        os.chmod(f"{folder}/start.sh", 0o755)

        session_id = str(uuid.uuid4())[:8]
        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/sh /start.sh"

        with open(f"{folder}/.session_id", "w") as f:
            f.write(session_id)

        subprocess.Popen(command, shell=True)

        await interaction.followup.send(f"✅ VPS Alpine đã khởi chạy!\n🆔 ID VPS của bạn: `{session_id}`")

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo VPS: {e}")

@tree.command(name="stopvps", description="Dừng VPS đã tạo")
async def stopvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    if os.path.exists(folder):
        shutil.rmtree(folder)
        await interaction.response.send_message("🛑 VPS đã bị xoá.")
    else:
        await interaction.response.send_message("❗ Bạn chưa có VPS đang chạy.")

@tree.command(name="renewvps", description="Gia hạn VPS nếu bị lỗi")
async def renewvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    start_script = f"{folder}/start.sh"
    if os.path.exists(start_script):
        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/sh /start.sh"
        subprocess.Popen(command, shell=True)
        await interaction.response.send_message("🔁 VPS đã được khởi chạy lại.")
    else:
        await interaction.response.send_message("❗ Không tìm thấy VPS để restart.")

@tree.command(name="xemssh", description="Lấy SSH VPS hiện tại")
async def getssh(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    ssh_path = f"{folder}/tmp/ssh.txt"

    if os.path.exists(ssh_path):
        with open(ssh_path) as f:
            ssh_link = f.read().strip()
        await interaction.user.send(f"🔐 SSH của bạn:\n```{ssh_link}```")
        await interaction.response.send_message("✅ SSH đã gửi qua DM.")
    else:
        await interaction.response.send_message("❗ Chưa có SSH session hoặc VPS chưa chạy.")

bot.run(TOKEN)
