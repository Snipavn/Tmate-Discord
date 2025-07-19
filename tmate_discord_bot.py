import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import time
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104  # sửa thành ID owner thật
ALLOWED_CHANNEL_ID = 1378918272812060742  # sửa thành ID channel thật

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_credits = {}
user_vps = {}
user_cauhinh = {}

ubuntu_url = "https://partner-images.canonical.com/core/focal/current/ubuntu-focal-core-cloudimg-amd64-root.tar.gz"
ubuntu_file = "ubuntu.tar.gz"

@bot.event
async def on_ready():
    print(f"Bot đã sẵn sàng với tên {bot.user}")
    await tree.sync()

def save_file(path, content):
    with open(path, "w") as f:
        f.write(content)

def load_ssh(session_path):
    try:
        result = subprocess.check_output([
            "tmate", "-S", session_path, "display", "-p", "#{tmate_ssh}"
        ])
        return result.decode().strip()
    except:
        return None

@tree.command(name="getcredit", description="Nhận 5 credit mỗi 12 tiếng")
async def getcredit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = int(time.time())
    last = user_credits.get(f"{user_id}_last", 0)
    if now - last < 43200:
        await interaction.response.send_message("Mày chỉ có thể nhận credit sau 12 tiếng!", ephemeral=True)
    else:
        user_credits[f"{user_id}_last"] = now
        user_credits[user_id] = user_credits.get(user_id, 0) + 5
        await interaction.response.send_message("Bạn đã nhận được 5 credit!", ephemeral=True)

@tree.command(name="credit", description="Xem số credit")
async def credit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit = user_credits.get(user_id, 0)
    await interaction.response.send_message(f"Bạn có {credit} credit", ephemeral=True)

@tree.command(name="givecredit", description="Tặng credit (admin)")
@app_commands.describe(user="Người nhận", amount="Số lượng")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bạn không có quyền.", ephemeral=True)
        return
    uid = str(user.id)
    user_credits[uid] = user_credits.get(uid, 0) + amount
    await interaction.response.send_message(f"Đã tặng {amount} credit cho {user.mention}", ephemeral=True)

@tree.command(name="xoacredit", description="Xóa credit (admin)")
@app_commands.describe(user="Người bị xóa", amount="Số lượng")
async def xoacredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bạn không có quyền.", ephemeral=True)
        return
    uid = str(user.id)
    user_credits[uid] = max(0, user_credits.get(uid, 0) - amount)
    await interaction.response.send_message(f"Đã xóa {amount} credit của {user.mention}", ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.describe(option="Chọn cấu hình")
async def shopping(interaction: discord.Interaction, option: str):
    user_id = str(interaction.user.id)
    options = {
        "2GB-2core": 20,
        "4GB-4core": 40,
        "8GB-8core": 80,
        "12GB-12core": 120,
        "16GB-16core": 160
    }
    if option not in options:
        await interaction.response.send_message("Cấu hình không hợp lệ.", ephemeral=True)
        return
    cost = options[option]
    if user_credits.get(user_id, 0) < cost:
        await interaction.response.send_message("Không đủ credit.", ephemeral=True)
        return
    user_credits[user_id] -= cost
    user_cauhinh[user_id] = option
    await interaction.response.send_message(f"Đã mua cấu hình {option}", ephemeral=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình VPS đã mua")
@app_commands.describe(option="Cấu hình muốn chọn")
async def setcauhinh(interaction: discord.Interaction, option: str):
    user_id = str(interaction.user.id)
    if user_cauhinh.get(user_id) != option:
        await interaction.response.send_message("Bạn chưa mua cấu hình này.", ephemeral=True)
    else:
        user_vps[user_id] = option
        await interaction.response.send_message(f"Đã chọn cấu hình {option} để dùng.", ephemeral=True)

@tree.command(name="deploy", description="Tạo VPS")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Bạn không thể dùng lệnh ở đây!", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    if user_id not in user_vps:
        await interaction.response.send_message("Bạn chưa chọn cấu hình VPS. Dùng /setcauhinh", ephemeral=True)
        return

    credit = user_credits.get(user_id, 0)
    if credit < 10:
        await interaction.response.send_message("Cần ít nhất 10 credit để tạo VPS!", ephemeral=True)
        return

    folder = f"vps/{user_id}"
    os.makedirs(folder, exist_ok=True)
    tar_path = f"{folder}/{ubuntu_file}"
    if not os.path.exists(tar_path):
        subprocess.run(f"curl -L {ubuntu_url} -o {tar_path}", shell=True)

    command = (
        f"proot -R {folder} /bin/bash -c 'apt update && apt install -y openssh-server && service ssh start && bash'"
    )

    session_path = f"/tmp/tmate_{user_id}.sock"
    subprocess.Popen(
        f"tmate -S {session_path} new-session -d && "
        f"tmate -S {session_path} wait tmate-ready",
        shell=True
    )

    await asyncio.sleep(3)
    ssh = load_ssh(session_path)
    if ssh:
        await interaction.user.send(f"SSH của bạn: `{ssh}`")
        await interaction.response.send_message("Tạo xong VPS, SSH đã gửi DM.", ephemeral=True)
        user_credits[user_id] -= 10
        user_vps[user_id] = {
            "session": session_path,
            "time": int(time.time())
        }
    else:
        await interaction.response.send_message("Tạo SSH thất bại!", ephemeral=True)

@tree.command(name="stopvps", description="Dừng VPS")
async def stopvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    info = user_vps.get(user_id)
    if not info:
        await interaction.response.send_message("Bạn chưa tạo VPS!", ephemeral=True)
        return
    subprocess.run(f"tmate -S {info['session']} kill-session", shell=True)
    await interaction.response.send_message("Đã dừng VPS.", ephemeral=True)
    del user_vps[user_id]

@tree.command(name="renew", description="Gia hạn VPS")
async def renew(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_vps:
        await interaction.response.send_message("Bạn chưa có VPS để gia hạn!", ephemeral=True)
        return
    if user_credits.get(user_id, 0) < 10:
        await interaction.response.send_message("Không đủ credit để gia hạn!", ephemeral=True)
        return
    user_credits[user_id] -= 10
    user_vps[user_id]["time"] = int(time.time())
    await interaction.response.send_message("Đã gia hạn VPS thêm 1 ngày!", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian VPS còn lại")
async def timevps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_vps:
        await interaction.response.send_message("Bạn chưa tạo VPS!", ephemeral=True)
        return
    created = user_vps[user_id]["time"]
    remaining = 86400 - (int(time.time()) - created)
    h = remaining // 3600
    m = (remaining % 3600) // 60
    s = remaining % 60
    await interaction.response.send_message(f"VPS còn {h} giờ {m} phút {s} giây", ephemeral=True)

@tree.command(name="cuoccredit", description="Xem credit đã dùng")
async def cuoccredit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    total = 0
    if user_id in user_vps:
        created = user_vps[user_id]["time"]
        days = (int(time.time()) - created) // 86400 + 1
        total = days * 10
    await interaction.response.send_message(f"Bạn đã dùng {total} credit cho VPS.", ephemeral=True)

bot.run(TOKEN)
