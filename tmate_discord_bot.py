import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess
import os
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

#TOKEN
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DB_FILE = "db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

@bot.event
async def on_ready():
    check_vps_expiry.start()
    print(f"Bot online: {bot.user}")

def is_owner(interaction):
    return interaction.user.id == OWNER_ID

def allowed_channel(interaction):
    return interaction.channel.id == ALLOWED_CHANNEL_ID

@tree.command(name="credit", description="Kiểm tra credit của mày")
async def credit(interaction: discord.Interaction):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.get(uid, {})
    coin = user.get("credit", 0)
    await interaction.response.send_message(f"Mày còn {coin} coin, nghèo rớt mồng tơi.")

@tree.command(name="getcredit", description="Xin thêm 1 coin (12h 1 lần)")
async def getcredit(interaction: discord.Interaction):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.setdefault(uid, {})
    last = user.get("last_claim")
    now = datetime.utcnow()

    if last and (now - datetime.fromisoformat(last)) < timedelta(hours=12):
        return await interaction.response.send_message("Mỗi 12 tiếng mới xin được, đồ ăn hại.", ephemeral=True)

    user["credit"] = user.get("credit", 0) + 1
    user["last_claim"] = now.isoformat()
    save_db(db)
    await interaction.response.send_message("Đã cho 1 coin. Cầm đỡ mà sống.")

@tree.command(name="givecredit", description="Cho coin cho thằng ngu nào đó (chỉ owner)")
@app_commands.describe(user="Thằng cần được bố thí", amount="Số coin")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Cút, mày không phải admin.", ephemeral=True)
    uid = str(user.id)
    db = load_db()
    db.setdefault(uid, {})["credit"] = db.get(uid, {}).get("credit", 0) + amount
    save_db(db)
    await interaction.response.send_message(f"Đã cho {amount} coin cho {user.mention}.")

@tree.command(name="xoacredit", description="Xoá coin của đứa nào đó (chỉ owner)")
@app_commands.describe(user="Thằng bị trừ", amount="Số coin")
async def xoacredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày méo phải admin, câm.", ephemeral=True)
    uid = str(user.id)
    db = load_db()
    db.setdefault(uid, {})["credit"] = max(0, db.get(uid, {}).get("credit", 0) - amount)
    save_db(db)
    await interaction.response.send_message(f"Đã trừ {amount} coin của {user.mention}.")

@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.describe(option="Chọn cấu hình muốn mua")
async def shopping(interaction: discord.Interaction, option: str):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    options = {
        "2core_2gb": 20,
        "4core_4gb": 40,
        "8core_8gb": 80,
        "12core_12gb": 120,
        "16core_16gb": 160
    }

    if option not in options:
        return await interaction.response.send_message("Chọn 1 trong: 2core_2gb, 4core_4gb, 8core_8gb, 12core_12gb, 16core_16gb", ephemeral=True)

    db = load_db()
    user = db.setdefault(uid, {})
    owned = user.setdefault("owned_configs", [])
    if option in owned:
        return await interaction.response.send_message("Mày mua rồi còn mua nữa à?", ephemeral=True)

    if user.get("credit", 0) < options[option]:
        return await interaction.response.send_message("Không đủ coin. Mày nghèo bỏ mẹ.", ephemeral=True)

    user["credit"] -= options[option]
    owned.append(option)
    save_db(db)
    await interaction.response.send_message(f"Mua thành công `{option}`. Dùng `/setcauhinh` để chọn.")

@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua để deploy")
@app_commands.describe(option="Cấu hình muốn set")
async def setcauhinh(interaction: discord.Interaction, option: str):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.get(uid, {})
    if option not in user.get("owned_configs", []):
        return await interaction.response.send_message("Mày chưa mua cấu hình này. Đừng xạo chó.", ephemeral=True)

    user["vps_config"] = option
    save_db(db)
    await interaction.response.send_message(f"Đã chọn cấu hình `{option}`. Dùng `/deploy` để triển.")

