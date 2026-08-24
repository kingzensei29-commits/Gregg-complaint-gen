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

# --- Encryption Core Setup (For brain.enc only) ---
def get_cipher():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key()
        print(f"⚠️ Warning: ENCRYPTION_KEY not found in environment. Generated temporary key: {key.decode()}")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def load_encrypted_json(filename, default_val=None):
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

def save_encrypted_json(filename, data):
    try:
        cipher = get_cipher()
        json_str = json.dumps(data, indent=4)
        encrypted_data = cipher.encrypt(json_str.encode("utf-8"))
        with open(filename, "wb") as f:
            f.write(encrypted_data)
    except Exception as e:
        print(f"❌ Critical Error saving/decrypting {filename}: {e}")

def load_plain_json(filename, default_val=None):
    if default_val is None:
        default_val = {}
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading plain JSON {filename}: {e}")
    return default_val

# --- Flask Web Server with Secured Brevo Inbound Webhook ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🟢 Fully Encrypted Pipeline Bot with Robust ID Lookup is online!"

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
                custom_id = matched_pipeline["custom_id"]
                
                requires_verification = any(term in email_body.lower() for term in ["verify", "phone", "sms", "code", "security check"])
                has_voucher = any(term in email_body.lower() for term in ["voucher", "gift card", "credit", "reward", "compensate", "compensation", "e-code", "promo"])

                if requires_verification:
                    update_burner_status(custom_id, "Awaiting Phone Verification (Vault Auto-Fetch)")
                    if bot.loop:
                        asyncio.run_coroutine_threadsafe(
                            notify_user_with_vault_phone(user_id, brand_name, subject, email_body),
                            bot.loop
                        )
                elif has_voucher:
                    update_burner_status(custom_id, "🎁 Voucher/Refund Received! Ready to Redeem")
                    update_pipeline_reply_snippet(custom_id, email_body[:300])
                    if bot.loop:
                        asyncio.run_coroutine_threadsafe(
                            deliver_support_reply_dm(user_id, brand_name, subject, email_body, is_voucher=True),
                            bot.loop
                        )
                    remove_persistent_pipeline(burner_address)
                else:
                    update_burner_status(custom_id, "Support Response Received (No Voucher yet)")
                    update_pipeline_reply_snippet(custom_id, email_body[:300])
                    remove_persistent_pipeline(burner_address)

        return jsonify({"status": "success", "processed": True}), 200
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

BRAIN_FILE = "brain.enc"
BRANDS_FILE = "brands.json"

BRANDS = load_plain_json(BRANDS_FILE, {})
print(f"✅ Loaded {len(BRANDS)} brands from {BRANDS_FILE}: {list(BRANDS.keys())}")

def load_brain():
    default_structure = {
        "active_users": {},
        "usage_stats": {},
        "burner_registry": {},
        "persistent_pipelines": {},
        "pending_phone_verifications": {},
        "user_phone_vault": {}
    }
    data = load_encrypted_json(BRAIN_FILE, default_structure)
    updated = False
    for key in default_structure:
        if key not in data:
            data[key] = default_structure[key]
            updated = True
    if updated:
        save_brain(data)
    return data

def save_brain(data):
    save_encrypted_json(BRAIN_FILE, data)

def generate_custom_complaint_id(username):
    clean_name = re.sub(r'[^a-zA-Z]', '', username).lower()
    if len(clean_name) < 4:
        clean_name = (clean_name + "user")[:4]
    else:
        clean_name = clean_name[:4]
    
    part1 = ''.join(random.choices("0123456789ABCDEF", k=4))
    part2 = ''.join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    return f"{clean_name}-{part1}-{part2}"

