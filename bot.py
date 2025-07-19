import discord
from discord.ext import commands
from discord import app_commands
import subprocess, os, asyncio, random, time
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104  # thay bằng ID của bạn
ALLOWED_CHANNEL_ID = 1378918272812060742  # thay bằng ID kênh
ALLOWED_ROLE_ID = 997017581766574234  # thay bằng ID role

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_credits = {}
user_configs = {}
user_sessions = {}

# Tải credit từ file (nếu có)
if os.path.exists("credits.txt"):
    with open("credits.txt", "r") as f:
        for line in f:
            uid, credit = line.strip().split()
            user_credits[int(uid)] = int(credit)

def save_credits():
    with open("credits.txt", "w") as f:
        for uid, credit in user_credits.items():
            f.write(f"{uid} {credit}\n")

def get_config_price(ram):
    return {
        2: 20,
        4: 40,
        8: 80,
        12: 120,
        16: 160
    }.get(ram, 0)

@tree.command(name="getcredit")
async def get_credit(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    uid = interaction.user.id
    now = time.time()
    if os.path.exists(f"claim_{uid}") and now - os.path.getmtime(f"claim_{uid}") < 43200:
        await interaction.response.send_message("Bạn chỉ được nhận 1 credit mỗi 12 giờ.", ephemeral=True)
        return
    with open(f"claim_{uid}", "w") as f: f.write("x")
    user_credits[uid] = user_credits.get(uid, 0) + 1
    save_credits()
    await interaction.response.send_message(f"Bạn đã nhận 1 credit. Tổng: {user_credits[uid]}")

@tree.command(name="credit")
async def credit(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    uid = interaction.user.id
    await interaction.response.send_message(f"Bạn có {user_credits.get(uid, 0)} credit.")

@tree.command(name="givecredit")
@app_commands.describe(user="Người nhận", amount="Số lượng")
async def give_credit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID: return
    user_credits[user.id] = user_credits.get(user.id, 0) + amount
    save_credits()
    await interaction.response.send_message(f"Đã cộng {amount} credit cho {user.mention}")

@tree.command(name="xoacredit")
@app_commands.describe(user="Người bị xóa")
async def xoa_credit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID: return
    user_credits[user.id] = 0
    save_credits()
    await interaction.response.send_message(f"Đã xóa credit của {user.mention}")

@tree.command(name="cuoccredit")
async def cuoccredit(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    sorted_users = sorted(user_credits.items(), key=lambda x: x[1], reverse=True)
    msg = "\n".join([f"<@{uid}>: {credit}" for uid, credit in sorted_users[:10]])
    await interaction.response.send_message(f"**Top credit:**\n{msg}")

@tree.command(name="shopping")
@app_commands.describe(ram="RAM (2, 4, 8, 12, 16)")
async def shopping(interaction: discord.Interaction, ram: int):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    uid = interaction.user.id
    cost = get_config_price(ram)
    if cost == 0:
        await interaction.response.send_message("Cấu hình không hợp lệ.")
        return
    if user_credits.get(uid, 0) < cost:
        await interaction.response.send_message("Bạn không đủ credit.")
        return
    user_credits[uid] -= cost
    user_configs[uid] = ram
    save_credits()
    await interaction.response.send_message(f"Đã mua cấu hình VPS {ram}GB RAM.")

@tree.command(name="setcauhinh")
@app_commands.describe(ram="RAM (2, 4, 8, 12, 16)")
async def setcauhinh(interaction: discord.Interaction, ram: int):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    uid = interaction.user.id
    if ram not in [2, 4, 8, 12, 16] or user_configs.get(uid) != ram:
        await interaction.response.send_message("Bạn chưa mua cấu hình này.")
        return
    user_configs[uid] = ram
    await interaction.response.send_message(f"Đã set cấu hình VPS {ram}GB RAM.")

@tree.command(name="deploy")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID: return
    if not any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("Bạn không có quyền dùng lệnh này.")
        return
    uid = interaction.user.id
    if uid not in user_configs:
        await interaction.response.send_message("Bạn chưa set cấu hình VPS.")
        return

    vps_folder = f"/root/bot1/vps_{uid}"
    os.makedirs(vps_folder, exist_ok=True)
    tar_path = os.path.join(vps_folder, "ubuntu.tar.gz")
    await interaction.response.send_message("Đang tạo VPS. Vui lòng chờ...")

    if not os.path.exists(tar_path):
        subprocess.run(f"wget -O {tar_path} https://raw.githubusercontent.com/adi1090x/files/master/ubuntu.tar.gz", shell=True)

    cmd = (
        f"cd {vps_folder} && proot -r . -b /dev -b /proc -b /sys -w /root bash -c \""
        f"apt update && apt install -y tmate && "
        f"tmate -S /tmp/tmate.sock new-session -d && "
        f"tmate -S /tmp/tmate.sock wait tmate-ready && "
        f"tmate -S /tmp/tmate.sock display -p '#{{tmate_ssh}}' > ssh.txt\""
    )
    subprocess.Popen(cmd, shell=True)

    await asyncio.sleep(10)
    try:
        with open(f"{vps_folder}/ssh.txt") as f:
            ssh_link = f.read().strip()
        await interaction.user.send(f"🔐 SSH VPS của bạn:\n```{ssh_link}```")
        await interaction.followup.send("SSH đã gửi về tin nhắn riêng.")
    except:
        await interaction.followup.send("Lỗi khi gửi SSH.")

@tree.command(name="stopvps")
async def stopvps(interaction: discord.Interaction):
    uid = interaction.user.id
    folder = f"/root/bot1/vps_{uid}"
    subprocess.run(f"rm -rf {folder}", shell=True)
    await interaction.response.send_message("Đã xoá VPS.")

@tree.command(name="renew")
async def renew(interaction: discord.Interaction):
    uid = interaction.user.id
    folder = f"/root/bot1/vps_{uid}"
    subprocess.run(f"rm -rf {folder}", shell=True)
    await interaction.response.send_message("Đã gia hạn lại VPS.")

@tree.command(name="timevps")
async def timevps(interaction: discord.Interaction):
    uid = interaction.user.id
    folder = f"/root/bot1/vps_{uid}"
    if os.path.exists(folder):
        created = os.path.getctime(folder)
        alive = int(time.time() - created)
        await interaction.response.send_message(f"⏱ VPS hoạt động được {alive} giây.")
    else:
        await interaction.response.send_message("Bạn chưa tạo VPS.")

@bot.event
async def on_ready():
    await tree.sync()
    print("Bot đã sẵn sàng.")

bot.run(TOKEN)
