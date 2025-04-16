import os
import re
import requests
import instaloader
import telebot
import sys
from dotenv import load_dotenv

# Load only the Telegram bot token
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Setup Instaloader
SESSION_FILE = "ig_session"
L = instaloader.Instaloader(
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    post_metadata_txt_pattern="",
    filename_pattern="{shortcode}"
)

# Login or load existing session
def login_instagram():
    if os.path.exists(SESSION_FILE):
        try:
            L.load_session_from_file(username=None, filename=SESSION_FILE)
            print("✅ Logged in using existing session.")
            return
        except Exception as e:
            print(f"⚠️ Failed to load session. Reason: {e}")
    
    print("🔐 Instagram Login Required")
    try:
        ig_username = input("📥 Instagram Username: ").strip()
        ig_password = input("🔑 Instagram Password: ").strip()
        L.login(ig_username, ig_password)
        L.save_session_to_file(SESSION_FILE)
        print("✅ Logged in and session saved.")
    except Exception as e:
        print(f"❌ Login failed. Please check your credentials.\nError: {e}")
        exit(1)

# Extract shortcode
def extract_shortcode(url):
    match = re.search(r"instagram\.com/(?:reel|p|tv)/([^/?#&]+)", url)
    return match.group(1) if match else None

# Fetch post
def fetch_post(shortcode):
    return instaloader.Post.from_shortcode(L.context, shortcode)

# Send media
def send_media(chat_id, media_url, is_video):
    action = 'upload_video' if is_video else 'upload_photo'
    bot.send_chat_action(chat_id, action)

    r = requests.get(media_url, stream=True)
    if r.status_code == 200:
        media = r.content
        if is_video:
            bot.send_video(chat_id, media)
        else:
            bot.send_photo(chat_id, media)
    else:
        bot.send_message(chat_id, "⚠️ Failed to fetch media.")

# /start
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, """
👋 Welcome to the InstaHive Bot!

📥 Send me any public Instagram Reel, Post, or Video:
🔗 https://www.instagram.com/reel/shortcode/

I'll send:
✅ Cover image
✅ Post media (video/photo)
✅ Post details

🔧 Built by @imraj569  
🔗 GitHub: https://github.com/imraj569
""")

# /privacy
@bot.message_handler(commands=['privacy'])
def privacy_command(message):
    privacy_text = """
🔐 <b>Privacy Policy</b>

📁 <b>No Storage of Personal Data:</b>  
🕒 All processing happens in real-time. No messages, links, or media are stored on any server.

🔑 <b>No Credential Collection:</b>  
🙅‍♂️ This bot will never ask for your Instagram username or password.

💬 <b>Message Privacy:</b>  
📎 Only Instagram links are processed. All other messages are ignored automatically.

🛡️ We care about your privacy. By using this bot, you agree to these simple, user-first principles.
"""
    bot.send_message(message.chat.id, privacy_text, parse_mode="HTML", disable_web_page_preview=True)


# Handle Instagram links
@bot.message_handler(func=lambda msg: True)
def handle_instagram_url(message):
    url = message.text.strip()
    shortcode = extract_shortcode(url)

    if not shortcode:
        bot.reply_to(message, "❌ Invalid Instagram URL. Please send a valid /p/, /reel/, or /tv/ link.")
        return

    bot.send_chat_action(message.chat.id, 'typing')

    try:
        post = fetch_post(shortcode)

        # Send cover
        bot.send_chat_action(message.chat.id, 'upload_photo')
        r = requests.get(post.url)
        if r.status_code == 200:
            bot.send_photo(message.chat.id, r.content, caption="🖼 Cover image")

        # Post details
        caption = post.caption or "No caption"
        details = f"""📄 <b>Post Details</b>
👤 <b>User:</b> @{post.owner_username}
❤️ <b>Likes:</b> {post.likes}
📝 <b>Caption:</b> {caption[:200]}{'...' if len(caption) > 200 else ''}
🔗 <a href="{url}">View on Instagram</a>"""
        bot.send_message(message.chat.id, details, parse_mode="HTML", disable_web_page_preview=False)

        # Media
        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                media_url = node.video_url if node.is_video else node.display_url
                send_media(message.chat.id, media_url, node.is_video)
        else:
            media_url = post.video_url if post.is_video else post.url
            send_media(message.chat.id, media_url, post.is_video)

    except Exception as e:
        print(f"⚠️ Error processing request: {str(e)}")  # Log error to console
        maintenance_msg = """🔧 Maintenance Notice

Sorry, we're experiencing technical difficulties. 
Our team is working to fix this issue ASAP.

Please try again later. 
If the problem persists, contact @imraj569"""
        bot.reply_to(message, maintenance_msg)

# Run bot
if __name__ == "__main__":
    os.system("clear")
    login_instagram()
    print("🤖 Bot is running... by @imraj569")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"⚠️ Bot crashed: {e}")
        print("⏳ Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)