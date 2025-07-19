import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, subprocess, time
from dotenv import load_dotenv

# Load token từ .env
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Cấu hình
OWNER_ID = 882844895902040104  # ID của mày
ALLOWED_CHANNEL_ID = 1378918272812060742  # ID channel bot cho phép hoạt động

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

CREDIT_FILE = "credits.json"
CONFIG_FILE = "user_configs.json"
FREE_CREDIT_INTERVAL = 12 * 3600
CONFIG_PRICES = {
    "2GB-2core": 20,
    "4GB-4core": 40,
    "8GB-8core": 80,
    "12GB-12core": 120,
    "16GB-16core": 160
}

# ===== File và credit =====
def read_json(path):
    if not os.path.exists(path): return {}
    with open(path, "r") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_credit(uid):
    return read_json(CREDIT_FILE).get(str(uid), {}).get("amount", 0)

def add_credit(uid, amount):
    data = read_json(CREDIT_FILE)
    uid = str(uid)
    if uid not in data: data[uid] = {"amount": 0, "last_claim": 0}
    data[uid]["amount"] += amount
    write_json(CREDIT_FILE, data)

def set_last_claim(uid, t):
    data = read_json(CREDIT_FILE)
    uid = str(uid)
    if uid not in data: data[uid] = {"amount": 0}
    data[uid]["last_claim"] = t
    write_json(CREDIT_FILE, data)

def get_last_claim(uid):
    return read_json(CREDIT_FILE).get(str(uid), {}).get("last_claim", 0)

# ===== VPS và cấu hình =====
def get_user_config(uid):
    return read_json(CONFIG_FILE).get(str(uid), {})

def set_user_config(uid, conf):
    data = read_json(CONFIG_FILE)
    data[str(uid)] = conf
    write_json(CONFIG_FILE, data)

def remove_user_config(uid):
    data = read_json(CONFIG_FILE)
    data.pop(str(uid), None)
    write_json(CONFIG_FILE, data)

def get_session_path(uid): return f"/tmp/vps_session_{uid}"

def get_ubuntu_script(uid):
    folder = get_session_path(uid)
    return f"""
rm -rf {folder} && \
mkdir -p {folder} && \
cd {folder} && \
apt update -y && apt install -y wget curl proot tar && \
wget https://raw.githubusercontent.com/proot-me/proot-static-build/master/static/proot -O proot && \
chmod +x proot && \
wget https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.4-base-amd64.tar.gz && \
mkdir rootfs && \
./proot -S rootfs tar -xzf ubuntu-base-22.04.4-base-amd64.tar.gz && \
tmate -S {folder}/tmate.sock new-session -d && \
tmate -S {folder}/tmate.sock wait tmate-ready && \
tmate -S {folder}/tmate.sock display -p 'SSH: #{{tmate_ssh}} | ID: #{{tmate_session_id}}'
"""

def run_bash(script):
    try:
        return subprocess.check_output(script, shell=True, text=True)
    except Exception as e:
        return f"Lỗi mẹ rồi: {e}"

# ===== Slash commands =====
@tree.command(name="deploy", description="Tạo VPS Ubuntu bằng proot + tmate")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Cút về đúng channel đồ ngu.", ephemeral=True)
    uid = interaction.user.id
    conf = get_user_config(uid)
    if "ram" not in conf or "cpu" not in conf:
        return await interaction.response.send_message("Chưa /setcauhinh mà đòi deploy? Đồ gà.", ephemeral=True)
    if os.path.exists(get_session_path(uid)):
        return await interaction.response.send_message("Mày deploy rồi còn bày đặt. Dùng /stopvps trước!", ephemeral=True)
    if get_credit(uid) < 10:
        return await interaction.response.send_message("Mày nghèo rớt, đủ 10 credit rồi quay lại.", ephemeral=True)

    add_credit(uid, -10)
    conf["expire"] = int(time.time()) + 86400
    set_user_config(uid, conf)

    await interaction.response.send_message("Đang khởi tạo VPS, ngồi im chờ...")

    ssh = run_bash(get_ubuntu_script(uid)).strip()
    await interaction.followup.send(f"VPS của mày nè:\n```{ssh}```")

@tree.command(name="stopvps", description="Xoá VPS hiện tại")
async def stopvps(interaction: discord.Interaction):
    uid = interaction.user.id
    folder = get_session_path(uid)
    subprocess.run(f"rm -rf {folder}", shell=True)
    remove_user_config(uid)
    await interaction.response.send_message("VPS của mày đã bị tiễn về trời!")

@tree.command(name="renew", description="Gia hạn VPS thêm 1 ngày (10 credit)")
async def renew(interaction: discord.Interaction):
    uid = interaction.user.id
    conf = get_user_config(uid)
    if not conf or "expire" not in conf:
        return await interaction.response.send_message("Mày có VPS đâu mà renew đồ hâm?", ephemeral=True)
    if get_credit(uid) < 10:
        return await interaction.response.send_message("Mày nghèo, đủ 10 credit rồi nói chuyện.", ephemeral=True)
    conf["expire"] += 86400
    set_user_config(uid, conf)
    add_credit(uid, -10)
    await interaction.response.send_message("Gia hạn xong, sống thêm 1 ngày nữa đi thg lười.")

