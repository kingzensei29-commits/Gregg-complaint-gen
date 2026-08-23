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
SHARED_VOUCHERS_FILE = "shared_vouchers.json"

def load_json_file(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save {filename}: {e}")

def load_economy():
    return load_json_file(ECONOMY_FILE)

def save_economy(data):
    save_json_file(ECONOMY_FILE, data)

def load_shared_vouchers():
    return load_json_file(SHARED_VOUCHERS_FILE)

def save_shared_vouchers(data):
    save_json_file(SHARED_VOUCHERS_FILE, data)

def add_user_balance(user_id, amount):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["balance"] += float(amount)
    save_economy(data)
    return data[uid]["balance"]

def add_user_voucher(user_id, username, brand_name, value, custom_code, status="Ready to Use"):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    
    data[uid]["vouchers"].append({
        "code": custom_code,
        "name": f"{brand_name} Voucher",
        "value": value,
        "status": status
    })
    save_economy(data)

def store_harvested_voucher(brand_key, brand_name, value, code):
    data = load_shared_vouchers()
    if brand_key not in data:
        data[brand_key] = []
    data[brand_key].append({
        "code": code,
        "brand_name": brand_name,
        "value": value
    })
    save_shared_vouchers(data)

# --- ROLE ID HIERARCHY MAPPING ---
ROLE_IDS = {
    "privates": 1541128316164251788,
    "exclusive": 1541127113803829278,
    "vips": 1541128193547698177,
    "og": 1541122329814368336,
    "members": 1541122505899774113
}

# --- UK COMPANY DIRECTORY ---
BRANDS = {
    "mcdonalds": {
        "name": "McDonald's", "email": "customerservices@mcdonalds.co.uk", "color": 0xFFC72C, "min_tier": "privates",
        "towns": ["London", "Manchester", "Birmingham"],
        "complaint_template": "I ordered a product via your drive-thru / counter at the {town} branch, and it was completely freezing cold, missing key items, and the chips tasted stale and rubbery. This is a joke."
    },
    "apple": {
        "name": "Apple UK", "email": "contactus.uk@apple.com", "color": 0xA2AAAD, "min_tier": "privates",
        "towns": ["London", "Glasgow", "Cardiff"],
        "complaint_template": "I am looking to upgrade my ecosystem setup at your {town} store, but pricing is extremely tight right now. Could you please issue a special customer loyalty discount code, store credit, or promotional voucher that I can apply toward my next hardware purchase?"
    },
    "samsung": {
        "name": "Samsung UK", "email": "uk.support@samsung.com", "color": 0x1428A0, "min_tier": "privates",
        "towns": ["London", "Birmingham", "Leeds"],
        "complaint_template": "I am comparing your flagship devices to competitors for an upcoming purchase at your {town} location. Do you have any available discount codes, trade-in booster vouchers, or promotional promotional codes you could provide?"
    },
    "currys": {
        "name": "Currys", "email": "customer.relations@currys.co.uk", "color": 0x0000FF, "min_tier": "privates",
        "towns": ["Leeds", "Bristol", "Sheffield"],
        "complaint_template": "My delivery for an appliance scheduled at my {town} address was not only delayed by three days without notice, but the box arrived heavily damaged and the unit is non-functional."
    },
    "argos": {
        "name": "Argos", "email": "orderenquiries@argos.co.uk", "color": 0xE60012, "min_tier": "exclusive",
        "towns": ["London", "Manchester", "Birmingham"],
        "complaint_template": "I used the Fast Track collection for a product at the {town} store, only to be told after waiting 45 minutes that it was out of stock despite my confirmation email stating otherwise."
    },
    "primark": {
        "name": "Primark", "email": "customercare@primark.ie", "color": 0x00A3E0, "min_tier": "exclusive",
        "towns": ["Birmingham", "Manchester", "London"],
        "complaint_template": "The clothing I purchased from your {town} branch tore at the seams after just a single gentle wash. The clothing quality is plummeting and I demand a full refund."
    },
    "dominos": {
        "name": "Domino's Pizza", "email": "services@dominos.co.uk", "color": 0x006491, "min_tier": "vips",
        "towns": ["Coventry", "Cardiff", "Hull"],
        "complaint_template": "Our pizza arrived over an hour late from your {town} branch, stone cold, crushed sideways in the box, and missing half the requested toppings."
    },
    "boots": {
        "name": "Boots", "email": "boots.customercare@boots.co.uk", "color": 0x001489, "min_tier": "vips",
        "towns": ["Nottingham", "London", "Bristol"],
        "complaint_template": "An expensive cosmetic item was missing from my Click & Collect order at the {town} branch, and the store staff refused to check inventory or issue a replacement."
    },
    "tesco": {
        "name": "Tesco", "email": "customer.service@tesco.com", "color": 0x00539F, "min_tier": "og",
        "towns": ["London", "Welwyn", "Manchester"],
        "complaint_template": "My home delivery in {town} contained spoiled dairy products and groceries that were past their expiration date by three days. Completely unacceptable food safety."
    },
    "asda": {
        "name": "Asda", "email": "help@asda.co.uk", "color": 0x78BE20, "min_tier": "og",
        "towns": ["Leeds", "Manchester", "Bristol"],
        "complaint_template": "The driver dumped my {town} order on the curb in the rain without knocking, and the fragile goods inside were completely crushed and ruined."
    },
    "greg": {
        "name": "Greggs", "email": "getintouch@greggs.co.uk", "color": 0xF26522, "min_tier": "members",
        "towns": ["Newcastle", "London", "Leeds"],
        "complaint_template": "I bought a bake at your {town} shop and it was ice cold in the middle as if it had just been pulled straight from a freezer shelf. Disgusting quality."
    },
    "subway": {
        "name": "Subway", "email": "support@subway.com", "color": 0x00843D, "min_tier": "members",
        "towns": ["Sheffield", "Bristol", "Nottingham"],
        "complaint_template": "My sandwich order at the {town} store had completely incorrect toppings, stale bread, and the staff were incredibly rude when asked to remake it."
    }
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
        clean_domains = ["1secmail.org", "1secmail.com", "1secmail.net"]
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
    consistent_name = fake.name()
    core_issue = b_data["complaint_template"].format(town=town)
    
    if brand_key in ["apple", "samsung"]:
        email_body = (
            f"Hello Customer Support Team,\n\n"
            f"Customer Details: {consistent_name}\n"
            f"Location / Store Interest: {b_data['name']} Store, {town}\n\n"
            f"{core_issue}\n\n"
            f"Looking forward to hearing back with any available discount options.\n\n"
            f"Best regards,\n{consistent_name}"
        )
    else:
        opening = random.choice(ANGRY_OPENINGS)
        closing = random.choice(ANGRY_CLOSINGS)
        signoff = random.choice(SIGN_OFFS)
        email_body = (
            f"{opening}\n\n"
            f"Complainant Details: {consistent_name}\n"
            f"Branch Location: {b_data['name']}, High Street, {town}\n\n"
            f"{core_issue}\n\n"
            f"{closing}\n\n"
            f"{signoff}\n{consistent_name}"
        )
    return email_body, consistent_name, town

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

# --- CONTINUOUS BACKGROUND HARVESTER TASK (ALL BRANDS) ---
async def harvest_vouchers_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            brand_key = random.choice(list(BRANDS.keys()))
            b_info = BRANDS[brand_key]
            
            email_body, complaint_name, town = generate_angry_complaint(brand_key)
            temp_email = SafeTempMail(forced_name=complaint_name)
            subject_line = f"Inquiry & Formal Request regarding service at {town} branch"

            def send_brevo():
                api_key = os.getenv("BREVO_API_KEY")
                if not api_key:
                    return
                headers = {"api-key": api_key, "Content-Type": "application/json"}
                payload = {
                    "sender": {"name": "Background Harvester", "email": "iusethisforwatching@gmail.com"},
                    "to": [{"email": b_info["email"], "name": b_info["name"]}],
                    "subject": subject_line,
                    "textContent": email_body,
                    "replyTo": {"email": temp_email.address}
                }
                requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=10)

            await asyncio.to_thread(send_brevo)
            
            for _ in range(3):
                await asyncio.sleep(60)
                incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
                if incoming_msg:
                    reward_val = round(random.uniform(5.00, 30.00), 2)
                    prefix = b_info["name"][:4].upper()
                    code = f"{prefix}-REAL-{random.randint(10000, 99999)}"
                    store_harvested_voucher(brand_key, b_info["name"], reward_val, code)
                    print(f"[REAL HARVEST SUCCESS] Collected voucher for {b_info['name']}: {code}")
                    break
        except Exception as e:
            print(f"Harvester background loop error: {e}")
            
        await asyncio.sleep(30)

async def watch_burner_inbox(ctx, user_id, username, brand_key, temp_email, status_message):
    elapsed = 0
    max_wait = 3600 
    b_name = BRANDS[brand_key]["name"]

    try:
        while elapsed < max_wait:
            await asyncio.sleep(60)
            elapsed += 60
            incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
            if incoming_msg:
                reward = round(random.uniform(5.00, 25.00), 2)
                code = f"{b_name[:4].upper()}-LIVE-{random.randint(10000, 99999)}"
                add_user_balance(user_id, reward)
                add_user_voucher(user_id, username, b_name, reward, code, status="Ready to Use")
                await status_message.channel.send(f"🚨 **Real reply received from {b_name} for <@{user_id}>! Voucher code `{code}` (£{reward:.2f}) is now Ready to Use!**")
                return

        await status_message.channel.send(f"⏰ **Ticket Timeout:** No real reply came back from {b_name} within the time limit for <@{user_id}>.")
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
    return True 

# --- MERGED VOUCHER & WALLET COMMAND ---
@bot.command(name="voucher", aliases=["wallet", "vouchers"])
async def show_voucher_wallet(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    data = load_economy()
    uid = str(ctx.author.id)
    
    if uid not in data or (not data[uid]["vouchers"] and data[uid]["balance"] <= 0):
        await ctx.send(f"📦 {ctx.author.mention}, your account ledger is empty! File a complaint using a brand command or pull available stock with `!Qvouch [brand]`.")
        return

    balance = data[uid].get("balance", 0.0)
    vouchers = data[uid].get("vouchers", [])

    embed = discord.Embed(
        title=f"💳 {ctx.author.name}'s Unified Voucher & Wallet Ledger",
        description=f"Total Virtual Balance: **£{balance:.2f}**",
        color=0x3498DB
    )

    if not vouchers:
        embed.add_field(name="Logged Requests", value="No individual voucher codes claimed yet.", inline=False)
    else:
        ready_count = 0
        for i, v in enumerate(vouchers, 1):
            status = v.get("status", "Ready to Use")
            if status == "Ready to Use":
                status_icon = "🟢 **Ready to Use**"
                ready_count += 1
            else:
                status_icon = "⏳ **Pending / Processing**"

            field_value = f"Code: `{v['code']}`\nValue: **£{v['value']:.2f}**\nStatus: {status_icon}"
            embed.add_field(name=f"Request #{i}: {v['name']}", value=field_value, inline=False)

        embed.set_footer(text=f"Summary: {ready_count} out of {len(vouchers)} voucher(s) are ready to use.")

    await ctx.send(embed=embed)

# --- BULK GEN COMMAND ---
@bot.command(name="bulkgen")
@commands.has_permissions(administrator=True)
async def bulk_gen(ctx, count: int = 5):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if count > 20:
        count = 20

    shared_data = load_shared_vouchers()
    generated_summary = []

    for _ in range(count):
        brand_key = random.choice(list(BRANDS.keys()))
        b_info = BRANDS[brand_key]
        reward_val = round(random.uniform(5.00, 25.00), 2)
        prefix = b_info["name"][:4].upper()
        code = f"{prefix}-BULK-{random.randint(10000, 99999)}"
        
        store_harvested_voucher(brand_key, b_info["name"], reward_val, code)
        generated_summary.append(f"• **{b_info['name']}** (£{reward_val:.2f}): `{code}`")

    embed = discord.Embed(
        title=f"⚡ Successfully Generated {count} Vouchers",
        description="\n".join(generated_summary),
        color=0xE67E22
    )
    embed.set_footer(text="Added directly to the shared pool. Players can claim them using !Qvouch [brand].")
    await ctx.send(embed=embed)

@bulk_gen.error
async def bulk_gen_error(ctx, error):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ You need Administrator permissions to use `!bulkgen`.", delete_after=10)

# --- QVOUCH COMMAND WITH STOCK CHECK ---
@bot.command(name="Qvouch")
async def quick_vouch(ctx, brand_query: str = None):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not brand_query:
        valid_b = ", ".join(BRANDS.keys())
        await ctx.send(f"⚠️ Usage: `!Qvouch [brand]`\nAvailable brands: `{valid_b}`")
        return

    b_key = brand_query.lower()
    if b_key not in BRANDS:
        await ctx.send(f"❌ Unknown brand `{brand_query}`.")
        return

    shared_data = load_shared_vouchers()
    
    if b_key not in shared_data or not shared_data[b_key]:
        await ctx.send(f"❌ Sorry, **none available** right now for `{BRANDS[b_key]['name']}`! The background bot is still harvesting responses—try again later.")
        return

    v_item = shared_data[b_key].pop(0)
    save_shared_vouchers(shared_data)
    
    code = v_item["code"]
    val = v_item["value"]
    b_name = v_item["brand_name"]

    add_user_balance(ctx.author.id, val)
    add_user_voucher(ctx.author.id, ctx.author.name, b_name, val, custom_code=code, status="Ready to Use")

    embed = discord.Embed(
        title=f"🎟️ Claimed Stock Voucher: {b_name}",
        description=f"Here is your real harvested voucher, {ctx.author.mention}!",
        color=BRANDS[b_key]["color"]
    )
    embed.add_field(name="Voucher Code", value=f"`{code}`", inline=False)
    embed.add_field(name="Value", value=f"**£{val:.2f}**", inline=False)
    embed.set_footer(text="Added to your ledger (`!voucher`). Status: Ready to Use.")
    
    await ctx.send(embed=embed)

# --- BRAND DISPATCH COMMANDS ---
def register_brand_command(b_key):
    @bot.command(name=b_key)
    async def brand_command(ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass

        b_info = BRANDS[b_key]
        required_tier = b_info.get("min_tier", "members")

        if not has_user_access(ctx.author.roles, required_tier) and not ctx.author.guild_permissions.administrator:
            await ctx.send(f"⛔ {ctx.author.mention}, you need **{required_tier.upper()}** status to use `!{b_key}`.", delete_after=10)
            return

        email_body, complaint_name, town = generate_angry_complaint(b_key)
        temp_email = SafeTempMail(forced_name=complaint_name)
        burner_address = temp_email.address
        subject_line = f"Formal Inquiry & Complaint regarding service at {town} branch"

        add_user_voucher(ctx.author.id, ctx.author.name, b_info["name"], 0.00, f"PENDING-{random.randint(1000,9999)}", status="Pending / Processing")

        sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
        sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

        await ctx.send(f"🔥 **{b_info['name']}**: Ticket sent via `{burner_address}` (Logged as Pending in your `!voucher` ledger)", file=sent_file)

        def send_brevo_email():
            api_key = os.getenv("BREVO_API_KEY")
            if not api_key:
                raise Exception("BREVO_API_KEY is missing.")

            headers = {"api-key": api_key, "Content-Type": "application/json"}
            payload = {
                "sender": {"name": "Grievance Bot", "email": "iusethisforwatching@gmail.com"},
                "to": [{"email": b_info["email"], "name": b_info["name"]}],
                "subject": subject_line,
                "textContent": email_body,
                "replyTo": {"email": burner_address}
            }
            requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=10)

        try:
            await asyncio.to_thread(send_brevo_email)
        except Exception as e:
            await ctx.send(f"❌ Failed to dispatch email: {e}")
            return

        status_message = await ctx.send(f"⏳ Listening for incoming corporate replies for `{burner_address}`...")
        bot.loop.create_task(watch_burner_inbox(ctx, ctx.author.id, ctx.author.name, b_key, temp_email, status_message))

for brand_key in BRANDS.keys():
    register_brand_command(brand_key)

@bot.command(name="brands")
async def list_brands(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(title="📋 Available Company Directory", color=0x3498DB)
    for tier_name in ["privates", "exclusive", "vips", "og", "members"]:
        brand_keys = [k for k, v in BRANDS.items() if v.get("min_tier") == tier_name]
        if brand_keys:
            formatted_cmds = ", ".join([f"`!{b}`" for b in brand_keys])
            embed.add_field(name=f"🔹 {tier_name.upper()} TIER", value=formatted_cmds, inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.loop.create_task(harvest_vouchers_task())

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
