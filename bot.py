import os
import random
import asyncio
import threading
import json
import re
import requests
from io import BytesIO
from flask import Flask
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Flask Web Server ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🟢 Mistral Persistent Pipeline Code-Brain is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

ECONOMY_FILE = "user_economy.json"
ACTIVE_USERS_FILE = "active_users.json"
USAGE_STATS_FILE = "user_usage_stats.json"
BURNER_REGISTRY_FILE = "burner_registry.json"
PERSISTENT_PIPELINES_FILE = "persistent_pipelines.json"
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

def load_active_users():
    return load_json_file(ACTIVE_USERS_FILE, {})

def save_active_users(data):
    save_json_file(ACTIVE_USERS_FILE, data)

def load_usage_stats():
    return load_json_file(USAGE_STATS_FILE, {})

def save_usage_stats(data):
    save_json_file(USAGE_STATS_FILE, data)

def load_burner_registry():
    return load_json_file(BURNER_REGISTRY_FILE, {})

def save_burner_registry(data):
    save_json_file(BURNER_REGISTRY_FILE, data)

def load_persistent_pipelines():
    return load_json_file(PERSISTENT_PIPELINES_FILE, {})

def save_persistent_pipelines(data):
    save_json_file(PERSISTENT_PIPELINES_FILE, data)

def register_persistent_pipeline(user_id, username, brand_name, burner_username, burner_domain):
    pipelines = load_persistent_pipelines()
    key = f"{burner_username}@{burner_domain}"
    pipelines[key] = {
        "user_id": str(user_id),
        "username": username,
        "brand_name": brand_name,
        "burner_username": burner_username,
        "burner_domain": burner_domain,
        "elapsed": 0
    }
    save_persistent_pipelines(pipelines)

def remove_persistent_pipeline(burner_address):
    pipelines = load_persistent_pipelines()
    key = burner_address.lower()
    if key in pipelines:
        del pipelines[key]
        save_persistent_pipelines(pipelines)

def log_user_usage(user_id, username, brand_name, burner_address, subject, body):
    stats = load_usage_stats()
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {"total_generations": 0, "history": []}
    
    stats[uid]["total_generations"] += 1
    stats[uid]["history"].append({
        "brand": brand_name,
        "burner": burner_address,
        "subject": subject
    })
    save_usage_stats(stats)

    registry = load_burner_registry()
    registry[burner_address.lower()] = {
        "user_id": uid,
        "username": username,
        "brand": brand_name,
        "subject": subject,
        "body_snippet": body[:200],
        "status": "Active Pipeline Waiting for Response"
    }
    save_burner_registry(registry)

def update_burner_status(burner_address, new_status):
    registry = load_burner_registry()
    b_key = burner_address.lower()
    if b_key in registry:
        registry[b_key]["status"] = new_status
        save_burner_registry(registry)

def add_user_voucher(user_id, username, brand_name, value, custom_code):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    
    data[uid]["vouchers"].append({
        "code": custom_code,
        "name": f"{brand_name} Voucher",
        "value": value,
        "status": "Verified & Ready"
    })
    save_economy(data)

class DynamicBurnerMailbox:
    def __init__(self, username, domain):
        self.username = username
        self.domain = domain
        self.address = f"{self.username}@{self.domain}"

    def check_inbox_and_attachments(self):
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
                        class ParsedMail:
                            subject = data.get('subject', 'No Subject')
                            body = data.get('textBody', data.get('body', ''))
                            attachments = data.get('attachments', [])
                        return ParsedMail()
        except Exception:
            pass
        return None

def generate_mistral_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    consistent_name = fake.name()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        fallback_issue = f"I am thoroughly disgusted with the appalling service at your {town} branch."
        email_body = f"Dear Support Team,\n\nMy name is {consistent_name}. I am writing to formally complain about my terrible experience at your {town} branch.\n\n{fallback_issue}\n\nI expect a generous goodwill gift voucher.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Unacceptable experience at {town} branch"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"You are an irate, genuinely furious UK customer writing a formal complaint email to customer relations for the brand '{b_data['name']}'. "
        f"The incident occurred at their physical store or via delivery in {town}. "
        f"STRICT RULES:\n"
        f"1. Reference specific realistic items sold by '{b_data['name']}' that were ruined, faulty, or missing.\n"
        f"2. Tone must be deeply angry, highly critical, and completely human.\n"
        f"3. Explicitly demand a substantial financial refund or a goodwill gift voucher as compensation.\n"
        f"4. ABSOLUTE CONSTRAINT: NEVER mention receipts, paper proof, transaction numbers, or having physical evidence.\n"
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
            subject_line = f"Absolute shambles at your {town} branch"
            body_lines = lines
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
            return "\n".join(body_lines).strip(), consistent_name, town, subject_line
    except Exception:
        pass

    return f"Terrible service at {town}. I demand a voucher.", consistent_name, town, "Complaint"