@tree.command(name="getcredit", description="Nhận 1 credit / 12 tiếng")
async def getcredit(interaction: discord.Interaction):
    uid = interaction.user.id
    now = int(time.time())
    last = get_last_claim(uid)
    if now - last < FREE_CREDIT_INTERVAL:
        remain = (FREE_CREDIT_INTERVAL - (now - last)) // 60
        return await interaction.response.send_message(f"Còn {remain} phút nữa mới xin được nữa, đừng có lì.")
    add_credit(uid, 1)
    set_last_claim(uid, now)
    await interaction.response.send_message("Rồi đó, cho 1 credit. Lo mà xài.")

@tree.command(name="credit", description="Xem số credit của mày")
async def credit(interaction: discord.Interaction):
    c = get_credit(interaction.user.id)
    await interaction.response.send_message(f"Mày đang có {c} credit đó, biết xài chưa?")

@tree.command(name="givecredit", description="(ADMIN) Cho credit thằng khác")
@app_commands.describe(user="Thằng nhận", amount="Số credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày có phải chủ đâu mà bày đặt?", ephemeral=True)
    add_credit(user.id, amount)
    await interaction.response.send_message(f"Đã cho {amount} credit cho {user.mention}.")

@tree.command(name="xoacredit", description="(ADMIN) Xoá sạch credit của thằng khác")
@app_commands.describe(user="Thằng bị xóa")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Cấm xía vô chuyện admin!", ephemeral=True)
    add_credit(user.id, -get_credit(user.id))
    await interaction.response.send_message(f"{user.mention} đã bị nghèo trắng tay.")

@tree.command(name="cuoccredit", description="Xem top thằng giàu nhất")
async def cuoccredit(interaction: discord.Interaction):
    data = read_json(CREDIT_FILE)
    top = sorted(data.items(), key=lambda x: x[1].get("amount", 0), reverse=True)
    msg = "\n".join([f"<@{uid}>: {info['amount']} credit" for uid, info in top[:10]])
    await interaction.response.send_message("Top thằng giàu:\n" + msg)

@tree.command(name="shopping", description="Mua cấu hình VPS (RAM-CPU)")
@app_commands.describe(option="Chọn cấu hình muốn mua")
@app_commands.choices(option=[app_commands.Choice(name=k, value=k) for k in CONFIG_PRICES])
async def shopping(interaction: discord.Interaction, option: app_commands.Choice[str]):
    uid = interaction.user.id
    price = CONFIG_PRICES[option.value]
    if get_credit(uid) < price:
        return await interaction.response.send_message(f"Mày nghèo, {option.value} cần {price} credit.")
    add_credit(uid, -price)
    conf = get_user_config(uid)
    conf.update({"ram": option.value.split("-")[0], "cpu": option.value.split("-")[1]})
    set_user_config(uid, conf)
    await interaction.response.send_message(f"Đã mua cấu hình {option.value}, nhớ /setcauhinh để dùng.")

@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua để chuẩn bị deploy")
@app_commands.describe(option="Cấu hình đã mua")
@app_commands.choices(option=[app_commands.Choice(name=k, value=k) for k in CONFIG_PRICES])
async def setcauhinh(interaction: discord.Interaction, option: app_commands.Choice[str]):
    conf = {"ram": option.value.split("-")[0], "cpu": option.value.split("-")[1]}
    set_user_config(interaction.user.id, conf)
    await interaction.response.send_message(f"Đã chọn cấu hình {option.value} cho mày.")

@tree.command(name="timevps", description="Xem thời gian VPS còn lại")
async def timevps(interaction: discord.Interaction):
    conf = get_user_config(interaction.user.id)
    if not conf or "expire" not in conf:
        return await interaction.response.send_message("Mày chưa deploy gì cả thg ngu.")
    remain = conf["expire"] - int(time.time())
    if remain <= 0:
        return await interaction.response.send_message("VPS mày hết hạn rồi. Xài /renew hoặc biến.")
    h, m = remain // 3600, (remain % 3600) // 60
    await interaction.response.send_message(f"Còn {h}h {m}m nữa rồi cút.")

# Xoá VPS hết hạn mỗi 5 phút
@tasks.loop(minutes=5)
async def cleanup_vps():
    now = int(time.time())
    data = read_json(CONFIG_FILE)
    for uid, conf in list(data.items()):
        if "expire" in conf and conf["expire"] < now:
            subprocess.run(f"rm -rf {get_session_path(uid)}", shell=True)
            remove_user_config(uid)

@bot.event
async def on_ready():
    await tree.sync()
    cleanup_vps.start()
    print(f"Bot đã online dưới tên: {bot.user}")

bot.run(TOKEN)