def find_pipeline_by_id(search_id):
    """Robust case-insensitive search across burner_registry and persistent_pipelines with fallback synchronization."""
    brain = load_brain()
    search_clean = search_id.strip().lower()
    
    # 1. Search in burner_registry (Primary source of truth for user IDs & custom IDs)
    registry = brain.get("burner_registry", {})
    for k, v in registry.items():
        if k.lower() == search_clean or v.get("custom_id", "").lower() == search_clean:
            return v.get("custom_id", k), v

    # 2. Search in persistent_pipelines and sync/fallback to registry if missing
    pipelines = brain.get("persistent_pipelines", {})
    for k, v in pipelines.items():
        if v.get("custom_id", "").lower() == search_clean or k.lower() == search_clean:
            custom_id = v.get("custom_id", search_id)
            burner_address = f"{v.get('burner_username')}@{v.get('burner_domain')}".lower()
            
            pipeline_data = {
                "custom_id": custom_id,
                "address": burner_address,
                "user_id": str(v.get("user_id")),
                "username": v.get("username", "Unknown"),
                "brand": v.get("brand_name", "Unknown"),
                "subject": "Formal Complaint & Compensation Request",
                "body_snippet": "Pipeline active and awaiting support response...",
                "reply_snippet": "No response yet",
                "status": "Active UK Pipeline Awaiting Voucher",
                "redeemed": False
            }
            
            if "burner_registry" not in brain:
                brain["burner_registry"] = {}
            brain["burner_registry"][custom_id] = pipeline_data
            save_brain(brain)
            
            return custom_id, pipeline_data
            
    return None, None

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
        if p_key == key or f"{p_data.get('burner_username')}@{p_data.get('burner_domain')}".lower() == key:
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
        "reply_snippet": "No response yet",
        "status": "Active UK Pipeline Awaiting Voucher",
        "redeemed": False
    }
    save_brain(brain)

def update_burner_status(custom_id, new_status):
    brain = load_brain()
    real_key, _ = find_pipeline_by_id(custom_id)
    if real_key:
        brain["burner_registry"][real_key]["status"] = new_status
        save_brain(brain)

def update_pipeline_reply_snippet(custom_id, reply_text):
    brain = load_brain()
    real_key, _ = find_pipeline_by_id(custom_id)
    if real_key:
        brain["burner_registry"][real_key]["reply_snippet"] = reply_text
        save_brain(brain)

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
                    f"📱 **Auto-Fetched Vault Phone:** `{vaulted_phone}`"
                )
            else:
                dm_text = (
                    f"🛡️ **Security Verification Triggered by {brand_name}!**\n"
                    f"Subject: *{subject}*\n\n"
                    f"> *Support says:* {body[:350]}...\n\n"
                    f"⚠️ No phone number found in your vault. Send `!setphone <number>` in chat to save one!"
                )
            await user.send(dm_text)
    except Exception as e:
        print(f"Failed to send vault notification DM: {e}")

