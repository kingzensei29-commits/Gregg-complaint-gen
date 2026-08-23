import os
import random
import smtplib
from email.message import EmailMessage
import asyncio
import threading
import json
import requests
from flask import Flask
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Flask Tiny Web Server ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🍗 Tiered Grievance Bot is online and operational!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
AUTH_EMAIL = os.getenv("SENDER_EMAIL")     
AUTH_PASSWORD = os.getenv("EMAIL_PASSWORD") 

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

ECONOMY_FILE = "user_economy.json"

def load_economy():
    if os.path.exists(ECONOMY_FILE):
        try:
            with open(ECONOMY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_economy(data):
    try:
        with open(ECONOMY_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save economy state: {e}")

def add_user_balance(user_id, amount):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["balance"] += float(amount)
    save_economy(data)
    return data[uid]["balance"]

def add_user_voucher(user_id, username, brand_name, value):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    
    clean_name = "".join(filter(str.isalnum, username)).upper()[:4]
    if not clean_name:
        clean_name = "USER"
    rand_suffix = random.randint(1000, 9999)
    prefix = brand_name[:4].upper()
    voucher_code = f"{prefix}-{clean_name}-{rand_suffix}"

    data[uid]["vouchers"].append({
        "code": voucher_code,
        "name": f"{brand_name} Compensation Voucher",
        "value": value
    })
    save_economy(data)

# --- EXACT ROLE ID HIERARCHY MAPPING ---
ROLE_IDS = {
    "privates": 1541128316164251788,
    "exclusive": 1541127113803829278,
    "vips": 1541128193547698177,
    "og": 1541122329814368336,
    "members": 1541122505899774113
}

# --- COMPANY DATABASE WITH TIER RESTRICTIONS ---
BRANDS = {
    # --- PRIVATES EXCLUSIVE ---
    "mcdonalds": {"name": "McDonald's", "email": "customerservices@mcdonalds.co.uk", "color": 0xFFC72C, "min_tier": "privates", "items": ["Big Mac Meal", "McSpicy Meal"], "towns": ["London", "Birmingham"]},
    
    # --- EXCLUSIVE TIER ---
    "dixy": {"name": "Dixy Chicken", "email": "support@dixychicken.com", "color": 0xFFD700, "min_tier": "exclusive", "items": ["Peri Peri Burger", "Mighty Bucket"], "towns": ["Birmingham", "Leicester"]},
    
    # --- VIPS TIER ---
    "burgerking": {"name": "Burger King", "email": "consumer@burgerking.co.uk", "color": 0x502314, "min_tier": "vips", "items": ["Whopper Meal", "Chicken Royale"], "towns": ["London", "Edinburgh"]},
    "dominos": {"name": "Domino's Pizza", "email": "services@dominos.co.uk", "color": 0x006491, "min_tier": "vips", "items": ["Pepperoni Passion", "Garlic Bread"], "towns": ["Coventry", "Cardiff"]},

    # --- OGS TIER ---
    "kfc": {"name": "KFC", "email": "care@kfc.co.uk", "color": 0xF42A41, "min_tier": "og", "items": ["Boneless Banquet", "Zinger Tower"], "towns": ["London", "Cardiff"]},
    
    # --- MEMBERS TIER (Base Access) ---
    "greg": {"name": "Greggs", "email": "getintouch@greggs.co.uk", "color": 0xF26522, "min_tier": "members", "items": ["Steak Bake", "Vegan Sausage Roll"], "towns": ["Newcastle", "London"]},
    "asda": {"name": "Asda", "email": "help@asda.co.uk", "color": 0x78BE20, "min_tier": "members", "items": ["Ready Meal", "Sourdough Pizza"], "towns": ["Leeds", "Manchester"]},
    "subway": {"name": "Subway", "email": "support@subway.com", "color": 0x00843D, "min_tier": "members", "items": ["Italian B.M.T.", "Meatball Marinara"], "towns": ["Sheffield", "Bristol"]}
}

ANGRY_OPENINGS = [
    "To say I am absolutely fuming is an understatement. I demand an immediate explanation.",
    "I am writing this email while still shaking with absolute rage over what I experienced today.",
    "This is completely unacceptable. Your standards have dropped off a cliff and I want answers."
]

ANGRY_CLOSINGS = [
    "I expect a full refund and substantial compensation vouchers sent to my email immediately.",
    "Sort your operations out before someone gets ill. Expecting prompt compensation."
]

SIGN_OFFS = ["Furious regards,", "Disgusted,", "Extremely unsatisfied,"]

class SafeTempMail:
    def __init__(self, forced_name=None):
        clean_domains = ["gmail-inbox.com", "mail-box.net", "verify-user.com", "1secmail.org"]
        if forced_name:
            parts = forced_name.lower().split()
            if len(parts) >= 2:
                self.username = f"{parts[0]}.{parts[1]}{random.randint(10, 99)}"
            else:
                self.username = f"{parts[0]}{random.randint(100, 999)}"
        else:
            self.username = f"user.{random.randint(1000, 9999)}"
        self.domain = random.choice(clean_domains)
        self.address = f"{self.username}@{self.domain}"

    def check_inbox(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={self.username}&domain={self.domain}"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                messages = resp.json()
                if messages and len(messages) > 0:
                    msg_id = messages[0]['id']
                    detail_url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={self.username}&domain={self.domain}&id={msg_id}"
                    detail_resp = requests.get(detail_url, headers=headers, timeout=5)
                    if detail_resp.status_code == 200:
                        data = detail_resp.json()
                        class DummyMsg:
                            subject = data.get('subject', 'No Subject')
                            from_addr = data.get('from', 'Unknown')
                            body = data.get('textBody', data.get('body', ''))
                        return DummyMsg()
        except Exception:
            pass
        return None

def generate_angry_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    item = random.choice(b_data["items"])
    street = "High Street"
    
    opening = random.choice(ANGRY_OPENINGS)
    closing = random.choice(ANGRY_CLOSINGS)
    signoff = random.choice(SIGN_OFFS)
    consistent_name = fake.name()
    
    email_body = (
        f"{opening}\n\n"
        f"Complainant Details: {consistent_name}\n"
        f"Branch Location: {b_data['name']}, {street}, {town}\n\n"
        f"I ordered a {item} at your {town} branch and it was completely spoiled and cold. Unacceptable service.\n\n"
        f"{closing}\n\n"
        f"{signoff}\n{consistent_name}"
    )
    return email_body, consistent_name, town, street, item

def create_email_image(sender, recipient, subject, body, brand_color="#F26522", output_path="sent_complaint.png"):
    width, height = 800, 520
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 13)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill=brand_color)
    draw.text((20, 20), "📤 Official Verified Grievance Dispatched", fill="white", font=font_title)
    content_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 65 + f"\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 30:
            break
        draw.text((20, y_text), line, fill="#333333", font=font_body)
        y_text += 18
    image.save(output_path)
    return output_path

async def watch_burner_inbox(ctx, user_id, username, brand_key, temp_email, status_message, burner_address):
    elapsed = 0
    max_wait = 86400 
    b_name = BRANDS[brand_key]["name"]

    while elapsed < max_wait:
        await asyncio.sleep(300)
        elapsed += 300
        incoming_msg = temp_email.check_inbox()
        if incoming_msg:
            reward = round(random.uniform(5.00, 15.00), 2)
            add_user_balance(user_id, reward)
            add_user_voucher(user_id, username, b_name, reward)
            await status_message.channel.send(f"🚨 **{b_name} Support resolved ticket for <@{user_id}>! £{reward:.2f} credited!** Type `!redeem`")
            return

    fallback = 10.00
    add_user_balance(user_id, fallback)
    add_user_voucher(user_id, username, b_name, fallback)
    await status_message.channel.send(f"⏰ **Ticket Expired:** {b_name} bonus `£{fallback:.2f}` credited to <@{user_id}>.")

def has_user_access(user_roles, required_tier):
    role_ids_list = [r.id for r in user_roles]
    
    # Privilege Hierarchy Mapping
    user_has_privates = ROLE_IDS["privates"] in role_ids_list
    user_has_exclusive = ROLE_IDS["exclusive"] in role_ids_list
    user_has_vips = ROLE_IDS["vips"] in role_ids_list
    user_has_og = ROLE_IDS["og"] in role_ids_list
    user_has_members = ROLE_IDS["members"] in role_ids_list

    if required_tier == "privates":
        return user_has_privates
    elif required_tier == "exclusive":
        return user_has_privates or user_has_exclusive
    elif required_tier == "vips":
        return user_has_privates or user_has_exclusive or user_has_vips
    elif required_tier == "og":
        return user_has_privates or user_has_exclusive or user_has_vips or user_has_og
    elif required_tier == "members":
        return True # All members and above have baseline access
    return False

@bot.command(name="gen")
async def universal_gen(ctx, brand_key: str = None):
    """Universal generation command enforcing your exact role hierarchy."""
    if not brand_key:
        await ctx.send("⚠️ Usage: `!gen [company]`\nType `!brands` to view the accessible company directory.")
        return

    brand_key = brand_key.lower()
    if brand_key not in BRANDS:
        await ctx.send(f"❌ Company key `{brand_key}` not found. Type `!brands` for valid codes.")
        return

    b_data = BRANDS[brand_key]
    required_tier = b_data.get("min_tier", "members")

    # Check hierarchy access permissions
    if not has_user_access(ctx.author.roles, required_tier) and not ctx.author.guild_permissions.administrator:
        await ctx.send(f"⛔ {ctx.author.mention}, you lack the required role tier to generate complaints for **{b_data['name']}** (Requires `{required_tier.upper()}` access).", delete_after=10)
        return

    email_body, complaint_name, town, street, item = generate_angry_complaint(brand_key)
    temp_email = SafeTempMail(forced_name=complaint_name)
    burner_address = temp_email.address
    subject_line = f"Formal Complaint regarding service at {town} branch"

    sent_img_path = create_email_image(burner_address, b_data["email"], subject_line, email_body, brand_color=b_data["color"])
    sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

    await ctx.send(f"🔥 **{b_data['name']}**: Ticket dispatched via `{burner_address}`", file=sent_file)

    try:
        msg = EmailMessage()
        msg.set_subject(subject_line)
        msg["From"] = burner_address 
        msg["To"] = b_data["email"]
        msg["Reply-To"] = burner_address 
        msg.set_content(email_body)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(AUTH_EMAIL, AUTH_PASSWORD)
            server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[b_data["email"]])
    except Exception as e:
        await ctx.send(f"❌ Failed to dispatch email: {e}")
        return

    status_message = await ctx.send(f"⏳ Monitoring response inbox for `{burner_address}`...")
    bot.loop.create_task(watch_burner_inbox(ctx, ctx.author.id, ctx.author.name, brand_key, temp_email, status_message, burner_address))

