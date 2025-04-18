import os
import re
import requests
import instaloader
import telebot
import sys
from dotenv import load_dotenv
import tempfile,psutil

# Cross-platform single instance lock
def single_instance_lock():
    lock_file = os.path.join(tempfile.gettempdir(), "instahive.lock")
    
    # Check for existing lock
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read())
                if psutil.pid_exists(old_pid):
                    print(f"⚠️ Terminating existing instance with PID {old_pid}")
                    os.kill(old_pid, 9)
        except Exception as e:
            print(f"⚠️ Error handling existing lock: {e}")
    
    # Create new lock
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    
    # Add cleanup handler
    def cleanup():
        try:
            os.remove(lock_file)
        except:
            pass
    
    import atexit
    atexit.register(cleanup)

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


def send_media(chat_id, media_url, is_video):
    action = 'upload_video' if is_video else 'upload_photo'
    bot.send_chat_action(chat_id, action)

    try:
        # Download media with timeout
        with requests.get(media_url, stream=True, timeout=(5, 30)) as r:  # 5s connect, 30s read
            if r.status_code != 200:
                bot.send_message(chat_id, "⚠️ Failed to fetch media.")
                return

            # Save to temp file
            suffix = '.mp4' if is_video else '.jpg'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                temp_path = f.name

        # Send with increased timeout
        with open(temp_path, 'rb') as file:
            if is_video:
                bot.send_video(chat_id, file, timeout=60)  # 60 seconds timeout
            else:
                bot.send_photo(chat_id, file, timeout=60)

        # Cleanup
        os.unlink(temp_path)

    except requests.exceptions.Timeout:
        bot.send_message(chat_id, "⌛ Media download timed out. Please try again.")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Error: {str(e)}")

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

        # Post details (removed inline caption preview)
        details = f"""📄 <b>Post Details</b>
👤 <b>User:</b> @{post.owner_username}
❤️ <b>Likes:</b> {post.likes}
🔗 <a href="{url}">View on Instagram</a>"""
        bot.send_message(message.chat.id, details, parse_mode="HTML", disable_web_page_preview=False)

        # ✨ Copyable caption
        caption = post.caption or "No caption"
        bot.send_message(message.chat.id, f"📝 <b>Full Caption:</b>\n<code>{caption.strip()}</code>", parse_mode="HTML")

       
        # Media
        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                media_url = node.video_url if node.is_video else node.display_url
                send_media(message.chat.id, media_url, node.is_video)
        else:
            media_url = post.video_url if post.is_video else post.url
            send_media(message.chat.id, media_url, post.is_video)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# Run bot
if __name__ == "__main__":
    single_instance_lock()  # Add this line before starting
    
    login_instagram()
    print("🤖 Bot is running... by @imraj569")
    
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"⚠️ Bot crashed: {e}")
        print("⏳ Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)
