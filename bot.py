import discord
from discord.ext import commands
from discord import app_commands
import os, subprocess, asyncio, time, json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_data = {}
if os.path.exists("data.json"):
    with open("data.json", "r") as f:
        user_data = json.load(f)

def save_data():
    with open("data.json", "w") as f:
        json.dump(user_data, f)

def get_user(uid):
    if str(uid) not in user_data:
        user_data[str(uid)] = {
            "credit": 0,
            "vps": None,
            "time": 0,
            "cauhinh": None,
            "owned": []
        }
    return user_data[str(uid)]

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot is ready as {bot.user}")

@tree.command(name="getcredit", description="Nhận 1 credit mỗi 12 giờ")
async def getcredit(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    now = time.time()
    if now - user["credit"] < 43200:
        await interaction.response.send_message("Bạn đã nhận credit trong 12 giờ qua!", ephemeral=True)
        return
    user["credit"] = now
    user["cuoc"] = user.get("cuoc", 0) + 1
    save_data()
    await interaction.response.send_message("Đã nhận 1 credit!", ephemeral=True)

@tree.command(name="credit", description="Xem số credit bạn đang có")
async def credit(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    await interaction.response.send_message(f"Bạn có {user.get('cuoc', 0)} credit.", ephemeral=True)

@tree.command(name="givecredit", description="(Owner) Tặng credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bạn không có quyền.", ephemeral=True)
        return
    u = get_user(user.id)
    u["cuoc"] = u.get("cuoc", 0) + amount
    save_data()
    await interaction.response.send_message(f"Đã cộng {amount} credit cho {user.name}.")

@tree.command(name="xoacredit", description="(Owner) Xoá credit")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bạn không có quyền.", ephemeral=True)
        return
    u = get_user(user.id)
    u["cuoc"] = 0
    save_data()
    await interaction.response.send_message(f"Đã xoá credit của {user.name}.")

@tree.command(name="cuoccredit", description="Xem lịch sử nhận credit")
async def cuoccredit(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    await interaction.response.send_message(f"Bạn đã nhận tổng {user.get('cuoc', 0)} credit.", ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS")
@app_commands.choices(option=[
    app_commands.Choice(name="2GB - 2core", value="2-2"),
    app_commands.Choice(name="4GB - 4core", value="4-4"),
    app_commands.Choice(name="8GB - 8core", value="8-8"),
    app_commands.Choice(name="12GB - 12core", value="12-12"),
    app_commands.Choice(name="16GB - 16core", value="16-16"),
])
async def shopping(interaction: discord.Interaction, option: app_commands.Choice[str]):
    user = get_user(interaction.user.id)
    prices = {
        "2-2": 20, "4-4": 40, "8-8": 80, "12-12": 120, "16-16": 160
    }
    if option.value in user["owned"]:
        await interaction.response.send_message("Bạn đã mua cấu hình này rồi.", ephemeral=True)
        return
    if user["cuoc"] < prices[option.value]:
        await interaction.response.send_message("Bạn không đủ credit.", ephemeral=True)
        return
    user["cuoc"] -= prices[option.value]
    user["owned"].append(option.value)
    save_data()
    await interaction.response.send_message(f"Đã mua cấu hình {option.name}.", ephemeral=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình VPS đã mua")
@app_commands.choices(option=[
    app_commands.Choice(name="2GB - 2core", value="2-2"),
    app_commands.Choice(name="4GB - 4core", value="4-4"),
    app_commands.Choice(name="8GB - 8core", value="8-8"),
    app_commands.Choice(name="12GB - 12core", value="12-12"),
    app_commands.Choice(name="16GB - 16core", value="16-16"),
])
async def setcauhinh(interaction: discord.Interaction, option: app_commands.Choice[str]):
    user = get_user(interaction.user.id)
    if option.value not in user["owned"]:
        await interaction.response.send_message("Bạn chưa mua cấu hình này.", ephemeral=True)
        return
    user["cauhinh"] = option.value
    save_data()
    await interaction.response.send_message(f"Đã set cấu hình: {option.name}", ephemeral=True)

@tree.command(name="deploy", description="Tạo VPS Ubuntu proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Không được dùng lệnh ở đây!", ephemeral=True)
        return
    user = get_user(interaction.user.id)
    if user["vps"]:
        await interaction.response.send_message("Bạn đã có VPS đang chạy!", ephemeral=True)
        return
    if not user.get("cauhinh"):
        await interaction.response.send_message("Bạn chưa set cấu hình VPS!", ephemeral=True)
        return
    uid = str(interaction.user.id)
    folder = f"vps_{uid}"
    os.makedirs(folder, exist_ok=True)
    rootfs = "ubuntu.tar.gz"
    if not os.path.exists(rootfs):
        await interaction.response.send_message("Đang tải Ubuntu...", ephemeral=True)
        subprocess.run(["wget", "https://partner-images.canonical.com/core/jammy/current/ubuntu-jammy-core-cloudimg-amd64-root.tar.gz", "-O", rootfs])
    subprocess.run(["proot", "-0", "-r", folder, "tar", "-xzf", rootfs, "-C", folder])
    script = f"""/bin/bash -c "apt update && apt install -y tmate && tmate -S /tmp/tmate.sock new-session -d && tmate -S /tmp/tmate.sock wait tmate-ready && tmate -S /tmp/tmate.sock display -p '#{{tmate_ssh}}' > /tmp/{uid}.ssh && sleep 3600" """
    subprocess.Popen(f"proot -0 -r {folder} -b /dev/ -b /proc/ -b /sys/ -w /root {script}", shell=True)
    user["vps"] = time.time()
    user["time"] = 3600
    save_data()
    await interaction.response.send_message("Đang khởi động VPS...", ephemeral=True)
    await asyncio.sleep(10)
    with open(f"/tmp/{uid}.ssh") as f:
        ssh = f.read()
    await interaction.user.send(f"🔗 VPS SSH của bạn: `{ssh}`")

@tree.command(name="stopvps", description="Tắt VPS của bạn")
async def stopvps(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user["vps"]:
        await interaction.response.send_message("Bạn chưa có VPS!", ephemeral=True)
        return
    uid = str(interaction.user.id)
    folder = f"vps_{uid}"
    subprocess.run(["rm", "-rf", folder])
    user["vps"] = None
    user["time"] = 0
    save_data()
    await interaction.response.send_message("Đã tắt VPS của bạn.", ephemeral=True)

@tree.command(name="renew", description="Gia hạn VPS thêm 1 giờ với 10 credit")
async def renew(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user["vps"]:
        await interaction.response.send_message("Bạn chưa có VPS!", ephemeral=True)
        return
    if user["cuoc"] < 10:
        await interaction.response.send_message("Bạn không đủ credit!", ephemeral=True)
        return
    user["cuoc"] -= 10
    user["time"] += 3600
    save_data()
    await interaction.response.send_message("Đã gia hạn VPS thêm 1 giờ.", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian VPS còn lại")
async def timevps(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user["vps"]:
        await interaction.response.send_message("Bạn chưa có VPS!", ephemeral=True)
        return
    left = int(user["vps"] + user["time"] - time.time())
    await interaction.response.send_message(f"⏳ VPS còn lại: {left//60} phút {left%60} giây.", ephemeral=True)

bot.run(TOKEN)