async def deliver_support_reply_dm(user_id, brand_name, subject, body, is_voucher=False):
    try:
        user = await bot.fetch_user(user_id)
        if user and is_voucher:
            dm_text = (
                f"🎁 **Voucher / Refund Secured from {brand_name}!**\n"
                f"Subject: *{subject}*\n\n"
                f"> *Support Reply:* {body[:500]}...\n\n"
                f"*(Type `!redeem [your_gen_id]` in the server to claim and receive your secure voucher files).* "
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
        fallback_issue = f"I visited your {town} branch and experienced substandard service and ruined items."
        email_body = f"Dear Customer Support Team,\n\nMy name is {consistent_name}. I am writing regarding my recent experience at your {town} branch.\n\n{fallback_issue}\n\nGiven the severity of this issue and the distress caused, I expect a prompt goodwill voucher or full refund to make amends for this experience.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Formal Complaint & Compensation Request - {town}"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = (
        f"You are writing a formal customer complaint email for the brand '{b_data['name']}' regarding their branch in {town}. "
        f"STRICT DIRECTIVES:\n"
        f"1. Describe a realistic, frustrating customer service or product quality issue.\n"
        f"2. Write in a firm, polite, professional British English tone.\n"
        f"3. Explicitly demand a goodwill compensation voucher, credit, or full refund as a resolution for the distress caused.\n"
        f"4. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"5. The very first line must start with 'SUBJECT: ' followed by a strong complaint subject line."
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
            subject_line = f"Formal Complaint & Compensation Request - {town}"
            body_lines = lines
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
            return "\n".join(body_lines).strip(), consistent_name, town, subject_line
    except Exception:
        pass

    return f"Service complaint reported at {town}. Expecting a goodwill voucher.", consistent_name, town, "Formal Complaint & Compensation Request"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Robust Case-Insensitive Pipeline & Redemption Active.")

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

        # 📊 Advanced Pipeline Pic Lookup Command: !pic [custom_id]
        if content_lower.startswith("!pic"):
            parts = content.split(" ", 1)
            if len(parts) < 2:
                await message.reply("⚠️ Please provide your Generation ID (e.g., `!pic shar-1A2B-C3D4`).")
                return
            
            search_id = parts[1].strip()
            real_key, pipeline_info = find_pipeline_by_id(search_id)

            if not pipeline_info:
                await message.reply(f"❌ No pipeline found matching ID: `{search_id}`.")
                return

            def create_advanced_status_card():
                width, height = 900, 600
                image = Image.new("RGB", (width, height), color="#1E1E24")
                draw = ImageDraw.Draw(image)
                
                try:
                    font_header = ImageFont.truetype("arial.ttf", 20)
                    font_bold = ImageFont.truetype("arial.ttf", 14)
                    font_regular = ImageFont.truetype("arial.ttf", 13)
                except IOError:
                    font_header = ImageFont.load_default()
                    font_bold = ImageFont.load_default()
                    font_regular = ImageFont.load_default()

                # Header Banner
                draw.rectangle([(0, 0), (width, 80)], fill="#2F3136")
                draw.text((30, 25), f"UK Pipeline Status Dashboard [{real_key}]", fill="#00FFCC", font=font_header)

                # Status Box
                status_color = "#FFA500" if "Awaiting" in pipeline_info['status'] else "#00FF66"
                draw.rectangle([(30, 100), (width - 30, 160)], fill="#2D2F35", outline="#40444B", width=2)
                draw.text((50, 110), "Current Pipeline Status:", fill="#8E9297", font=font_bold)
                draw.text((50, 130), pipeline_info['status'], fill=status_color, font=font_header)

                # Metadata Section
                draw.text((30, 190), f"Brand Target: {pipeline_info['brand']}", fill="#FFFFFF", font=font_bold)
                draw.text((30, 215), f"Burner Address: {pipeline_info['address']}", fill="#B9BBBE", font=font_regular)
                draw.text((30, 240), f"Subject: {pipeline_info['subject']}", fill="#B9BBBE", font=font_regular)

                # Initial Complaint Snippet Box
                draw.rectangle([(30, 280), (width - 30, 420)], fill="#25272C", outline="#36393F", width=1)
                draw.text((45, 290), "Dispatched Complaint Snippet:", fill="#00B0F4", font=font_bold)
                y_text = 315
                for line in pipeline_info['body_snippet'].splitlines():
                    if y_text > 400:
                        break
                    draw.text((45, y_text), line, fill="#DCDDDE", font=font_regular)
                    y_text = y_text + 18

                # Support Reply / Voucher Box
                draw.rectangle([(30, 440), (width - 30, 570)], fill="#25272C", outline="#36393F", width=1)
                draw.text((45, 450), "Latest Support Reply & Voucher Status:", fill="#FF5555" if "No response" in pipeline_info['reply_snippet'] else "#55FF55", font=font_bold)
                y_text = 475
                for line in pipeline_info['reply_snippet'].splitlines():
                    if y_text > 550:
                        break
                    draw.text((45, y_text), line, fill="#DCDDDE", font=font_regular)
                    y_text = y_text + 18

                path = f"status_{real_key}.png"
                image.save(path)
                return path

            img_path = await asyncio.to_thread(create_advanced_status_card)
            card_file = discord.File(img_path, filename="pipeline_status.png")

            await message.channel.send(
                f"📊 **Advanced Pipeline Diagnostic for ID:** `{real_key}`\n"
                f"> **Status:** {pipeline_info['status']}",
                file=card_file
            )
            return

        # 🎁 Secure Redemption Command: !redeem [custom_id]
        if content_lower.startswith("!redeem"):
            parts = content.split(" ", 1)
            if len(parts) < 2:
                await message.reply("⚠️ Please provide your Generation ID to redeem (e.g., `!redeem shar-1A2B-C3D4`).")
                return

            search_id = parts[1].strip()
            real_key, pipeline_info = find_pipeline_by_id(search_id)

            if not pipeline_info:
                await message.reply(f"❌ No pipeline found matching ID: `{search_id}`.")
                return

            if pipeline_info["user_id"] != str(message.author.id):
                await message.reply("⛔ **Access Denied:** You are not the authorized creator of this pipeline ID.")
                return

            if "Voucher" not in pipeline_info["status"] and "🎁" not in pipeline_info["status"]:
                await message.reply("⚠️ This pipeline has not yet received a confirmed voucher or financial remedy from support.")
                return

            if pipeline_info.get("redeemed", False):
                await message.reply("⚠️ This voucher has already been successfully redeemed and claimed.")
                return

            brain = load_brain()
            if real_key in brain.get("burner_registry", {}):
                brain["burner_registry"][real_key]["redeemed"] = True
                save_brain(brain)

            def create_redemption_card():
                width, height = 900, 500
                image = Image.new("RGB", (width, height), color="#121216")
                draw = ImageDraw.Draw(image)
                
                try:
                    font_header = ImageFont.truetype("arial.ttf", 22)
                    font_bold = ImageFont.truetype("arial.ttf", 14)
                    font_regular = ImageFont.truetype("arial.ttf", 13)
                except IOError:
                    font_header = ImageFont.load_default()
                    font_bold = ImageFont.load_default()
                    font_regular = ImageFont.load_default()

                draw.rectangle([(0, 0), (width, 80)], fill="#1F2421")
                draw.text((30, 25), f"🎁 Verified Voucher & Compensation Claim [{real_key}]", fill="#00FF99", font=font_header)

                draw.text((30, 110), f"Brand: {pipeline_info['brand']}", fill="#FFFFFF", font=font_bold)
                draw.text((30, 135), f"Owner Discord ID: {message.author.id} (Verified)", fill="#8E9297", font=font_regular)

                draw.rectangle([(30, 175), (width - 30, 450)], fill="#1B1D23", outline="#2E3136", width=2)
                draw.text((45, 190), "Secured Support Voucher / Resolution Payload:", fill="#00D26A", font=font_bold)
                
                y_text = 225
                for line in pipeline_info['reply_snippet'].splitlines():
                    if y_text > 420:
                        break
                    draw.text((45, y_text), line, fill="#E2E8F0", font=font_regular)
                    y_text = y_text + 18

                path = f"redeemed_{real_key}.png"
                image.save(path)
                return path

            redeem_img_path = await asyncio.to_thread(create_redemption_card)
            redeem_file = discord.File(redeem_img_path, filename="verified_voucher.png")

            try:
                dm_channel = await message.author.create_dm()
                await dm_channel.send(
                    f"🎉 **Your Voucher has been successfully verified and claimed!**\n"
                    f"> **Generation ID:** `{real_key}`\n"
                    f"> **Brand:** `{pipeline_info['brand']}`\n\n"
                    f"Here is your official secure voucher card and text payload:",
                    file=redeem_file
                )
                await message.reply(f"✅ **Identity Verified!** Your voucher has been securely dispatched to your DMs with the full confirmation card.")
            except Exception as e:
                await message.reply(f"✅ **Identity Verified!** However, I couldn't send you a DM (please check your privacy settings). Here is your voucher file directly in the channel:", file=redeem_file)
            return

        # Matches format: !<brandname> gen
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
                    draw.text((20, 20), f"Official UK Grievance Dispatched [ID: {custom_id}]", fill="white", font=font_title)
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
                    f"🛡️ **{b_info['name']}** Pipeline Dispatched Successfully!\n"
                    f"> **Generation ID:** `{custom_id}` *(Use `!pic {custom_id}` to check status)*\n"
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
                    update_burner_status(custom_id, f"Dispatch Failed: {e}")
                    await message.channel.send(f"❌ Dispatch failure: {e}")
                    return
                return

        await bot.process_commands(message)
    except Exception as e:
        print(f"❌ Exception in on_message: {e}")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server, daemon=True)
        server_thread.start()
        bot.run(TOKEN)
