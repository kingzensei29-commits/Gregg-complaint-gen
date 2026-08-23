import os
import random
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
    return "🍗 Massive UK Grievance Bot is online and operational!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

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

# --- EXPANDED UK COMPANY DIRECTORY ---
BRANDS = {
    # --- PRIVATES TIER ---
    "mcdonalds": {"name": "McDonald's", "email": "customerservices@mcdonalds.co.uk", "color": 0xFFC72C, "min_tier": "privates", "items": ["Big Mac Meal", "McSpicy Meal", "Quarter Pounder"], "towns": ["London", "Manchester", "Birmingham"]},
    "apple": {"name": "Apple UK", "email": "contactus.uk@apple.com", "color": 0xA2AAAD, "min_tier": "privates", "items": ["iPhone Screen Repair", "AirPods Pro", "MacBook Charger"], "towns": ["London", "Glasgow", "Cardiff"]},
    "currys": {"name": "Currys", "email": "customer.relations@currys.co.uk", "color": 0x0000FF, "min_tier": "privates", "items": ["OLED TV", "Gaming Laptop", "Coffee Machine"], "towns": ["Leeds", "Bristol", "Sheffield"]},
    "samsung": {"name": "Samsung UK", "email": "support.uk@samsung.com", "color": 0x1428A0, "min_tier": "privates", "items": ["Galaxy Smartphone", "Soundbar", "Monitor"], "towns": ["London", "Manchester", "Edinburgh"]},
    "nike": {"name": "Nike UK", "email": "help.uk@nike.com", "color": 0x111111, "min_tier": "privates", "items": ["Air Force 1", "Tech Fleece Tracksuit", "Air Max"], "towns": ["London", "Liverpool", "Newcastle"]},

    # --- EXCLUSIVE TIER ---
    "dixy": {"name": "Dixy Chicken", "email": "support@dixychicken.com", "color": 0xFFD700, "min_tier": "exclusive", "items": ["Peri Peri Burger", "Mighty Bucket"], "towns": ["Birmingham", "Leicester", "Bradford"]},
    "argos": {"name": "Argos", "email": "orderenquiries@argos.co.uk", "color": 0xE60012, "min_tier": "exclusive", "items": ["Dyson Airwrap", "Nintendo Switch", "PlayStation Controller"], "towns": ["London", "Manchester", "Birmingham"]},
    "primark": {"name": "Primark", "email": "customercare@primark.ie", "color": 0x00A3E0, "min_tier": "exclusive", "items": ["Winter Coat", "Pyjamas Set", "Bedding Bundle"], "towns": ["Birmingham", "Manchester", "London"]},
    "jd": {"name": "JD Sports", "email": "customercare@jdsports.co.uk", "color": 0x000000, "min_tier": "exclusive", "items": ["Tracksuit", "Running Trainers", "Hoodie"], "towns": ["Liverpool", "Manchester", "Glasgow"]},
    "zara": {"name": "Zara UK", "email": "contact.uk@zara.com", "color": 0x222222, "min_tier": "exclusive", "items": ["Wool Overcoat", "Denim Jeans", "Leather Boots"], "towns": ["London", "Edinburgh", "Brighton"]},

    # --- VIPS TIER ---
    "burgerking": {"name": "Burger King", "email": "consumer@burgerking.co.uk", "color": 0x502314, "min_tier": "vips", "items": ["Whopper Meal", "Chicken Royale"], "towns": ["London", "Edinburgh", "Belfast"]},
    "dominos": {"name": "Domino's Pizza", "email": "services@dominos.co.uk", "color": 0x006491, "min_tier": "vips", "items": ["Pepperoni Passion", "Garlic Pizza Bread"], "towns": ["Coventry", "Cardiff", "Hull"]},
    "boots": {"name": "Boots", "email": "boots.customercare@boots.co.uk", "color": 0x001489, "min_tier": "vips", "items": ["Skincare Bundle", "Electric Toothbrush", "Perfume"], "towns": ["Nottingham", "London", "Bristol"]},
    "next": {"name": "Next", "email": "complaints@next.co.uk", "color": 0x990000, "min_tier": "vips", "items": ["Living Room Rug", "Curtains", "Designer Jeans"], "towns": ["Leicester", "Sheffield", "Cardiff"]},
    "asos": {"name": "ASOS", "email": "support@asos.com", "color": 0x222222, "min_tier": "vips", "items": ["Party Dress", "Designer Jacket", "Sneakers"], "towns": ["London", "Manchester", "Leeds"]},

    # --- OGS TIER ---
    "kfc": {"name": "KFC", "email": "care@kfc.co.uk", "color": 0xF42A41, "min_tier": "og", "items": ["Boneless Banquet", "Zinger Tower"], "towns": ["London", "Cardiff", "Liverpool"]},
    "tesco": {"name": "Tesco", "email": "customer.service@tesco.com", "color": 0x00539F, "min_tier": "og", "items": ["Finest Ready Meal", "Grocery Order", "Birthday Cake"], "towns": ["London", "Welwyn", "Manchester"]},
    "sainsburys": {"name": "Sainsbury's", "email": "enquiries@sainsburys.co.uk", "color": 0xF56600, "min_tier": "og", "items": ["Taste the Difference Meal Deal", "Wine Case"], "towns": ["London", "Brighton", "Reading"]},
    "asda": {"name": "Asda", "email": "help@asda.co.uk", "color": 0x78BE20, "min_tier": "og", "items": ["Extra Special Pizza", "Groceries Delivery"], "towns": ["Leeds", "Manchester", "Bristol"]},
    "morrisons": {"name": "Morrisons", "email": "fresh@morrisonsplc.co.uk", "color": 0x007833, "min_tier": "og", "items": ["The Best Steak", "Market Street Bakery Box"], "towns": ["Bradford", "Leeds", "Sheffield"]},

    # --- MEMBERS TIER ---
    "greg": {"name": "Greggs", "email": "getintouch@greggs.co.uk", "color": 0xF26522, "min_tier": "members", "items": ["Steak Bake", "Vegan Sausage Roll", "Festive Bake"], "towns": ["Newcastle", "London", "Leeds"]},
    "subway": {"name": "Subway", "email": "support@subway.com", "color": 0x00843D, "min_tier": "members", "items": ["Italian B.M.T.", "Meatball Marinara"], "towns": ["Sheffield", "Bristol", "Nottingham"]},
    "costa": {"name": "Costa Coffee", "email": "feedback@costa.co.uk", "color": 0x8C1D40, "min_tier": "members", "items": ["Caramel Latte", "Ham & Cheese Toastie"], "towns": ["London", "Manchester", "York"]},
    "starbucks": {"name": "Starbucks", "email": "customerservice@starbucks.co.uk", "color": 0x00704A, "min_tier": "members", "items": ["Frappuccino", "Chicken Panini"], "towns": ["Bath", "Oxford", "Cambridge"]},
    "lidl": {"name": "Lidl GB", "email": "customer.services@lidl.co.uk", "color": 0x0050AA, "min_tier": "members", "items": ["Bakery Selection", "Deluxe Grocery Box"], "towns": ["London", "Wimbledon", "Glasgow"]},
    "aldi": {"name": "Aldi UK", "email": "customer.service@aldi.co.uk", "color": 0x002B66, "min_tier": "members", "items": ["Specially Selected Wine", "Weekly Shop"], "towns": ["Atherstone", "London", "Birmingham"]}
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

    try:
        while elapsed < max_wait:
            await asyncio.sleep(300)
            elapsed += 300
            incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
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
    except Exception as e:
        print(f"Inbox watcher error: {e}")

def has_user_access(user_roles, required_tier):
    role_ids_list = [r.id for r in user_roles]
    
    user_has_privates = ROLE_IDS["privates"] in role_ids_list
    user_has_exclusive = ROLE_IDS["exclusive"] in role_ids_list
    user_has_vips = ROLE_IDS["vips"] in role_ids_list
    user_has_og = ROLE_IDS["og"] in role_ids_list

    if required_tier == "privates":
        return user_has_privates
    elif required_tier == "exclusive":
        return user_has_privates or user_has_exclusive
    elif required_tier == "vips":
        return user_has_privates or user_has_exclusive or user_has_vips
    elif required_tier == "og":
        return user_has_privates or user_has_exclusive or user_has_vips or user_has_og
    elif required_tier == "members":
        return True 
    return False

# --- BULLETPROOF COMMAND FACTORY FOR INDIVIDUAL BRANDS (DIRECT HTTP API) ---
def register_brand_command(b_key):
    @bot.command(name=b_key)
    async def brand_command(ctx):
        b_info = BRANDS[b_key]
        required_tier = b_info.get("min_tier", "members")

        if not has_user_access(ctx.author.roles, required_tier) and not ctx.author.guild_permissions.administrator:
            await ctx.send(f"⛔ {ctx.author.mention}, you need **{required_tier.upper()}** status or higher to use `!{b_key}`.", delete_after=10)
            return

        email_body, complaint_name, town, street, item = generate_angry_complaint(b_key)
        temp_email = SafeTempMail(forced_name=complaint_name)
        burner_address = temp_email.address
        subject_line = f"Formal Complaint regarding service at {town} branch"

        sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
        sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

        await ctx.send(f"🔥 **{b_info['name']}**: Ticket dispatched via `{burner_address}`", file=sent_file)

        def send_http_email():
            api_key = os.getenv("RESEND_API_KEY")
            if not api_key:
                raise Exception("RESEND_API_KEY is missing from environment variables.")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": "Grievance Bot <onboarding@resend.dev>",
                "to": [b_info["email"]],
                "subject": subject_line,
                "text": email_body,
                "reply_to": burner_address
            }
            
            response = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=10)
            if response.status_code not in [200, 201]:
                raise Exception(f"API Error ({response.status_code}): {response.text}")

        try:
            await asyncio.to_thread(send_http_email)
        except Exception as e:
            await ctx.send(f"❌ Failed to dispatch email: {e}")
            return

        status_message = await ctx.send(f"⏳ Monitoring response inbox for `{burner_address}`...")
        bot.loop.create_task(watch_burner_inbox(ctx, ctx.author.id, ctx.author.name, b_key, temp_email, status_message, burner_address))

