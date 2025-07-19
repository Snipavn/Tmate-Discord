import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, subprocess, asyncio, datetime, random, json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104  # thay bằng ID của bạn
ALLOWED_CHANNEL_ID = 1378918272812060742  # chỉ cho chạy lệnh ở channel này

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

data = {}

def save_data():
    with open("credit.json", "w") as f:
        json.dump(data, f)

def load_data():
    global data
    if os.path.exists("credit.json"):
        with open("credit.json") as f:
            data = json.load(f)

load_data()

def get_user(user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"credit": 0, "session": None, "expires": None}
    return data[uid]

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã online dưới tên {bot.user}")

def is_owner(interaction):
    return interaction.user.id == OWNER_ID

def is_allowed_channel(interaction):
    return interaction.channel.id == ALLOWED_CHANNEL_ID

@tree.command(name="getcredit", description="Nhận 1 credit mỗi 12h")
async def getcredit(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    uid = str(interaction.user.id)
    user = get_user(uid)
    now = datetime.datetime.utcnow()
    last = user.get("last_credit")
    if last and (now - datetime.datetime.fromisoformat(last)).total_seconds() < 43200:
        await interaction.response.send_message("Mỗi 12 tiếng mới được xin thêm credit, đợi đi thằng ngu.")
        return
    user["credit"] += 1
    user["last_credit"] = now.isoformat()
    save_data()
    await interaction.response.send_message(f"Đã cộng 1 credit cho thằng {interaction.user.name}")

@tree.command(name="credit", description="Xem credit hiện tại")
async def credit(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    user = get_user(interaction.user.id)
    await interaction.response.send_message(f"Thằng {interaction.user.name} có {user['credit']} credit.")

@tree.command(name="givecredit", description="Tặng credit cho người khác (OWNER)")
@app_commands.describe(user="Người nhận", amount="Số credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_owner(interaction): return
    target = get_user(user.id)
    target["credit"] += amount
    save_data()
    await interaction.response.send_message(f"Đã cho {amount} credit thằng {user.name}")

@tree.command(name="xoacredit", description="Xoá credit thằng khác (OWNER)")
@app_commands.describe(user="Người bị xóa")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction): return
    target = get_user(user.id)
    target["credit"] = 0
    save_data()
    await interaction.response.send_message(f"Xoá sạch credit thằng {user.name} rồi.")

@tree.command(name="deploy", description="Tạo VPS Ubuntu bằng proot")
async def deploy(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    await interaction.response.defer()
    user = get_user(interaction.user.id)
    if user["credit"] < 10:
        await interaction.followup.send("Mày nghèo quá, cần 10 credit mới deploy được.")
        return
    uid = str(interaction.user.id)
    session_id = f"{uid}-{random.randint(1000,9999)}"
    folder = f"/tmp/proot-{session_id}"
    os.makedirs(folder, exist_ok=True)
    rootfs = f"{folder}/ubuntu22.tar.gz"
    if not os.path.exists(rootfs):
        subprocess.run(f"curl -L https://raw.githubusercontent.com/ni28pro/ubuntu/main/ubuntu22.tar.gz -o {rootfs}", shell=True)
        subprocess.run(f"cd {folder} && tar -xzf ubuntu22.tar.gz", shell=True)
    script = f"""
tmate -S {folder}/tmate.sock new-session -d &&
tmate -S {folder}/tmate.sock wait tmate-ready &&
tmate -S {folder}/tmate.sock display -p '#{{tmate_ssh}}'
"""
    result = subprocess.run(script, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ssh = result.stdout.strip()
    expires = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    user["credit"] -= 10
    user["session"] = session_id
    user["expires"] = expires.isoformat()
    save_data()
    try:
        await interaction.user.send(f"Đây là SSH của mày: `{ssh}`\nSession ID: `{session_id}`\nHạn dùng: `{expires}`")
    except:
        await interaction.followup.send(f"Không gửi được DM cho mày, check lại setting Discord.")
    await interaction.followup.send(f"Tao gửi SSH qua DM rồi, dùng lẹ lên!")

@tree.command(name="stopvps", description="Dừng VPS của mày")
async def stopvps(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    user = get_user(interaction.user.id)
    if not user.get("session"):
        await interaction.response.send_message("Mày chưa deploy cái gì cả.")
        return
    folder = f"/tmp/proot-{user['session']}"
    subprocess.run(f"rm -rf {folder}", shell=True)
    user["session"] = None
    user["expires"] = None
    save_data()
    await interaction.response.send_message("Đã xoá mẹ VPS của mày rồi.")

@tree.command(name="renew", description="Gia hạn VPS 1 ngày = 10 credit")
async def renew(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    user = get_user(interaction.user.id)
    if not user.get("session"):
        await interaction.response.send_message("Mày có VPS đâu mà gia hạn con đần.")
        return
    if user["credit"] < 10:
        await interaction.response.send_message("Không đủ 10 credit để gia hạn, kiếm thêm đi thg nghèo.")
        return
    expires = datetime.datetime.fromisoformat(user["expires"]) + datetime.timedelta(days=1)
    user["credit"] -= 10
    user["expires"] = expires.isoformat()
    save_data()
    await interaction.response.send_message(f"Đã gia hạn, dùng tới {expires} luôn đi.")

@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    if not is_allowed_channel(interaction): return
    user = get_user(interaction.user.id)
    if not user.get("expires"):
        await interaction.response.send_message("Mày chưa deploy cái gì cả.")
        return
    now = datetime.datetime.utcnow()
    expire = datetime.datetime.fromisoformat(user["expires"])
    remain = expire - now
    if remain.total_seconds() <= 0:
        await interaction.response.send_message("Hết hạn mẹ rồi, đi renew lẹ đi.")
    else:
        await interaction.response.send_message(f"VPS còn sống thêm {remain}.")

@tasks.loop(minutes=5)
async def auto_delete_expired():
    for uid, info in data.items():
        if info.get("expires"):
            exp = datetime.datetime.fromisoformat(info["expires"])
            if datetime.datetime.utcnow() > exp:
                folder = f"/tmp/proot-{info['session']}"
                subprocess.run(f"rm -rf {folder}", shell=True)
                info["session"] = None
                info["expires"] = None
    save_data()

auto_delete_expired.start()
bot.run(TOKEN)
