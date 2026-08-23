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
    return "🍗 Massive UK Grievance Bot with Hyper-Realistic Mistral AI is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

ECONOMY_FILE = "user_economy.json"
SHARED_VOUCHERS_FILE = "shared_vouchers.json"
BRANDS_FILE = "brands.json"

def load_json_file(filename, default_val=None):
    if default_val is None:
        default_val = {}
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save {filename}: {e}")

BRANDS = load_json_file(BRANDS_FILE, {})

def load_economy():
    return load_json_file(ECONOMY_FILE, {})

def save_economy(data):
    save_json_file(ECONOMY_FILE, data)

def load_shared_vouchers():
    return load_json_file(SHARED_VOUCHERS_FILE, {})

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

ROLE_IDS = {
    "privates": 1541128316164251788,
    "exclusive": 1541127113803829278,
    "vips": 1541128193547698177,
    "og": 1541122329814368336,
    "members": 1541122505899774113
}

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
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.status_code == 200:
                messages = resp.json()
                if messages and len(messages) > 0:
                    msg_id = messages[0]['id']
                    detail_url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={self.username}&domain={self.domain}&id={msg_id}"
                    detail_resp = requests.get(detail_url, headers=headers, timeout=4)
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

# --- HYPER-REALISTIC MISTRAL SCENARIO GENERATOR ---
def generate_mistral_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    consistent_name = fake.name()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        fallback_issue = f"I went into your {town} branch and had a terrible experience with your products and staff service."
        email_body = f"Dear Customer Support,\n\nMy name is {consistent_name}. I am writing regarding my visit to your {town} branch.\n\n{fallback_issue}\n\nI expect a full refund or a generous gift voucher to make up for this.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Appalling service at {town} store - compensation requested"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Explicit system and user instructions demanding fury, real products, and a voucher demand
    prompt = (
        f"You are an irate, genuinely frustrated UK customer writing a formal complaint email to customer relations for the brand '{b_data['name']}'. "
        f"The incident occurred at their physical store or via delivery in {town}. "
        f"CRITICAL RULES:\n"
        f"1. Name and reference realistic products, menu choices, or items sold strictly by '{b_data['name']}' (e.g., if it's a food place, mention specific cold/ruined food items; if retail, mention specific damaged goods or rude floor staff).\n"
        f"2. Tone must be genuinely angry, highly critical, conversational yet formal enough for corporate support, sounding 100% like a real human consumer losing their temper.\n"
        f"3. Explicitly demand a substantial financial refund or a goodwill gift voucher to compensate for the ruined experience.\n"
        f"4. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"5. On the absolute first line of your response, write a custom email subject line starting with 'SUBJECT: '."
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": 400
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            result_json = response.json()
            content = result_json["choices"][0]["message"]["content"].strip()
            
            lines = content.splitlines()
            subject_line = f"Absolute shambles at your {town} branch - compensation required"
            body_lines = lines
            
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
                
            email_body = "\n".join(body_lines).strip()
            return email_body, consistent_name, town, subject_line
    except Exception as e:
        print(f"Mistral acceleration exception: {e}")

    fallback_issue = f"I am utterly disgusted by the state of things during my recent visit to your {town} shop. The service was atrocious and items were completely sub-par."
    email_body = f"Dear Customer Relations,\n\n{fallback_issue}\n\nI demand a voucher or reimbursement immediately.\n\nYours,\n{consistent_name}"
    return email_body, consistent_name, town, f"Unacceptable experience at {town} store"

def create_email_image(sender, recipient, subject, body, brand_color=0xF26522, output_path="sent_complaint.png"):
    if isinstance(brand_color, int):
        brand_color = f"#{brand_color:06x}"
    width, height = 800, 540
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 12)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill=brand_color)
    draw.text((20, 20), "📤 Furious Consumer Grievance Dispatched (Mistral AI)", fill="white", font=font_title)
    content_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 68 + f"\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 25:
            break
        draw.text((20, y_text), line, fill="#222222", font=font_body)
        y_text += 17
    image.save(output_path)
    return output_path

async def harvest_vouchers_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            if BRANDS:
                brand_key = random.choice(list(BRANDS.keys()))
                b_info = BRANDS[brand_key]
                email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_key)
                temp_email = SafeTempMail(forced_name=complaint_name)

                def send_brevo():
                    api_key = os.getenv("BREVO_API_KEY")
                    if not api_key:
                        return
                    headers = {"api-key": api_key, "Content-Type": "application/json"}
                    payload = {
                        "sender": {"name": "Auto Harvester", "email": "iusethisforwatching@gmail.com"},
                        "to": [{"email": b_info["email"], "name": b_info["name"]}],
                        "subject": subject_line,
                        "textContent": email_body,
                        "replyTo": {"email": temp_email.address}
                    }
                    requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=8)

                await asyncio.to_thread(send_brevo)
                
                for _ in range(2):
                    await asyncio.sleep(45)
                    incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
                    if incoming_msg:
                        reward_val = round(random.uniform(5.00, 30.00), 2)
                        prefix = b_info["name"][:4].upper()
                        code = f"{prefix}-REAL-{random.randint(10000, 99999)}"
                        store_harvested_voucher(brand_key, b_info["name"], reward_val, code)
                        break
        except Exception as e:
            print(f"Harvester loop error: {e}")
        await asyncio.sleep(25)

