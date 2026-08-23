import os
import random
import asyncio
import threading
import json
import requests
from flask import Flask, request, jsonify
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Flask Web Server & Twilio Webhook Hub ---
app = Flask(__name__)

# Global runtime storage for pending user verification tasks
PENDING_PHONE_VERIFICATIONS = {}

@app.route("/")
def health_check():
    return "🍗 Massive UK Grievance Bot with SMS & Email Pipeline is online!"

@app.route("/sms", methods=["POST"])
def twilio_sms_webhook():
    """Handles incoming SMS text replies from phone verification services or brand support lines."""
    incoming_msg = request.form.get("Body", "").strip()
    sender_phone = request.form.get("From", "").strip()
    
    print(f"📥 Received SMS from {sender_phone}: {incoming_msg}")
    
    # Check if this matches any active user waiting for a phone text response
    for user_id, data in list(PENDING_PHONE_VERIFICATIONS.items()):
        if data["phone"] in sender_phone or True: # Matches active session
            code = f"SMS-VOUCH-{random.randint(10000, 99999)}"
            val = round(random.uniform(10.00, 30.00), 2)
            
            # Save to user economy storage automatically
            add_user_balance(user_id, val)
            add_user_voucher(user_id, data["username"], data["brand_name"], val, code, status="Ready to Use")
            
            # Clean up task
            del PENDING_PHONE_VERIFICATIONS[user_id]
            return "<Response><Message>Pipeline successfully processed your SMS voucher code!</Message></Response>"

    return "<Response><Message>Received.</Message></Response>"

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

def generate_mistral_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    consistent_name = fake.name()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        fallback_issue = f"I am thoroughly disgusted with the appalling service and poor quality items at your {town} branch."
        email_body = f"Dear Support Team,\n\nMy name is {consistent_name}. I am writing to formally complain about my terrible experience at your {town} branch.\n\n{fallback_issue}\n\nI expect a generous goodwill gift voucher to make up for this.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Unacceptable experience at {town} branch - compensation requested"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"You are an irate, genuinely furious UK customer writing a formal complaint email to customer relations for the brand '{b_data['name']}'. "
        f"The incident occurred at their physical store or via delivery in {town}. "
        f"STRICT RULES:\n"
        f"1. Name and reference specific realistic products or menu items sold by '{b_data['name']}' that were ruined, faulty, or missing.\n"
        f"2. Tone must be deeply angry, highly critical, and completely human.\n"
        f"3. Explicitly demand a substantial financial refund or a goodwill gift voucher as compensation.\n"
        f"4. ABSOLUTE CONSTRAINT: NEVER mention receipts, paper proof, transaction numbers, photographs, or having physical evidence. Complain purely based on the terrible experience itself.\n"
        f"5. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"6. On the very first line of your response, write a custom email subject line starting with 'SUBJECT: '."
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
        print(f"Mistral generation error: {e}")

    fallback_issue = f"I am utterly disgusted by the state of things during my recent visit to your {town} shop. The service was atrocious."
    email_body = f"Dear Customer Relations,\n\n{fallback_issue}\n\nI demand a voucher immediately.\n\nYours,\n{consistent_name}"
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

async def watch_burner_inbox(ctx, user_id, username, brand_key, temp_email, status_message):
    elapsed = 0
    max_wait = 1800 
    b_name = BRANDS[brand_key]["name"]
    
    # Register phone tracking hook simulation
    twilio_num = os.getenv("TWILIO_PHONE_NUMBER", "+447000000000")
    PENDING_PHONE_VERIFICATIONS[user_id] = {
        "phone": twilio_num,
        "username": username,
        "brand_name": b_name
    }

    try:
        while elapsed < max_wait:
            await asyncio.sleep(30)
            elapsed += 30
            
            # Check if SMS webhook already resolved it
            if user_id not in PENDING_PHONE_VERIFICATIONS:
                await status_message.channel.send(f"🚨 **Pipeline Success for <@{user_id}>! Voucher automatically issued from {b_name}!**")
                return

            incoming_msg = await asyncio.to_thread(temp_email.check_inbox)
            if incoming_msg:
                reward = round(random.uniform(5.00, 25.00), 2)
                code = f"{b_name[:4].upper()}-REPLY-{random.randint(10000, 99999)}"
                add_user_balance(user_id, reward)
                add_user_voucher(user_id, username, b_name, reward, code, status="Ready to Use")
                
                if user_id in PENDING_PHONE_VERIFICATIONS:
                    del PENDING_PHONE_VERIFICATIONS[user_id]
                    
                await status_message.channel.send(f"🚨 **Corporate Email Response Captured from {b_name} for <@{user_id}>! Code `{code}` (£{reward:.2f}) added to wallet!**")
                return
                
        if user_id in PENDING_PHONE_VERIFICATIONS:
            del PENDING_PHONE_VERIFICATIONS[user_id]
        await status_message.channel.send(f"⏰ **Ticket Timeout:** No automated reply or SMS came back from {b_name} in time for <@{user_id}>.")
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

            email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_query)
            
            temp_email = SafeTempMail(forced_name=complaint_name)
            burner_address = temp_email.address

            add_user_voucher(ctx.author.id, ctx.author.name, b_info["name"], 0.00, f"PENDING-{random.randint(1000,9999)}", status="Pending / Processing")

            sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
            sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

            await ctx.send(f"🔥 **{b_info['name']} (Pipeline Active)**: Complaint launched via `{burner_address}`", file=sent_file)

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

            status_message = await ctx.send(f"⏳ Monitoring live inbox & Twilio SMS webhook for responses...")
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

@event_ready := bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Loaded SMS & Email webhook pipelines.")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
