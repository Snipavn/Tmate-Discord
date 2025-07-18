import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess
import os
import json
import asyncio
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

load_dotenv()
TOKEN= os.getenv("TOKEN")
OWNER_ID = 882844895902040104  # thay bằng ID của bạn
ALLOWED_CHANNEL_ID = 1378918272812060742  # thay bằng ID kênh cho phép dùng lệnh
SESSION_FILE = "tmate_sessions.json"
CREDIT_FILE = "user_credits.json"
CONFIG_FILE = "user_configs.json"

CONFIG_COSTS = {
    "2core_2gb": 20,
    "4core_4gb": 40,
    "8core_8gb": 80,
    "12core_12gb": 120,
    "16core_16gb": 160,
}


def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


tmate_sessions = load_json(SESSION_FILE)
user_credits = load_json(CREDIT_FILE)
user_configs = load_json(CONFIG_FILE)


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")
    await tree.sync()
    check_vps_expiry.start()


async def run_tmate(user_id):
    session_id = str(random.randint(10000, 99999))
    folder = f"/tmp/tmate_{user_id}"
    sock = f"{folder}/tmate.sock"

    os.makedirs(folder, exist_ok=True)

    process = await asyncio.create_subprocess_shell(
        f"tmate -S {sock} new-session -d && tmate -S {sock} wait tmate-ready && tmate -S {sock} display -p '#{{tmate_ssh}}'",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        ssh = stdout.decode().strip()
        expire_time = (datetime.utcnow() + timedelta(days=1)).isoformat()
        tmate_sessions[str(user_id)] = {
            "ssh": ssh,
            "sock": sock,
            "expire": expire_time,
            "session_id": session_id,
        }
        save_json(SESSION_FILE, tmate_sessions)
        return ssh, session_id
    return None, None


@tree.command(name="deploy", description="Triệu hồi VPS tạm thời (1 ngày)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Cút về đúng chỗ mày dùng lệnh!", ephemeral=True)

    user_id = str(interaction.user.id)

    if user_id not in user_configs:
        return await interaction.response.send_message("Mày chưa chọn cấu hình nào cả! /setcauhinh trước đi đã.", ephemeral=True)

    if user_credits.get(user_id, 0) < 10:
        return await interaction.response.send_message("Mày nghèo quá không đủ 10 coin mua vps!", ephemeral=True)

    if user_id in tmate_sessions:
        return await interaction.response.send_message("Mày đã có con VPS rồi đấy, đừng spam nữa!", ephemeral=True)

    ssh, session_id = await run_tmate(user_id)

    if ssh:
        user_credits[user_id] -= 10
        save_json(CREDIT_FILE, user_credits)
        await interaction.user.send(f"Đây là vps của mày nè:\n{ssh}\nSession ID: `{session_id}` (dùng để /renew hoặc /stopvps)")
        await interaction.response.send_message("Tao gửi vps cho mày trong tin nhắn riêng rồi đó! 😈", ephemeral=True)
    else:
        await interaction.response.send_message("Lỗi mẹ gì rồi, không tạo được vps cho mày!", ephemeral=True)


@tree.command(name="credit", description="Kiểm tra credit của mày")
async def credit(interaction: discord.Interaction):
    c = user_credits.get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"Mày còn {c} credit đó đồ gà.")


@tree.command(name="getcredit", description="Nhận credit mỗi 12 tiếng")
async def getcredit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = datetime.utcnow()

    if "last_claim" not in user_credits.get(user_id, {}):
        user_credits[user_id] = {"last_claim": now.isoformat(), "credit": 1}
    else:
        last = datetime.fromisoformat(user_credits[user_id]["last_claim"])
        if now - last < timedelta(hours=12):
            return await interaction.response.send_message("Tham vừa thôi! Đợi đủ 12 tiếng đi thằng ngu.", ephemeral=True)
        user_credits[user_id]["last_claim"] = now.isoformat()
        user_credits[user_id]["credit"] += 1

    save_json(CREDIT_FILE, user_credits)
    await interaction.response.send_message("Cho mày 1 credit nữa đó, giữ mà sống.")


@tree.command(name="stopvps", description="Dẹp con VPS của mày")
@app_commands.describe(session_id="Session ID lúc được gửi tin nhắn")
async def stopvps(interaction: discord.Interaction, session_id: str):
    user_id = str(interaction.user.id)
    session = tmate_sessions.get(user_id)

    if session and session.get("session_id") == session_id:
        try:
            os.remove(session["sock"])
            folder = os.path.dirname(session["sock"])
            if os.path.exists(folder):
                os.rmdir(folder)
        except:
            pass

        del tmate_sessions[user_id]
        save_json(SESSION_FILE, tmate_sessions)
        await interaction.response.send_message("Dẹp rồi đó thằng đần.")
    else:
        await interaction.response.send_message("Không tìm thấy VPS nào với Session ID mày đưa!", ephemeral=True)


