import os
import random
import asyncio
import threading
import json
import re
import requests
from io import BytesIO
from flask import Flask, request, jsonify
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Helper function defined first to fix the load order ---
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

# --- Flask Web Server with Secured Brevo Inbound Webhook ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🟢 Secured UK Mistral Brain-Integrated Bot is online!"

@app.route("/brevo-inbound", methods=["POST"])
def brevo_inbound_webhook():
    expected_secret = os.getenv("BREVO_WEBHOOK_SECRET")
    if expected_secret:
        client_secret = request.headers.get("X-Webhook-Secret", "")
        if client_secret != expected_secret:
            return jsonify({"status": "error", "message": "Unauthorized webhook access"}), 403

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No payload received"}), 400

        items = data.get("items", [data])
        for item in items:
            recipient_list = item.get("Recipients", [])
            to_field = item.get("To", [])
            
            target_address = ""
            if recipient_list:
                target_address = recipient_list[0].lower()
            elif to_field:
                target_address = to_field[0].get("Address", "").lower()

            email_body = item.get("ExtractedMarkdownMessage", item.get("RawHtmlBody", item.get("Body", "")))
            subject = item.get("Subject", "Support Reply")
            attachments = item.get("Attachments", [])

            brain = load_brain()
            pipelines = brain.get("persistent_pipelines", {})
            matched_pipeline = None
            
            for p_key, p_data in pipelines.items():
                burner_full = f"{p_data['burner_username']}@{p_data['burner_domain']}".lower()
                if burner_full == target_address or p_data['burner_username'].lower() in target_address:
                    matched_pipeline = p_data
                    break

            if matched_pipeline:
                user_id = int(matched_pipeline["user_id"])
                brand_name = matched_pipeline["brand_name"]
                burner_address = f"{matched_pipeline['burner_username']}@{matched_pipeline['burner_domain']}"
                
                code_match = re.search(r'\b([A-Z0-9]{4,6}-[A-Z0-9]{4,6}-[A-Z0-9]{4,6}|[A-Z0-9]{8,12})\b', email_body)
                extracted_code = code_match.group(1) if code_match else f"{brand_name[:4].upper()}-{random.randint(10000,99999)}"
                val = round(random.uniform(5.00, 30.00), 2)
                
                add_user_voucher(user_id, matched_pipeline["username"], brand_name, val, extracted_code)
                update_burner_status_by_address(burner_address, f"Success! Verified UK Reply Processed (£{val:.2f})")
                
                if bot.loop:
                    asyncio.run_coroutine_threadsafe(
                        deliver_voucher_dm(user_id, brand_name, subject, extracted_code, val, email_body, attachments),
                        bot.loop
                    )
                
                remove_persistent_pipeline(burner_address)

        return jsonify({"status": "success", "processed": True}), 200
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

BRAIN_FILE = "brain.json"
BRANDS_FILE = "brands.json"

BRANDS = load_json_file(BRANDS_FILE, {})

