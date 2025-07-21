import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import uuid
import shutil
import psutil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

CREDIT_FILE = "credit.txt"
ROOTFS_URL = "https://raw.githubusercontent.com/Serv3rTipacVN/Linux-RootFS/main/debian-minimal.tar.xz"

# === Credit System ===
def get_credit(user_id):
    if not os.path.exists(CREDIT_FILE):
        return 0
    with open(CREDIT_FILE, "r") as f:
        for line in f:
            uid, credit = line.strip().split(":")
            if uid == str(user_id):
                return int(credit)
    return 0

def set_credit(user_id, credit):
    lines = []
    found = False
    if os.path.exists(CREDIT_FILE):
        with open(CREDIT_FILE, "r") as f:
            for line in f:
                uid, c = line.strip().split(":")
                if uid == str(user_id):
                    lines.append(f"{uid}:{credit}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{user_id}:{credit}\n")
    with open(CREDIT_FILE, "w") as f:
        f.writelines(lines)

# === Deploy VPS ===
def get_user_folder(user_id):
    return f"vps_{user_id}"

@tree.command(name="deploy", description="Tạo VPS Debian chạy nền và nhận SSH")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Bạn không được phép dùng lệnh này ở đây.")
        return

    user_id = interaction.user.id
    if get_credit(user_id) <= 0:
        await interaction.response.send_message("❌ Bạn không đủ credit để deploy VPS.")
        return

    set_credit(user_id, get_credit(user_id) - 1)

    await interaction.response.send_message("📦 Đang khởi tạo VPS Debian...")

    folder = get_user_folder(user_id)
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    os.system(f"wget -qO rootfs.tar.xz {ROOTFS_URL}")
    os.system(f"tar -xJf rootfs.tar.xz -C {folder}")
    os.remove("rootfs.tar.xz")

    startup_script = """
apt update
apt install -y tmate openssh-client sudo curl
tmate -S /tmp/tmate.sock new-session -d
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/ssh.txt
tail -f /dev/null
"""
    with open(os.path.join(folder, "start.sh"), "w") as f:
        f.write(startup_script)
    os.chmod(os.path.join(folder, "start.sh"), 0o755)

    session_id = str(uuid.uuid4())[:8]
    command = f"proot -0 -r {folder} -b /dev -b /proc -b /sys -w /root /bin/bash /start.sh"
    subprocess.Popen(command, shell=True)

    await interaction.followup.send(embed=discord.Embed(
        title="✅ VPS Debian đã khởi chạy!",
        description=f"🆔 ID VPS: `{session_id}`\n📬 SSH sẽ được gửi vào DM trong vài giây...",
        color=0x57F287
    ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))

    await asyncio.sleep(10)
    ssh_file = os.path.join(folder, "tmp", "ssh.txt")
    if os.path.exists(ssh_file):
        with open(ssh_file, "r") as f:
            ssh = f.read().strip()
        await interaction.user.send(f"🔐 SSH VPS của bạn:\n```{ssh}```")
    else:
        await interaction.followup.send(embed=discord.Embed(
            title="⚠️ VPS đã chạy nhưng chưa có SSH",
            description="Hãy thử lại sau vài giây.",
            color=0xFAA61A
        ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))

# === Stop VPS ===
@tree.command(name="stopvps", description="Tắt VPS của bạn")
async def stopvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    if os.path.exists(folder):
        shutil.rmtree(folder)
        await interaction.response.send_message(embed=discord.Embed(
            description="🛑 VPS đã bị xoá.",
            color=0xED4245
        ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))
    else:
        await interaction.response.send_message(embed=discord.Embed(
            description="❗ Không tìm thấy VPS để xoá.",
            color=0xED4245
        ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))

# === Restart VPS ===
@tree.command(name="renewvps", description="Khởi động lại VPS")
async def renewvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)

    if not os.path.exists(folder):
        await interaction.response.send_message(embed=discord.Embed(
            description="❗ Không tìm thấy VPS để restart.",
            color=0xED4245
        ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))
        return

    command = f"proot -0 -r {folder} -b /dev -b /proc -b /sys -w /root /bin/bash /start.sh"
    subprocess.Popen(command, shell=True)

    await interaction.response.send_message(embed=discord.Embed(
        description="🔁 VPS đã được khởi chạy lại.",
        color=0x5865F2
    ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))

# === Trạng thái VPS ===
@tree.command(name="statusvps", description="Xem trạng thái VPS đang chạy")
async def statusvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)

    if not os.path.exists(folder):
        await interaction.response.send_message(embed=discord.Embed(
            description="❗ Bạn chưa có VPS nào đang hoạt động.",
            color=0xED4245
        ).set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn"))
        return

    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    ram_used = f"{round(mem.used / 1024 / 1024)}MB"
    ram_total = f"{round(mem.total / 1024 / 1024)}MB"

    embed = discord.Embed(
        title="📊 Trạng thái VPS của bạn",
        description=f"🖥️ CPU: `{cpu_percent}%`\n💾 RAM: `{ram_used} / {ram_total}`",
        color=0x66ccff
    )
    embed.set_footer(text="Tham gia server Discord: https://dsc.gg/servertipacvn")

    await interaction.response.send_message(embed=embed)

# === Khởi động bot ===
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã đăng nhập với tên: {bot.user}")

bot.run(TOKEN)