@tree.command(name="deploy", description="Deploy VPS tmate (yêu cầu cấu hình)")
async def deploy(interaction: discord.Interaction):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.get(uid, {})
    config = user.get("vps_config")
    if not config:
        return await interaction.response.send_message("Mày chưa chọn cấu hình. Dùng `/setcauhinh` đi rồi quay lại.", ephemeral=True)

    core = int(config.split("core_")[0])
    ram = int(config.split("_")[1].replace("gb", ""))
    sess_id = str(random.randint(10000, 99999))
    path = f"/tmp/{uid}_{sess_id}"
    os.makedirs(path, exist_ok=True)

    neofetch_path = os.path.join(path, "usr/bin/neofetch")
    os.makedirs(os.path.dirname(neofetch_path), exist_ok=True)
    with open(neofetch_path, "w") as f:
        f.write(f'''#!/bin/bash
echo "OS: ServerTipacvnOS"
echo "CPU: {core} vCore"
echo "Memory: {ram} GB"
echo "Shell: /bin/bash"
echo "Discord server: https://dsc.gg/servertipacvn"
''')
    os.chmod(neofetch_path, 0o755)

    tmate_sock = os.path.join(path, "tmate.sock")
    subprocess.run(
        f"tmate -S {tmate_sock} new-session -d && "
        f"tmate -S {tmate_sock} wait tmate-ready && "
        f"tmate -S {tmate_sock} display -p '#{{tmate_ssh}}' > {path}/ssh.txt",
        shell=True
    )

    with open(f"{path}/ssh.txt", "r") as f:
        ssh_link = f.read().strip()

    user["vps_expires"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    user["vps_path"] = path
    save_db(db)

    await interaction.user.send(f"**SSH của mày đây:**\n```{ssh_link}```\nDùng xong nhớ tắt, không tao xóa.")
    await interaction.response.send_message("Đã gửi SSH qua tin nhắn riêng, đồ giấu dốt.")

@tree.command(name="timevps", description="Kiểm tra thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.get(uid, {})
    exp = user.get("vps_expires")
    if not exp:
        return await interaction.response.send_message("Mày chưa deploy cái gì cả.")
    remaining = datetime.fromisoformat(exp) - datetime.utcnow()
    if remaining.total_seconds() <= 0:
        return await interaction.response.send_message("Hết hạn rồi còn hỏi. Deploy lại đi.")
    await interaction.response.send_message(f"VPS còn sống trong: {str(remaining).split('.')[0]}")

@tree.command(name="renew", description="Gia hạn VPS thêm 1 giờ với 10 coin")
async def renew(interaction: discord.Interaction):
    if not allowed_channel(interaction):
        return
    uid = str(interaction.user.id)
    db = load_db()
    user = db.setdefault(uid, {})
    if user.get("credit", 0) < 10:
        return await interaction.response.send_message("Không đủ coin để gia hạn. Nghèo thì out.", ephemeral=True)
    if "vps_expires" not in user:
        return await interaction.response.send_message("Mày chưa deploy cái gì để gia hạn hết.", ephemeral=True)
    user["credit"] -= 10
    user["vps_expires"] = (datetime.fromisoformat(user["vps_expires"]) + timedelta(hours=1)).isoformat()
    save_db(db)
    await interaction.response.send_message("Gia hạn thêm 1 tiếng. Cố mà dùng đi.")

@tasks.loop(minutes=1)
async def check_vps_expiry():
    db = load_db()
    now = datetime.utcnow()
    for uid, user in list(db.items()):
        exp = user.get("vps_expires")
        if exp and datetime.fromisoformat(exp) < now:
            path = user.get("vps_path")
            if path:
                subprocess.run(f"rm -rf {path}", shell=True)
            user.pop("vps_expires", None)
            user.pop("vps_path", None)
            user.pop("vps_config", None)
            try:
                u = await bot.fetch_user(int(uid))
                await u.send("Cái VPS mày hết hạn rồi, tao xóa rồi nhé.")
            except:
                pass
    save_db(db)

bot.run(TOKEN)