def ask_mistral_chatbot(user_query, author_name, author_id):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return "Mistral API key is missing."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    active_data = load_active_users()
    economy_data = load_economy()
    usage_stats = load_usage_stats()
    burner_registry = load_burner_registry()
    persistent_pipelines = load_persistent_pipelines()
    
    user_uid = str(author_id)
    user_active_count = active_data.get(user_uid, 0)
    user_total_gens = usage_stats.get(user_uid, {}).get("total_generations", 0)
    user_vouchers_count = len(economy_data.get(user_uid, {}).get("vouchers", []))
    
    system_prompt = (
        f"You are Mistral, an intelligent code-brain supervisor and companion for this consumer grievance platform.\n"
        f"REAL-TIME CODE-BRAIN TELEMETRY:\n"
        f"- Querying User: {author_name} (ID: {author_id})\n"
        f"- User Total Lifetime Pipelines Launched: {user_total_gens}\n"
        f"- User Currently Active Pipelines: {user_active_count}\n"
        f"- User Secured Vouchers: {user_vouchers_count}\n"
        f"- Total Persistent Active Pipelines in Disk State: {len(persistent_pipelines)}\n"
        f"- Total Registered Burners in Database: {len(burner_registry)}"
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7,
        "max_tokens": 250
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    
    return "Code-brain telemetry glitch encountered, ask again!"

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
    draw.text((20, 20), "Official Verified Grievance Dispatched", fill="white", font=font_title)
    content_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 68 + f"\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 25:
            break
        draw.text((20, y_text), line, fill="#222222", font=font_body)
        y_text += 17
    image.save(output_path)
    return output_path

def handle_human_verification_check(email_body):
    triggers = ["verify your identity", "security check", "sms code", "phone verification", "confirm your number", "captcha"]
    lowered = email_body.lower()
    for t in triggers:
        if t in lowered:
            return True
    return False

async def run_identity_and_voucher_pipeline(user_id, username, brand_name, burner_obj, elapsed_time=0):
    max_wait = 1200
    elapsed = elapsed_time
    register_persistent_pipeline(user_id, username, brand_name, burner_obj.username, burner_obj.domain)
    
    try:
        while elapsed < max_wait:
            await asyncio.sleep(35)
            elapsed += 35
            
            incoming = await asyncio.to_thread(burner_obj.check_inbox_and_attachments)
            if incoming:
                if handle_human_verification_check(incoming.body):
                    update_burner_status(burner_obj.address, "Triggered Human/SMS Verification Wall - Bypassing...")
                    await asyncio.sleep(5) 
                    continue

                code_match = re.search(r'\b([A-Z0-9]{4,6}-[A-Z0-9]{4,6}-[A-Z0-9]{4,6}|[A-Z0-9]{8,12})\b', incoming.body)
                
                if code_match or incoming.attachments:
                    extracted_code = code_match.group(1) if code_match else f"{brand_name[:4].upper()}-VERIFIED-{random.randint(1000,9999)}"
                    val = round(random.uniform(5.00, 25.00), 2)
                    
                    add_user_voucher(user_id, username, brand_name, val, extracted_code)
                    update_burner_status(burner_obj.address, f"Success! Voucher Secured (£{val:.2f})")
                    
                    try:
                        user = await bot.fetch_user(int(user_id))
                        if user:
                            dm_text = (
                                f"🛡️ **Identity Verification & Voucher Secured!**\n"
                                f"Brand: **{brand_name}**\n"
                                f"Voucher Code: `{extracted_code}` (Value: **£{val:.2f}**)"
                            )
                            
                            if incoming.attachments:
                                for att in incoming.attachments:
                                    att_name = att.get("filename", "voucher_barcode.png")
                                    att_url = f"https://www.1secmail.com/api/v1/?action=download&login={burner_obj.username}&domain={burner_obj.domain}&id={att.get('id')}"
                                    img_resp = requests.get(att_url)
                                    if img_resp.status_code == 200:
                                        img_file = discord.File(BytesIO(img_resp.content), filename=att_name)
                                        await user.send(dm_text, file=img_file)
                                        break
                            else:
                                await user.send(dm_text)
                    except Exception:
                        pass
                    break
    finally:
        remove_persistent_pipeline(burner_obj.address)
        active_users = load_active_users()
        uid_str = str(user_id)
        if uid_str in active_users and active_users[uid_str] > 0:
            active_users[uid_str] -= 1
            if active_users[uid_str] <= 0:
                del active_users[uid_str]
            save_active_users(active_users)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Resuming persistent pipelines...")
    
    # Automatically restore and resume any active pipelines from disk storage after a reboot/update
    pipelines = load_persistent_pipelines()
    if pipelines:
        print(f"🔄 Restoring {len(pipelines)} ongoing pipeline verification loops from persistent storage...")
        for burner_key, data in list(pipelines.items()):
            burner_obj = DynamicBurnerMailbox(data["burner_username"], data["burner_domain"])
            bot.loop.create_task(run_identity_and_voucher_pipeline(
                data["user_id"],
                data["username"],
                data["brand_name"],
                burner_obj,
                elapsed_time=data.get("elapsed", 0)
            ))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    content_lower = content.lower()
    
    # 1. Handle Generator Command
    if content_lower.startswith("!") and content_lower.endswith(" gen"):
        brand_query = content_lower[1:-4].strip()
        
        if brand_query in BRANDS:
            ctx = await bot.get_context(message)
            uid_str = str(ctx.author.id)
            
            active_users = load_active_users()
            current_active = active_users.get(uid_str, 0)
            
            if current_active >= 50:
                try:
                    await message.delete()
                except Exception:
                    pass
                await ctx.send(f"⏳ {ctx.author.mention}, you have reached your limit of **50 active pipelines**!", delete_after=10)
                return

            try:
                await message.delete()
            except Exception:
                pass

            active_users[uid_str] = current_active + 1
            save_active_users(active_users)

            b_info = BRANDS[brand_query]
            email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_query)
            
            clean_domains = ["1secmail.org", "1secmail.com", "1secmail.net"]
            b_username = f"user.claim.{random.randint(10000, 99999)}"
            b_domain = random.choice(clean_domains)
            burner_obj = DynamicBurnerMailbox(b_username, b_domain)
            burner_address = burner_obj.address

            log_user_usage(message.author.id, message.author.name, b_info["name"], burner_address, subject_line, email_body)

            sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
            sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

            email_client_layout = (
                f"🛡️ **{b_info['name']}**: Pipeline active ({active_users[uid_str]}/50 slots)\n"
                f"> **Burner Assigned:** `{burner_address}`\n"
                f"> **To:** `{b_info['email']}`\n"
                f"> **Subject:** `{subject_line}`\n"
                f"> ----------------------------------------\n"
                f"> *{email_body[:300]}...*"
            )

            await message.channel.send(email_client_layout, file=sent_file)

            def send_resend_email():
                api_key = os.getenv("RESEND_API_KEY")
                if not api_key:
                    raise Exception("RESEND_API_KEY is missing.")
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "from": "Grievance Mailer <onboarding@resend.dev>",
                    "to": [b_info["email"]],
                    "subject": subject_line,
                    "text": email_body,
                    "reply_to": burner_address
                }
                requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=8)

            try:
                await asyncio.to_thread(send_resend_email)
            except Exception as e:
                active_users = load_active_users()
                if uid_str in active_users:
                    active_users[uid_str] -= 1
                    if active_users[uid_str] <= 0:
                        del active_users[uid_str]
                    save_active_users(active_users)
                update_burner_status(burner_address, f"Dispatch Failed: {e}")
                await message.channel.send(f"❌ Dispatch failure: {e}")
                return

            bot.loop.create_task(run_identity_and_voucher_pipeline(message.author.id, message.author.name, b_info["name"], burner_obj))
            return

    # 2. Burner Status Command Check
    if content_lower.startswith("!status"):
        parts = content.split()
        if len(parts) > 1:
            query_burner = parts[1].strip().lower()
            registry = load_burner_registry()
            if query_burner in registry:
                info = registry[query_burner]
                embed = discord.Embed(title=f"📊 Burner Status: {query_burner}", color=0xF39C12)
                embed.add_field(name="Brand", value=info["brand"], inline=True)
                embed.add_field(name="Owner", value=info["username"], inline=True)
                embed.add_field(name="Pipeline State", value=info["status"], inline=False)
                embed.add_field(name="Subject", value=info["subject"], inline=False)
                await message.reply(embed=embed)
                return
            else:
                await message.reply(f"❌ Could not find burner address `{query_burner}` in the database.")
                return

    # 3. Free-flowing Code-Brain Chat
    if not content.startswith("!"):
        async with message.channel.typing():
            ai_reply = await asyncio.to_thread(ask_mistral_chatbot, content, message.author.name, message.author.id)
            await message.reply(ai_reply)
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
    
    if uid not in data or not data[uid]["vouchers"]:
        await ctx.send(f"📦 {ctx.author.mention}, your wallet ledger is empty!")
        return

    vouchers = data[uid]["vouchers"]

    embed = discord.Embed(
        title=f"💳 {ctx.author.name}'s Voucher Wallet",
        color=0x3498DB
    )

    for i, v in enumerate(vouchers, 1):
        field_value = f"Code: `{v['code']}`\nValue: **£{v['value']:.2f}**\nStatus: 🟢 **Verified & Ready**"
        embed.add_field(name=f"Voucher #{i}: {v['name']}", value=field_value, inline=False)

    await ctx.send(embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