async def watch_burner_inbox(ctx, user_id, username, brand_key, temp_email, status_message):
    elapsed = 0
    max_wait = 2400 
    b_name = BRANDS[brand_key]["name"]
    try:
        while elapsed < max_wait:
            await asyncio.sleep(45)
            elapsed += 45
            incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
            if incoming_msg:
                reward = round(random.uniform(5.00, 25.00), 2)
                code = f"{b_name[:4].upper()}-LIVE-{random.randint(10000, 99999)}"
                add_user_balance(user_id, reward)
                add_user_voucher(user_id, username, b_name, reward, code, status="Ready to Use")
                await status_message.channel.send(f"🚨 **Corporate Response Captured from {b_name} for <@{user_id}>! Voucher code `{code}` (£{reward:.2f}) added to wallet!**")
                return
        await status_message.channel.send(f"⏰ **Ticket Timeout:** No automated or agent response came back from {b_name} in time for <@{user_id}>.")
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

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip().lower()
    
    if content.startswith("!") and content.endswith(" gen"):
        brand_query = content[1:-4].strip()
        
        if brand_query in BRANDS:
            ctx = await bot.get_context(message)
            try:
                await message.delete()
            except Exception:
                pass

            b_info = BRANDS[brand_query]
            required_tier = b_info.get("min_tier", "members")

            if not has_user_access(ctx.author.roles, required_tier) and not ctx.author.guild_permissions.administrator:
                await ctx.send(f"⛔ {ctx.author.mention}, you need **{required_tier.upper()}** status to use `!{brand_query} gen`.", delete_after=10)
                return

            # Fast multi-threaded execution to ensure speed
            email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_query)
            
            temp_email = SafeTempMail(forced_name=complaint_name)
            burner_address = temp_email.address

            add_user_voucher(ctx.author.id, ctx.author.name, b_info["name"], 0.00, f"PENDING-{random.randint(1000,9999)}", status="Pending / Processing")

            sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
            sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

            await ctx.send(f"🔥 **{b_info['name']} (Hyper-Realistic Mistral AI)**: Grievance email launched via `{burner_address}`", file=sent_file)

            def send_brevo_email():
                api_key = os.getenv("BREVO_API_KEY")
                if not api_key:
                    raise Exception("BREVO_API_KEY is missing.")
                headers = {"api-key": api_key, "Content-Type": "application/json"}
                payload = {
                    "sender": {"name": "Grievance Dispatcher", "email": "iusethisforwatching@gmail.com"},
                    "to": [{"email": b_info["email"], "name": b_info["name"]}],
                    "subject": subject_line,
                    "textContent": email_body,
                    "replyTo": {"email": burner_address}
                }
                requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=8)

            try:
                await asyncio.to_thread(send_brevo_email)
            except Exception as e:
                await ctx.send(f"❌ Dispatch failure: {e}")
                return

            status_message = await ctx.send(f"⏳ Monitoring live support inbox for `{burner_address}`...")
            bot.loop.create_task(watch_burner_inbox(ctx, ctx.author.id, ctx.author.name, brand_query, temp_email, status_message))
            return

    await bot.process_commands(message)

@bot.command(name="voucher", aliases=["wallet", "vouchers"])
async def show_voucher_wallet(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    data = load_economy()
    uid = str(ctx.author.id)
    
    if uid not in data or (not data[uid]["vouchers"] and data[uid]["balance"] <= 0):
        await ctx.send(f"📦 {ctx.author.mention}, your wallet ledger is empty! File a complaint using `![brand] gen`.")
        return

    balance = data[uid].get("balance", 0.0)
    vouchers = data[uid].get("vouchers", [])

    embed = discord.Embed(
        title=f"💳 {ctx.author.name}'s Unified Voucher & Wallet Ledger",
        description=f"Total Virtual Balance: **£{balance:.2f}**",
        color=0x3498DB
    )

    for i, v in enumerate(vouchers, 1):
        status = v.get("status", "Ready to Use")
        status_icon = "🟢 **Ready to Use**" if status == "Ready to Use" else "⏳ **Pending / Processing**"
        field_value = f"Code: `{v['code']}`\nValue: **£{v['value']:.2f}**\nStatus: {status_icon}"
        embed.add_field(name=f"Request #{i}: {v['name']}", value=field_value, inline=False)

    await ctx.send(embed=embed)

@bot.command(name="bulkgen")
@commands.has_permissions(administrator=True)
async def bulk_gen(ctx, count: int = 5):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if count > 20:
        count = 20

    generated_summary = []
    for _ in range(count):
        if BRANDS:
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
    embed.set_footer(text="Added to shared pool. Claim using !Qvouch [brand].")
    await ctx.send(embed=embed)

@bot.command(name="Qvouch")
async def quick_vouch(ctx, brand_query: str = None):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not brand_query or brand_query.lower() not in BRANDS:
        await ctx.send("⚠️ Usage: `!Qvouch [brand]`")
        return

    b_key = brand_query.lower()
    shared_data = load_shared_vouchers()
    
    if b_key not in shared_data or not shared_data[b_key]:
        await ctx.send(f"❌ Sorry, **none available** right now for `{BRANDS[b_key]['name']}`! Try again later.")
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
        description=f"Here is your harvested voucher, {ctx.author.mention}!",
        color=BRANDS[b_key]["color"]
    )
    embed.add_field(name="Voucher Code", value=f"`{code}`", inline=False)
    embed.add_field(name="Value", value=f"**£{val:.2f}**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="brands")
async def list_brands(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(title=f"📋 Available Company Directory ({len(BRANDS)} Brands Loaded)", color=0x3498DB)
    for tier_name in ["privates", "exclusive", "vips", "og"]:
        brand_keys = [f"`!{k} gen`" for k, v in BRANDS.items() if v.get("min_tier") == tier_name]
        if brand_keys:
            for i in range(0, len(brand_keys), 15):
                chunk = brand_keys[i:i+15]
                embed.add_field(name=f"🔹 {tier_name.upper()} TIER", value=", ".join(chunk), inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Loaded {len(BRANDS)} brands with accelerated Mistral anger prompts.")
    bot.loop.create_task(harvest_vouchers_task())

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
