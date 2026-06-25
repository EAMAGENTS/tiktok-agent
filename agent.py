import os, json, requests, subprocess, tempfile, re
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import anthropic
from gtts import gTTS

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ─── 1. PRODUITS TRENDING ─────────────────────────────────────────────────────
def get_trending_products():
    print("🔍 Recherche produits trending...")
    return [
        {"name": "Lampe LED USB rechargeable portable", "price": "8.99€", "url": "https://fr.aliexpress.com/w/wholesale-led-usb-lamp.html"},
        {"name": "Montre connectée sport waterproof", "price": "15.99€", "url": "https://fr.aliexpress.com/w/wholesale-smart-watch.html"},
        {"name": "Écouteurs sans fil Bluetooth 5.0", "price": "12.99€", "url": "https://fr.aliexpress.com/w/wholesale-bluetooth-earphones.html"},
        {"name": "Mini aspirateur de bureau USB", "price": "6.99€", "url": "https://fr.aliexpress.com/w/wholesale-mini-vacuum.html"},
        {"name": "Support téléphone voiture magnétique", "price": "4.99€", "url": "https://fr.aliexpress.com/w/wholesale-car-phone-holder.html"},
    ]

# ─── 2. SCRIPT IA ─────────────────────────────────────────────────────────────
def select_product_and_write_script(products):
    print("🧠 Claude génère le script...")
    prompt = f"""Tu es expert TikTok viral. Voici des produits :
{json.dumps(products, ensure_ascii=False)}

Choisis le meilleur produit et écris un script vidéo TikTok de 30 secondes en français.
IMPORTANT : Le script doit être du TEXTE PUR à lire à voix haute, SANS aucune indication scénique, SANS parenthèses, SANS marqueurs de temps.

Réponds UNIQUEMENT en JSON :
{{
  "product": {{"name": "...", "price": "...", "url": "..."}},
  "script": "texte pur à lire, sans aucune annotation, 60 à 80 mots",
  "angle": "angle marketing en une phrase courte",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = re.sub(r'```json|```', '', response.content[0].text).strip()
    return json.loads(text)

# ─── 3. VOIX OFF gTTS ─────────────────────────────────────────────────────────
def generate_voiceover(script_text, output_path):
    print("🎙️ Génération voix off (gTTS)...")
    clean = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', script_text)
    clean = re.sub(r'\d+\s*[-–:]\s*\d+\s*s', '', clean)
    clean = clean.replace('"', '').strip()
    if len(clean) < 10:
        print("❌ Script trop court")
        return False
    tts = gTTS(text=clean, lang='fr', slow=False)
    tts.save(output_path)
    # Validation
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"✅ Audio OK ({os.path.getsize(output_path)} bytes)")
        return True
    print("❌ Audio invalide")
    return False

# ─── 4. CRÉATION IMAGE FFmpeg ─────────────────────────────────────────────────
def create_background(product_name, product_price, image_path):
    print("🖼️ Création image fond...")
    # Fond noir avec texte produit (couleur via lavfi)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s=1080x1920:d=1",
        "-frames:v", "1",
        image_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(image_path):
        print(f"✅ Image OK")
        return True
    print(f"❌ Erreur image : {result.stderr[-200:]}")
    return False

# ─── 5. MONTAGE VIDÉO FFmpeg ──────────────────────────────────────────────────
def create_video(image_path, audio_path, output_path):
    print("🎬 Montage vidéo...")
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
    try:
        duration = float(duration_result.stdout.strip())
    except:
        duration = 30.0
    print(f"   Durée audio : {duration:.1f}s")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "30", "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    print(f"

# ─── 6. UPLOAD CLOUDINARY ─────────────────────────────────────────────────────
def upload_to_cloudinary(video_path):
    print("☁️ Upload Cloudinary...")
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(url=os.getenv("CLOUDINARY_URL"))
        upload = cloudinary.uploader.upload_large(
            video_path,
            resource_type="video",
            folder="tiktok-agent",
            chunk_size=6000000
        )
        url = upload["secure_url"]
        print(f"✅ Vidéo en ligne : {url}")
        return url
    except Exception as e:
        print(f"❌ Cloudinary échoué : {e}")
        return None

# ─── PIPELINE ─────────────────────────────────────────────────────────────────
def run_agent():
    print("\n🚀 AGENT TIKTOK\n" + "="*40)
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Produits
        products = get_trending_products()

        # 2. Script
        data = select_product_and_write_script(products)
        product = data["product"]
        print(f"✅ Produit : {product['name']}")

        # 3. Audio
        audio_path = f"{tmpdir}/voix.mp3"
        if not generate_voiceover(data["script"], audio_path):
            print("⛔ ARRÊT : audio invalide")
            return

        # 4. Image
        image_path = f"{tmpdir}/bg.png"
        if not create_background(product["name"], product["price"], image_path):
            print("⛔ ARRÊT : image invalide")
            return

        # 5. Vidéo
        video_path = f"{tmpdir}/video.mp4"
        if not create_video(image_path, audio_path, video_path):
            print("⛔ ARRÊT : vidéo invalide")
            return

        # 6. Upload
        video_url = upload_to_cloudinary(video_path)
        if not video_url:
            print("⛔ ARRÊT : upload échoué")
            return

        # 7. Résultat final
        hashtags = " ".join(data["hashtags"])
        description = f"{data['angle']} 🔥 Lien en bio ! {hashtags}"
        print("\n" + "="*40)
        print(f"✅ CYCLE COMPLET RÉUSSI")
        print(f"📦 Produit : {product['name']} ({product['price']})")
        print(f"🌐 Vidéo : {video_url}")
        print(f"📱 Description : {description}")
        print("="*40)

if __name__ == "__main__":
    run_agent()