# Register all brand commands securely using the factory
for brand_key in BRANDS.keys():
    register_brand_command(brand_key)

# --- BULK GENERATION COMMAND (OGs and Above, accepts numbers) ---
@bot.command(name="bulkgen")
async def bulk_generation(ctx, brand_key: str = None, count: int = 5):
    """Allows OGs and higher tiers to run bulk generation runs up to 100."""
    user_roles = [r.id for r in ctx.author.roles]
    is_qualified = (
        ctx.author.guild_permissions.administrator or
        ROLE_IDS["privates"] in user_roles or
        ROLE_IDS["exclusive"] in user_roles or
        ROLE_IDS["vips"] in user_roles or
        ROLE_IDS["og"] in user_roles
    )

    if not is_qualified:
        await ctx.send(f"⛔ {ctx.author.mention}, the `!bulkgen` command is restricted to **OGs** and higher roles!", delete_after=10)
        return

    if not brand_key or brand_key.lower() not in BRANDS:
        valid_b = ", ".join(BRANDS.keys())
        await ctx.send(f"⚠️ Usage: `!bulkgen [brand] [count]`\nAvailable brands: `{valid_b}`")
        return

    brand_key = brand_key.lower()
    b_data = BRANDS[brand_key]

    if count < 1 or count > 100:
        await ctx.send("⚠️ Please specify a generation count between 1 and 100.")
        return

    await ctx.send(f"⚙️ Running bulk batch of `{count}` complaints for **{b_data['name']}**...")

    success_count = 0
    for i in range(count):
        try:
            email_body, complaint_name, town, street, item = generate_angry_complaint(brand_key)
            temp_email = SafeTempMail(forced_name=complaint_name)
            burner_address = temp_email.address
            print(f"[BULK {i+1}/{count}] {b_data['name']} -> Name: {complaint_name} | Email: {burner_address}")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Bulk error: {e}")

    await ctx.send(f"✅ Successfully test-generated `{success_count}/{count}` matched complaints for **{b_data['name']}**!")

@bot.command(name="brands")
async def list_brands(ctx):
    embed = discord.Embed(title="📋 Complete UK Company Directory", color=0x3498DB)
    for tier_name in ["privates", "exclusive", "vips", "og", "members"]:
        brand_keys = [k for k, v in BRANDS.items() if v.get("min_tier") == tier_name]
        if brand_keys:
            formatted_cmds = ", ".join([f"`!{b}`" for b in brand_keys])
            embed.add_field(name=f"🔹 {tier_name.upper()} TIER", value=formatted_cmds, inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