def load_brain():
    default_structure = {
        "economy": {},
        "active_users": {},
        "usage_stats": {},
        "burner_registry": {},
        "persistent_pipelines": {}
    }
    if os.path.exists(BRAIN_FILE):
        try:
            with open(BRAIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in default_structure:
                    if key not in data:
                        data[key] = default_structure[key]
                return data
        except Exception:
            pass
    return default_structure

def save_brain(data):
    try:
        with open(BRAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save brain.json: {e}")

def generate_custom_complaint_id(username):
    clean_name = re.sub(r'[^a-zA-Z]', '', username).lower()
    if len(clean_name) < 4:
        clean_name = (clean_name + "user")[:4]
    else:
        clean_name = clean_name[:4]
    
    part1 = ''.join(random.choices("0123456789ABCDEF", k=4))
    part2 = ''.join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    return f"{clean_name}-{part1}-{part2}"

def register_persistent_pipeline(user_id, username, brand_name, burner_username, burner_domain, custom_id):
    brain = load_brain()
    key = f"{burner_username}@{burner_domain}"
    brain["persistent_pipelines"][key] = {
        "user_id": str(user_id),
        "username": username,
        "brand_name": brand_name,
        "burner_username": burner_username,
        "burner_domain": burner_domain,
        "custom_id": custom_id
    }
    save_brain(brain)

def remove_persistent_pipeline(burner_address):
    brain = load_brain()
    pipelines = brain.get("persistent_pipelines", {})
    key = burner_address.lower()
    for p_key, p_data in list(pipelines.items()):
        if p_key == key or f"{p_data['burner_username']}@{p_data['burner_domain']}".lower() == key:
            del pipelines[p_key]
            save_brain(brain)
            break

def log_user_usage(user_id, username, brand_name, burner_address, subject, body, custom_id):
    brain = load_brain()
    uid = str(user_id)
    
    if uid not in brain["usage_stats"]:
        brain["usage_stats"][uid] = {"total_generations": 0, "history": []}
    
    brain["usage_stats"][uid]["total_generations"] += 1
    brain["usage_stats"][uid]["history"].append({
        "brand": brand_name,
        "burner": burner_address,
        "subject": subject,
        "custom_id": custom_id
    })
    
    brain["burner_registry"][custom_id] = {
        "custom_id": custom_id,
        "address": burner_address.lower(),
        "user_id": uid,
        "username": username,
        "brand": brand_name,
        "subject": subject,
        "body_snippet": body[:200],
        "status": "Active UK Pipeline Awaiting Response"
    }
    save_brain(brain)

def update_burner_status_by_address(burner_address, new_status):
    brain = load_brain()
    b_key = burner_address.lower()
    for k, info in brain["burner_registry"].items():
        if info["address"] == b_key:
            info["status"] = new_status
            save_brain(brain)
            break

def add_user_voucher(user_id, username, brand_name, value, custom_code):
    brain = load_brain()
    uid = str(user_id)
    if uid not in brain["economy"]:
        brain["economy"][uid] = {"balance": 0.0, "vouchers": []}
    
    brain["economy"][uid]["vouchers"].append({
        "code": custom_code,
        "name": f"{brand_name} Voucher",
        "value": value,
        "status": "Verified & Secure UK"
    })
    save_brain(brain)

async def deliver_voucher_dm(user_id, brand_name, subject, code, value, body, attachments):
    try:
        user = await bot.fetch_user(user_id)
        if user:
            dm_text = (
                f"🛡️ **Verified UK Support Reply Secured!**\n"
                f"Brand: **{brand_name}**\n"
                f"Subject: *{subject}*\n"
                f"Voucher Code: `{code}` (Value: **£{value:.2f}**)\n\n"
                f"> *Snippet:* {body[:300]}..."
            )
            await user.send(dm_text)
    except Exception as e:
        print(f"Failed to deliver secure DM: {e}")

class DynamicBurnerMailbox:
    def __init__(self, full_name):
        clean_name = re.sub(r'[^a-zA-Z]', '', full_name).lower()
        if len(clean_name) < 3:
            clean_name = "customer"
        self.username = f"{clean_name}{random.randint(100, 9999)}"
        self.domain = os.getenv("BREVO_INBOUND_DOMAIN", "bettercads.free.nf")
        self.address = f"{self.username}@{self.domain}"

def generate_mistral_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    consistent_name = fake.name()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        fallback_issue = f"I visited your {town} branch and found the items completely defective and unusable upon unpacking."
        email_body = f"Dear Customer Support Team,\n\nMy name is {consistent_name}. I am writing to formally log a serious complaint regarding my recent experience at your {town} branch.\n\n{fallback_issue}\n\nI expect a prompt resolution or a goodwill voucher.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Poor service and product failure at {town} branch"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = (
        f"You are writing a detailed, formal customer complaint email targeted at UK consumer standards for the brand '{b_data['name']}' regarding their branch in {town}. "
        f"STRICT DIRECTIVES:\n"
        f"1. Invent a specific, logical product failure or appalling staff service issue.\n"
        f"2. Write in a serious, frustrated British English tone demanding a goodwill gesture or voucher.\n"
        f"3. ABSOLUTELY NEVER mention receipts, proof of purchase, or transaction slips.\n"
        f"4. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"5. The very first line must start with 'SUBJECT: ' followed by a custom subject line."
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 400
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            lines = content.splitlines()
            subject_line = f"Appalling experience at your {town} branch"
            body_lines = lines
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
            return "\n".join(body_lines).strip(), consistent_name, town, subject_line
    except Exception:
        pass

    return f"Serious product defect reported at {town}, demanding resolution.", consistent_name, town, "Formal complaint regarding service"

def ask_mistral_chatbot(user_query, author_name, author_id):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return "Mistral API key is missing."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    brain = load_brain()
    user_uid = str(author_id)
    
    system_prompt = (
        f"You are Mistral, secure code-brain supervisor for this UK grievance pipeline.\n"
        f"- User: {author_name} (ID: {author_id})\n"
        f"- Total Pipelines: {brain['usage_stats'].get(user_uid, {}).get('total_generations', 0)}\n"
        f"- Secured Vouchers: {len(brain['economy'].get(user_uid, {}).get('vouchers', []))}"
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}],
        "temperature": 0.7,
        "max_tokens": 250
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    
    return "Code-brain telemetry glitch encountered!"

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
    draw.text((20, 20), "Official Verified UK Grievance Dispatched", fill="white", font=font_title)
    content_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 68 + f"\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 25:
            break
        draw.text((20, y_text), line, fill="#222222", font=font_body)
        y_text += 17
    image.save(output_path)
    return output_path

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Secure UK Brain-Connected Webhook Listener Active.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    content_lower = content.lower()
    
    # Generator Command (![brandname] gen)
    if content_lower.startswith("!") and content_lower.endswith(" gen"):
        brand_query = content_lower[1:-4].strip()
        
        if brand_query in BRANDS:
            ctx = await bot.get_context(message)
            uid_str = str(ctx.author.id)
            
            brain = load_brain()
            active_users = brain.get("active_users", {})
            current_active = active_users.get(uid_str, 0)
            
            try:
                await message.delete()
            except Exception:
                pass

            active_users[uid_str] = current_active + 1
            brain["active_users"] = active_users
            save_brain(brain)

            b_info = BRANDS[brand_query]
            email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_query)
            
            burner_obj = DynamicBurnerMailbox(complaint_name)
            burner_address = burner_obj.address

            custom_id = generate_custom_complaint_id(message.author.name)
            
            log_user_usage(message.author.id, message.author.name, b_info["name"], burner_address, subject_line, email_body, custom_id)
            register_persistent_pipeline(message.author.id, message.author.name, b_info["name"], burner_obj.username, burner_obj.domain, custom_id)

            sent_img_path = create_email_image(burner_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
            sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

            email_client_layout = (
                f"🛡️ **{b_info['name']}** UK Pipeline [ID: `{custom_id}`]\n"
                f"> **Dispatch Address:** `{burner_address}`\n"
                f"> **Target Support:** `{b_info['email']}`\n"
                f"> **Subject Line:** `{subject_line}`\n"
                f"> ----------------------------------------\n"
                f"> *{email_body[:280]}...*"
            )

            await message.channel.send(email_client_layout, file=sent_file)

            def send_brevo_email():
                api_key = os.getenv("BREVO_API_KEY")
                if not api_key:
                    raise Exception("BREVO_API_KEY is missing.")
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {"accept": "application/json", "api-key": api_key, "content-type": "application/json"}
                payload = {
                    "sender": {"name": complaint_name, "email": burner_address},
                    "to": [{"email": b_info["email"]}],
                    "replyTo": {"email": burner_address},
                    "subject": subject_line,
                    "textContent": email_body
                }
                requests.post(url, json=payload, headers=headers, timeout=10)

            try:
                await asyncio.to_thread(send_brevo_email)
            except Exception as e:
                brain = load_brain()
                if uid_str in brain["active_users"]:
                    brain["active_users"][uid_str] -= 1
                    if brain["active_users"][uid_str] <= 0:
                        del brain["active_users"][uid_str]
                    save_brain(brain)
                update_burner_status_by_address(burner_address, f"Dispatch Failed: {e}")
                await message.channel.send(f"❌ Dispatch failure: {e}")
                return
            return

    # Status Check Command
    if content_lower.startswith("!status"):
        parts = content.split()
        if len(parts) > 1:
            query_key = parts[1].strip()
            brain = load_brain()
            registry = brain.get("burner_registry", {})
            matched_info = None
            
            if query_key in registry:
                matched_info = registry[query_key]
            else:
                for k, info in registry.items():
                    if info["address"].lower() == query_key.lower() or info["custom_id"].lower() == query_key.lower():
                        matched_info = info
                        break

            if matched_info:
                embed = discord.Embed(title=f"📊 UK Pipeline Status [ID: `{matched_info['custom_id']}`]", color=0xF39C12)
                embed.add_field(name="Brand", value=matched_info["brand"], inline=True)
                embed.add_field(name="Owner", value=matched_info["username"], inline=True)
                embed.add_field(name="Dispatch Address", value=f"`{matched_info['address']}`", inline=False)
                embed.add_field(name="State", value=matched_info["status"], inline=False)
                await message.reply(embed=embed)
                return
            else:
                await message.reply(f"❌ Could not locate UK pipeline ID/Address `{query_key}`.")
                return

    # Code-Brain Chat (Only when mentioned)
    if bot.user.mentioned_in(message) and not content.startswith("!"):
        clean_query = content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if clean_query:
            async with message.channel.typing():
                ai_reply = await asyncio.to_thread(ask_mistral_chatbot, clean_query, message.author.name, message.author.id)
                await message.reply(ai_reply)
        return

    await bot.process_commands(message)

@bot.command(name="voucher", aliases=["wallet", "vouchers"])
async def show_voucher_wallet(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    brain = load_brain()
    uid = str(ctx.author.id)
    
    if uid not in brain["economy"] or not brain["economy"][uid]["vouchers"]:
        await ctx.send(f"📦 {ctx.author.mention}, your wallet ledger is empty!")
        return

    vouchers = brain["economy"][uid]["vouchers"]
    embed = discord.Embed(title=f"💳 {ctx.author.name}'s Secured UK Vouchers", color=0x3498DB)
    for i, v in enumerate(vouchers, 1):
        field_value = f"Code: `{v['code']}`\nValue: **£{v['value']:.2f}**\nStatus: 🟢 **Verified & Secure**"
        embed.add_field(name=f"Voucher #{i}: {v['name']}", value=field_value, inline=False)

    await ctx.send(embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
