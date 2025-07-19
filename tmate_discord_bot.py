import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess
import os
import asyncio
import json
import time
from dotenv import load_dotenv

# ====== CẤU HÌNH ======
load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104  # Thay bằng ID owner thật
ALLOWED_CHANNEL_ID = 1378918272812060742  # Thay bằng ID kênh được dùng bot

CREDIT_FILE = "credits.json"
VPS_DIR = "vps"
CONFIG_FILE = "configs.json"
UBUNTU_URL = "https://partner-images.canonical.com/core/jammy/current/ubuntu-jammy-core-cloudimg-amd64-root.tar.gz"

if not os.path.exists(CREDIT_FILE):
    with open(CREDIT_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(VPS_DIR):
    os.makedirs(VPS_DIR)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ====== HÀM XỬ LÝ CREDIT ======

def load_credits():
    with open(CREDIT_FILE, "r") as f:
        return json.load(f)

def save_credits(data):
    with open(CREDIT_FILE, "w") as f:
        json.dump(data, f)

def get_credit(uid):
    data = load_credits()
    return data.get(str(uid), {}).get("credit", 0)

def add_credit(uid, amount):
    data = load_credits()
    user = data.get(str(uid), {"credit": 0, "last_get": 0})
    user["credit"] += amount
    data[str(uid)] = user
    save_credits(data)

def set_credit(uid, amount):
    data = load_credits()
    user = data.get(str(uid), {"credit": 0, "last_get": 0})
    user["credit"] = amount
    data[str(uid)] = user
    save_credits(data)

# ====== HÀM VPS ======

def user_vps_dir(uid):
    return os.path.join(VPS_DIR, str(uid))

def vps_running(uid):
    return os.path.exists(os.path.join(user_vps_dir(uid), "tmate.sock"))

def kill_vps(uid):
    path = user_vps_dir(uid)
    subprocess.call(f"pkill -f 'tmate -S {path}/tmate.sock'", shell=True)
    subprocess.call(f"pkill -f 'proot -S {path}/ubuntu'", shell=True)

def create_vps(uid):
    path = user_vps_dir(uid)
    os.makedirs(path, exist_ok=True)
    ubuntu_tar = os.path.join(path, "ubuntu.tar.gz")
    ubuntu_root = os.path.join(path, "ubuntu")

    if not os.path.exists(ubuntu_tar):
        subprocess.call(f"wget -O {ubuntu_tar} {UBUNTU_URL}", shell=True)
    if not os.path.exists(ubuntu_root):
        os.makedirs(ubuntu_root, exist_ok=True)
        subprocess.call(f"proot --link2symlink -0 -r {ubuntu_root} -- tar -xf {ubuntu_tar} -C {ubuntu_root}", shell=True)

    tmate_sock = os.path.join(path, "tmate.sock")
    cmd = (
        f"tmate -S {tmate_sock} new-session -d && "
        f"tmate -S {tmate_sock} wait tmate-ready && "
        f"tmate -S {tmate_sock} display -p '#{{tmate_ssh}}'"
    )
    ssh = subprocess.check_output(cmd, shell=True).decode().strip()
    return ssh

# ====== LỆNH ======

@tree.command(name="deploy", description="Tạo VPS Ubuntu bằng proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Cút về channel được phép xài bot, thằng ngu!", ephemeral=True)
        return
    uid = interaction.user.id
    credit = get_credit(uid)
    configs = json.load(open(CONFIG_FILE))
    if str(uid) not in configs:
        await interaction.response.send_message("Mày chưa /setcauhinh, làm ơn set trước khi xài /deploy!", ephemeral=True)
        return
    cost = configs[str(uid)]["cost"]
    if credit < cost:
        await interaction.response.send_message(f"Đù má mày thiếu credit, cần {cost}, mày có {credit} thôi!", ephemeral=True)
        return
    add_credit(uid, -cost)
    ssh = create_vps(uid)
    await interaction.response.send_message("Tao đang gửi SSH riêng cho mày qua DM!")
    try:
        await interaction.user.send(f"🎯 Đây là SSH của mày:\n`{ssh}`\nThời hạn VPS: 1 ngày")
    except:
        await interaction.followup.send("DM mày tắt rồi, không gửi được!", ephemeral=True)

@tree.command(name="stopvps", description="Tắt VPS")
async def stopvps(interaction: discord.Interaction):
    uid = interaction.user.id
    kill_vps(uid)
    await interaction.response.send_message("VPS mày đã bị tao xử đẹp 😎", ephemeral=True)

@tree.command(name="renew", description="Gia hạn VPS")
async def renew(interaction: discord.Interaction):
    uid = interaction.user.id
    credit = get_credit(uid)
    configs = json.load(open(CONFIG_FILE))
    if str(uid) not in configs:
        await interaction.response.send_message("Chưa có cấu hình để renew!", ephemeral=True)
        return
    cost = configs[str(uid)]["cost"]
    if credit < cost:
        await interaction.response.send_message(f"Không đủ credit để gia hạn! Mày có {credit}, cần {cost}", ephemeral=True)
        return
    add_credit(uid, -cost)
    await interaction.response.send_message("Đã gia hạn VPS thêm 1 ngày, đừng để tao phải nói lần 2 😒", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    await interaction.response.send_message("Chức năng này đang dev, đợi đi thằng hấp 😎", ephemeral=True)

@tree.command(name="getcredit", description="Nhận credit mỗi 12h")
async def getcredit(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    data = load_credits()
    now = time.time()
    user = data.get(uid, {"credit": 0, "last_get": 0})
    if now - user["last_get"] < 43200:
        await interaction.response.send_message("Đợi 12h nữa hẵng xin credit nhé, đồ ăn hại 😡", ephemeral=True)
        return
    user["credit"] += 1
    user["last_get"] = now
    data[uid] = user
    save_credits(data)
    await interaction.response.send_message("Đã nhận 1 credit, nhớ dùng cho đàng hoàng 😏", ephemeral=True)

@tree.command(name="credit", description="Xem credit hiện tại")
async def credit(interaction: discord.Interaction):
    uid = interaction.user.id
    c = get_credit(uid)
    await interaction.response.send_message(f"Mày đang có {c} credit, xài cho khôn!", ephemeral=True)

@tree.command(name="givecredit", description="Admin tặng credit")
@app_commands.describe(user="Người nhận", amount="Số credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Câm mõm, mày không có quyền!", ephemeral=True)
        return
    add_credit(user.id, amount)
    await interaction.response.send_message(f"Đã cộng {amount} credit cho {user.mention}")

@tree.command(name="xoacredit", description="Xoá toàn bộ credit user")
@app_commands.describe(user="Người bị xoá")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Cút, lệnh này chỉ cho bố tao!", ephemeral=True)
        return
    set_credit(user.id, 0)
    await interaction.response.send_message(f"Đã xoá sạch credit của {user.mention}")

@tree.command(name="cuoccredit", description="Xem top người có credit")
async def cuoccredit(interaction: discord.Interaction):
    data = load_credits()
    sorted_users = sorted(data.items(), key=lambda x: x[1]["credit"], reverse=True)
    msg = "**💰 Top Credit:**\n"
    for i, (uid, val) in enumerate(sorted_users[:10], 1):
        user = await bot.fetch_user(int(uid))
        msg += f"{i}. {user.name}: {val['credit']} credit\n"
    await interaction.response.send_message(msg, ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.describe(level="Chọn cấp cấu hình (2/4/8/12/16 GB RAM)")
async def shopping(interaction: discord.Interaction, level: int):
    uid = interaction.user.id
    options = {
        2: {"cost": 20, "ram": "2GB", "cpu": 2},
        4: {"cost": 40, "ram": "4GB", "cpu": 4},
        8: {"cost": 80, "ram": "8GB", "cpu": 8},
        12: {"cost": 120, "ram": "12GB", "cpu": 12},
        16: {"cost": 160, "ram": "16GB", "cpu": 16},
    }
    if level not in options:
        await interaction.response.send_message("Chọn cấp RAM hợp lệ: 2, 4, 8, 12, 16!", ephemeral=True)
        return
    credit = get_credit(uid)
    if credit < options[level]["cost"]:
        await interaction.response.send_message("Credit mày không đủ để mua cấu hình này!", ephemeral=True)
        return
    add_credit(uid, -options[level]["cost"])
    configs = json.load(open(CONFIG_FILE))
    configs[str(uid)] = options[level]
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f)
    await interaction.response.send_message(f"Đã mua cấu hình {options[level]['ram']}, nhớ dùng /setcauhinh!", ephemeral=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua để dùng khi deploy")
async def setcauhinh(interaction: discord.Interaction):
    uid = interaction.user.id
    configs = json.load(open(CONFIG_FILE))
    if str(uid) not in configs:
        await interaction.response.send_message("Mày chưa mua cấu hình nào cả, /shopping ngay đi thằng ngu!", ephemeral=True)
        return
    await interaction.response.send_message("Đã chọn cấu hình thành công, mày deploy được rồi đó!", ephemeral=True)

# ====== KHỞI ĐỘNG ======

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đang chạy với tên {bot.user}")

bot.run(TOKEN)