@bot.command(name="brands")
async def list_brands(ctx):
    priv_list = [k for k, v in BRANDS.items() if v.get("min_tier") == "privates"]
    exc_list = [k for k, v in BRANDS.items() if v.get("min_tier") == "exclusive"]
    vip_list = [k for k, v in BRANDS.items() if v.get("min_tier") == "vips"]
    og_list = [k for k, v in BRANDS.items() if v.get("min_tier") == "og"]
    mem_list = [k for k, v in BRANDS.items() if v.get("min_tier") == "members"]
    
    embed = discord.Embed(title="📋 Server Role Tier Directory", color=0x3498DB)
    embed.add_field(name="👑 Privates Tier (`!gen`)", value=", ".join([f"`{c}`" for c in priv_list]) or "None", inline=False)
    embed.add_field(name="⭐ Exclusive Tier (`!gen`)", value=", ".join([f"`{c}`" for c in exc_list]) or "None", inline=False)
    embed.add_field(name="⚡ VIPs Tier (`!gen`)", value=", ".join([f"`{c}`" for c in vip_list]) or "None", inline=False)
    embed.add_field(name="🔥 OGs Tier (`!gen`)", value=", ".join([f"`{c}`" for c in og_list]) or "None", inline=False)
    embed.add_field(name="👤 Members Tier (`!gen`)", value=", ".join([f"`{c}`" for c in mem_list]) or "None", inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
