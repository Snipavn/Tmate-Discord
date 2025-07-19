import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import uuid
import asyncio
from dotenv import load_dotenv

# ====== CONFIG ======
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104  # ID của owner
ALLOWED_CHANNEL_ID = 1378918272812060742  # Chỉ cho phép chạy trong channel này
ROOTFS_URL = "https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz"
# ====================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

users_credit = {}
users_config = {}
active_sessions = {}

def get_user_folder(user_id):
    return f"users/{user_id}"

def get_proot_command(user_id):
    user_folder = get_user_folder(user_id)
    return f"proot -0 -r {user_folder}/alpine -b /dev -b /proc -w /root /bin/sh -c \"{INSTALL_AND_RUN_TMUX}\""

INSTALL_AND_RUN_TMUX = (
    "apk update && apk add tmate openssh curl bash neofetch && "
    "tmate -S /tmp/tmate.sock new-session -d && "
    "tmate -S /tmp/tmate.sock wait tmate-ready && "
    "tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/sshlink && "
    "sleep 3600"
)

async def send_ssh_dm(user: discord.User, user_id):
    ssh_file = f"{get_user_folder(user_id)}/alpine/tmp/sshlink"
    for _ in range(30):
        if os.path.exists(ssh_file):
            with open(ssh_file) as f:
                ssh_link = f.read().strip()
            await user.send(f"🔑 SSH của bạn: `{ssh_link}`")
            return
        await asyncio.sleep(2)
    await user.send("❌ Không lấy được SSH, vui lòng thử lại.")

@bot.event
async def on_ready():
    print(f"Đã đăng nhập: {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print("Lỗi sync:", e)

@tree.command(name="deploy", description="Tạo VPS Alpine kèm SSH")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("❌ Không được dùng ở đây", ephemeral=True)

    user_id = str(interaction.user.id)
    if user_id not in users_config:
        return await interaction.response.send_message("❌ Hãy dùng /setcauhinh trước.", ephemeral=True)

    if users_credit.get(user_id, 0) < 10:
        return await interaction.response.send_message("❌ Không đủ credit (10)", ephemeral=True)

    folder = get_user_folder(user_id)
    rootfs_path = f"{folder}/alpine"
    os.makedirs(folder, exist_ok=True)

    if not os.path.exists(rootfs_path):
        await interaction.response.send_message("📦 Đang tải Alpine...", ephemeral=True)
        os.system(f"curl -L {ROOTFS_URL} | tar -xz -C {folder}")

    await interaction.followup.send("🚀 Đang khởi động VPS...")

    command = get_proot_command(user_id)
    session = subprocess.Popen(command, shell=True)
    active_sessions[user_id] = session

    await send_ssh_dm(interaction.user, user_id)

@tree.command(name="stopvps", description="Dừng VPS")
async def stopvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    session = active_sessions.get(user_id)
    if session:
        session.terminate()
        await interaction.response.send_message("✅ VPS đã dừng.")
    else:
        await interaction.response.send_message("❌ Không tìm thấy VPS.")

@tree.command(name="renew", description="Gia hạn VPS")
async def renew(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in active_sessions:
        return await interaction.response.send_message("❌ Bạn chưa có VPS đang chạy.")
    if users_credit.get(user_id, 0) < 10:
        return await interaction.response.send_message("❌ Không đủ credit để gia hạn.")
    users_credit[user_id] -= 10
    await interaction.response.send_message("🔄 VPS đã được gia hạn thêm 1 giờ.")

@tree.command(name="givecredit", description="Thêm credit (owner)")
@app_commands.describe(user="Người nhận", amount="Số lượng")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Không có quyền.")
    uid = str(user.id)
    users_credit[uid] = users_credit.get(uid, 0) + amount
    await interaction.response.send_message(f"✅ Đã thêm {amount} credit cho {user.name}")

@tree.command(name="getcredit", description="Nhận 1 credit mỗi 12h")
async def getcredit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    users_credit[user_id] = users_credit.get(user_id, 0) + 1
    await interaction.response.send_message("✅ Bạn đã nhận 1 credit (12h cooldown).")

@tree.command(name="credit", description="Xem credit hiện tại")
async def credit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit = users_credit.get(user_id, 0)
    await interaction.response.send_message(f"💰 Bạn có {credit} credit.")

@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.choices(
    cauhinh=[
        app_commands.Choice(name="2GB RAM, 2 core (20c)", value="2"),
        app_commands.Choice(name="4GB RAM, 4 core (40c)", value="4"),
        app_commands.Choice(name="8GB RAM, 8 core (80c)", value="8"),
        app_commands.Choice(name="12GB RAM, 12 core (120c)", value="12"),
        app_commands.Choice(name="16GB RAM, 16 core (160c)", value="16")
    ]
)
async def shopping(interaction: discord.Interaction, cauhinh: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    cost = int(cauhinh.value) * 10
    if users_credit.get(user_id, 0) < cost:
        return await interaction.response.send_message("❌ Không đủ credit.")
    users_credit[user_id] -= cost
    users_config[user_id] = cauhinh.value
    await interaction.response.send_message(f"✅ Đã mua cấu hình {cauhinh.name}.")

@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua")
@app_commands.choices(
    cauhinh=[
        app_commands.Choice(name="2GB RAM, 2 core", value="2"),
        app_commands.Choice(name="4GB RAM, 4 core", value="4"),
        app_commands.Choice(name="8GB RAM, 8 core", value="8"),
        app_commands.Choice(name="12GB RAM, 12 core", value="12"),
        app_commands.Choice(name="16GB RAM, 16 core", value="16")
    ]
)
async def setcauhinh(interaction: discord.Interaction, cauhinh: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    if users_config.get(user_id) != cauhinh.value:
        return await interaction.response.send_message("❌ Bạn chưa mua cấu hình này.")
    users_config[user_id] = cauhinh.value
    await interaction.response.send_message(f"✅ Đã chọn cấu hình {cauhinh.name}.")

bot.run(TOKEN)
