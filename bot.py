import os
import random
import asyncio
import threading
import json
import re
import requests
from flask import Flask, request, jsonify
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont
from cryptography.fernet import Fernet

# --- Encryption Core Setup ---
def get_cipher():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key()
        print(f"⚠️ Warning: ENCRYPTION_KEY not found in environment. Generated temporary key: {key.decode()}")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def load_json_file(filename, default_val=None):
    if default_val is None:
        default_val = {}
    if os.path.exists(filename):
        try:
            with open(filename, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return default_val
            cipher = get_cipher()
            decrypted_data = cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode("utf-8"))
        except Exception as e:
            print(f"Error loading/decrypting {filename}: {e}")
    return default_val

def save_json_file(filename, data):
    try:
        cipher = get_cipher()
        json_str = json.dumps(data, indent=4)
        encrypted_data = cipher.encrypt(json_str.encode("utf-8"))
        with open(filename, "wb") as f:
            f.write(encrypted_data)
    except Exception as e:
        print(f"❌ Critical Error saving/encrypting {filename}: {e}")

# --- Flask Web Server with Secured Brevo Inbound Webhook ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🟢 Fully Encrypted Pipeline Bot with Voucher-Only Filter is online!"

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
                
                # Check for phone/security verification triggers first
                requires_verification = any(term in email_body.lower() for term in ["verify", "phone", "sms", "code", "security check"])
                
                # Check if the support reply includes a voucher, gift card, credit, or compensation
                has_voucher = any(term in email_body.lower() for term in ["voucher", "gift card", "credit", "reward", "compensate", "compensation", "e-code", "promo"])

                if requires_verification:
                    update_burner_status_by_address(burner_address, "Awaiting Phone Verification (Vault Auto-Fetch)")
                    if bot.loop:
                        asyncio.run_coroutine_threadsafe(
                            notify_user_with_vault_phone(user_id, brand_name, subject, email_body),
                            bot.loop
                        )
                elif has_voucher:
                    update_burner_status_by_address(burner_address, "Voucher Received - User Notified")
                    if bot.loop:
                        asyncio.run_coroutine_threadsafe(
                            deliver_support_reply_dm(user_id, brand_name, subject, email_body, attachments, is_voucher=True),
                            bot.loop
                        )
                    remove_persistent_pipeline(burner_address)
                else:
                    # Regular support response without a voucher — silently close pipeline without DMing user
                    update_burner_status_by_address(burner_address, "Support response received (No voucher, skipped DM)")
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

BRAIN_FILE = "brain.enc"
BRANDS_FILE = "brands.json"

BRANDS = load_json_file(BRANDS_FILE, {})

def load_brain():
    default_structure = {
        "active_users": {},
        "usage_stats": {},
        "burner_registry": {},
        "persistent_pipelines": {},
        "pending_phone_verifications": {},
        "user_phone_vault": {}
    }
    data = load_json_file(BRAIN_FILE, default_structure)
    updated = False
    for key in default_structure:
        if key not in data:
            data[key] = default_structure[key]
            updated = True
    if updated:
        save_brain(data)
    return data

def save_brain(data):
    save_json_file(BRAIN_FILE, data)

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

async def notify_user_with_vault_phone(user_id, brand_name, subject, body):
    try:
        user = await bot.fetch_user(user_id)
        if user:
            brain = load_brain()
            uid_str = str(user_id)
            vaulted_phone = brain.get("user_phone_vault", {}).get(uid_str, None)

            if vaulted_phone:
                dm_text = (
                    f"🛡️ **Security Verification Triggered by {brand_name}!**\n"
                    f"Subject: *{subject}*\n\n"
                    f"> *Support says:* {body[:350]}...\n\n"
                    f"📱 **Auto-Fetched Vault Phone:** `{vaulted_phone}`\n"
                    f"*(Use this saved number to complete the verification challenge on their portal).* "
                )
            else:
                dm_text = (
                    f"🛡️ **Security Verification Triggered by {brand_name}!**\n"
                    f"Subject: *{subject}*\n\n"
                    f"> *Support says:* {body[:350]}...\n\n"
                    f"⚠️ No phone number found in your vault. Send `!setphone <number>` in chat to save one for future pipelines!"
                )
            await user.send(dm_text)
    except Exception as e:
        print(f"Failed to send vault notification DM: {e}")

