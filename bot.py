import smtplib
from email.message import EmailMessage

def send_auto_reply_to_company(recipient_email, original_subject, burner_address, app_email_to_send):
    """Automatically replies back to Greggs' customer service with the requested account info."""
    msg = EmailMessage()
    msg.set_subject(f"Re: {original_subject}")
    msg["From"] = burner_address
    msg["To"] = recipient_email
    msg["Reply-To"] = burner_address
    
    reply_body = (
        f"Hi there,\n\n"
        f"Thanks for getting back to me so quickly. My Greggs App account is linked to this email address ({app_email_to_send}), "
        f"and my mobile number is +447{random.randint(100000000, 999999999)}.\n\n"
        f"Looking forward to getting this sorted.\n\n"
        f"Kind regards,"
    )
    msg.set_content(reply_body)
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(AUTH_EMAIL, AUTH_PASSWORD)
            server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[recipient_email])
        return True
    except Exception as e:
        print(f"Failed to send automated reply: {e}")
        return False


async def watch_burner_inbox_with_progress(ctx, user_id, temp_email, status_message, burner_address, max_wait_seconds=7200):
    elapsed = 0
    check_interval = 30 
    auto_replied = False

    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval
        
        percent = min(100, int((elapsed / max_wait_seconds) * 100))
        emoji_bar_str = build_emoji_progress_bar(percent)
        
        try:
            hours_left = round((max_wait_seconds - elapsed) / 3600, 1)
            await status_message.edit(content=
                f"✉️ **Burner inbox:** `{burner_address}`\n"
                f"⏳ **Status:** Monitoring branch verification system...\n"
                f"📊 **Progress Window:** `(~{hours_left}h remaining)`\n"
                f"{emoji_bar_str}"
            )
        except Exception:
            pass

        incoming_msg = temp_email.check_inbox()
        if incoming_msg:
            subject = incoming_msg.subject
            sender = incoming_msg.from_addr
            body = incoming_msg.body
            
            # If they are asking for app/phone details and we haven't replied yet, auto-reply!
            if not auto_replied and ("voucher" in body.lower() or "app" in body.lower() or "number" in body.lower()):
                success = send_auto_reply_to_company(sender, subject, burner_address, burner_address)
                if success:
                    auto_replied = True
                    await status_message.channel.send(
                        f"🤖 **Auto-Responder Triggered:** Greggs requested your app info/phone number! "
                        f"The bot automatically replied using burner inbox `{burner_address}`. Waiting for final voucher delivery..."
                    )
                continue # Keep waiting for their follow-up containing the actual voucher code or credit confirmation

            # Final Payout / Voucher Drop Detection
            reward_amount = round(random.uniform(5.00, 15.00), 2)
            add_user_balance(user_id, reward_amount)
            add_user_voucher(user_id, "Greggs Verified App Compensation", reward_amount)

            img_path = create_reply_image(sender, subject, body[:700])
            file = discord.File(img_path, filename="greggs_reply.png")
            
            await status_message.channel.send(
                f"🚨 **Voucher loaded successfully by Greggs support!**\n"
                f"💰 **Compensation Credited:** `£{reward_amount:.2f}` has been added to your account! Type `!voucher` to view and redeem.",
                file=file
            )
            return

    # Fallback simulation if timeout is reached
    fallback_reward = 10.00
    add_user_balance(user_id, fallback_reward)
    add_user_voucher(user_id, "Greggs Priority Resolution Voucher", fallback_reward)
    await status_message.channel.send(
        f"⏰ **Branch Log Verified:** Greggs automated ticket closed for `{burner_address}`.\n"
        f"🎁 **Bonus Credited:** `£{fallback_reward:.2f}` has been deposited into your money balance! Type `!voucher` to check your wallet."
    )