@tree.command(name="renew", description="Gia hạn VPS (5 coin)")
@app_commands.describe(session_id="Session ID của mày")
async def renew(interaction: discord.Interaction, session_id: str):
    user_id = str(interaction.user.id)
    if user_credits.get(user_id, 0) < 5:
        return await interaction.response.send_message("Nghèo rớt mồng tơi, đủ 5 coin chưa mà đòi renew?", ephemeral=True)

    session = tmate_sessions.get(user_id)
    if session and session.get("session_id") == session_id:
        expire_time = datetime.fromisoformat(session["expire"]) + timedelta(days=1)
        session["expire"] = expire_time.isoformat()
        user_credits[user_id] -= 5
        save_json(SESSION_FILE, tmate_sessions)
        save_json(CREDIT_FILE, user_credits)
        await interaction.response.send_message("Tao gia hạn thêm 1 ngày cho mày rồi đấy.")
    else:
        await interaction.response.send_message("Không tìm thấy session mày muốn renew!", ephemeral=True)


@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    session = tmate_sessions.get(user_id)

    if not session:
        return await interaction.response.send_message("Mày làm gì có con VPS nào đang chạy?", ephemeral=True)

    expire = datetime.fromisoformat(session["expire"])
    left = expire - datetime.utcnow()
    await interaction.response.send_message(f"VPS của mày còn sống thêm {left.total_seconds() // 3600:.0f} giờ nữa.")


@tree.command(name="givecredit", description="Cho coin thằng khác (Admin only)")
@app_commands.describe(user="Thằng gà muốn cho", amount="Số coin")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Cút! Lệnh này chỉ dành cho bố mày!", ephemeral=True)

    uid = str(user.id)
    user_credits[uid] = user_credits.get(uid, 0) + amount
    save_json(CREDIT_FILE, user_credits)
    await interaction.response.send_message(f"Đã cho {amount} coin cho {user.mention}.")


@tree.command(name="xoacredit", description="Xoá sạch coin thằng khác (Admin only)")
@app_commands.describe(user="Đứa bị xoá")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày nghĩ mày là ai mà đòi xài cái này?", ephemeral=True)

    uid = str(user.id)
    user_credits[uid] = 0
    save_json(CREDIT_FILE, user_credits)
    await interaction.response.send_message(f"Đã xoá sạch coin của {user.mention}.")


@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.describe(option="Cấu hình muốn mua")
async def shopping(interaction: discord.Interaction, option: str):
    user_id = str(interaction.user.id)
    if option not in CONFIG_COSTS:
        return await interaction.response.send_message("Cấu hình gà mày nhập sai mẹ rồi.", ephemeral=True)

    cost = CONFIG_COSTS[option]
    if user_credits.get(user_id, 0) < cost:
        return await interaction.response.send_message(f"Không đủ coin, cấu hình này cần {cost} coin.", ephemeral=True)

    user_credits[user_id] -= cost
    save_json(CREDIT_FILE, user_credits)
    user_configs.setdefault(user_id, {})[option] = True
    save_json(CONFIG_FILE, user_configs)
    await interaction.response.send_message(f"Đã mua cấu hình `{option}` cho mày rồi đó thằng ngu.")


@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua để dùng /deploy")
@app_commands.describe(option="Tên cấu hình")
async def setcauhinh(interaction: discord.Interaction, option: str):
    user_id = str(interaction.user.id)
    if option not in user_configs.get(user_id, {}):
        return await interaction.response.send_message("Cấu hình này mày chưa mua đâu, đừng láo.", ephemeral=True)

    user_configs[user_id]["selected"] = option
    save_json(CONFIG_FILE, user_configs)
    await interaction.response.send_message(f"Đã set cấu hình `{option}` cho mày deploy rồi đó.")


@tasks.loop(minutes=10)
async def check_vps_expiry():
    now = datetime.utcnow()
    expired = []

    for uid, session in tmate_sessions.items():
        if datetime.fromisoformat(session["expire"]) < now:
            expired.append(uid)

    for uid in expired:
        try:
            user = await bot.fetch_user(int(uid))
            await user.send("VPS của mày hết hạn rồi, đi mà tạo lại 😈")
        except:
            pass
        try:
            os.remove(tmate_sessions[uid]["sock"])
            os.rmdir(os.path.dirname(tmate_sessions[uid]["sock"]))
        except:
            pass
        del tmate_sessions[uid]

    if expired:
        save_json(SESSION_FILE, tmate_sessions)


bot.run("YOUR_TOKEN_HERE")