async def deliver_support_reply_dm(user_id, brand_name, subject, body, attachments, is_voucher=False):
    try:
        user = await bot.fetch_user(user_id)
        if user and is_voucher:
            dm_text = (
                f"🎁 **Voucher / Reward Received from {brand_name}!**\n"
                f"Subject: *{subject}*\n\n"
                f"> *Snippet:* {body[:500]}...\n\n"
                f"*(Pipeline has been automatically closed).* "
            )
            await user.send(dm_text)
    except Exception as e:
        print(f"Failed to deliver secure voucher DM: {e}")

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
        fallback_issue = f"I visited your {town} branch and experienced issues with service."
        email_body = f"Dear Customer Support Team,\n\nMy name is {consistent_name}. I am writing regarding my recent experience at your {town} branch.\n\n{fallback_issue}\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Feedback regarding {town} branch"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = (
        f"You are writing a formal customer feedback email for the brand '{b_data['name']}' regarding their branch in {town}. "
        f"STRICT DIRECTIVES:\n"
        f"1. Describe a realistic customer service or product issue.\n"
        f"2. Write in a polite, professional British English tone.\n"
        f"3. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"4. The very first line must start with 'SUBJECT: ' followed by a custom subject line."
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 400
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            lines = content.splitlines()
            subject_line = f"Feedback regarding your {town} branch"
            body_lines = lines
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
            return "\n".join(body_lines).strip(), consistent_name, town, subject_line
    except Exception:
        pass

    return f"Service feedback reported at {town}.", consistent_name, town, "Feedback regarding service"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Voucher-Only Pipeline Listener Active.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"❌ Error in command {ctx.command}: {error}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    try:
        content = message.content.strip()
        content_lower = content.lower()

        if content_lower.startswith("!setphone"):
            parts = content.split(" ", 1)
            if len(parts) > 1:
                phone_val = parts[1].strip()
                if len(phone_val) >= 10:
                    brain = load_brain()
                    uid_str = str(message.author.id)
                    if "user_phone_vault" not in brain:
                        brain["user_phone_vault"] = {}
                    brain["user_phone_vault"][uid_str] = phone_val
                    save_brain(brain)
                    
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    
                    await message.channel.send(f"🔒 **Phone number securely saved to your encrypted vault!**", delete_after=10)
                    return
                else:
                    await message.reply("⚠️ Please provide a valid full phone number (e.g., `!setphone +447123456789`).")
                    return

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

                def create_simple_email_img():
                    width, height = 800, 540
                    image = Image.new("RGB", (width, height), color="#FFF3E0")
                    draw = ImageDraw.Draw(image)
                    try:
                        font_title = ImageFont.truetype("arial.ttf", 18)
                        font_body = ImageFont.truetype("arial.ttf", 12)
                    except IOError:
                        font_title = ImageFont.load_default()
                        font_body = ImageFont.load_default()

                    draw.rectangle([(0, 0), (width, 70)], fill=b_info["color"])
                    draw.text((20, 20), "Official UK Grievance Dispatched", fill="white", font=font_title)
                    content_text = f"From: {burner_address}\nTo: {b_info['email']}\nSubject: {subject_line}\n" + "-" * 68 + f"\n\n{email_body}"
                    
                    y_text = 85
                    for line in content_text.splitlines():
                        if y_text > height - 25:
                            break
                        draw.text((20, y_text), line, fill="#222222", font=font_body)
                        y_text += 17
                    path = "sent_complaint.png"
                    image.save(path)
                    return path

                sent_img_path = await asyncio.to_thread(create_simple_email_img)
                sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

                email_client_layout = (
                    f"🛡️ **{b_info['name']}** Pipeline [ID: `{custom_id}`]\n"
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

        await bot.process_commands(message)
    except Exception as e:
        print(f"❌ Exception in on_message: {e}")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
