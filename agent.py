import os, json, requests, subprocess, tempfile, re
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import anthropic

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ─── ÉTAPE 1 : PRODUITS TRENDING ─────────────────────────────────────────────
def get_trending_products():
    print("🔍 Recherche produits trending...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        r = requests.get("https://www.aliexpress.com/bestselling/", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        products = []
        for item in soup.select("a[href*='/item/']")[:15]:
            name = item.get_text(strip=True)[:80]
            if len(name) > 10:
                url = "https:" + item["href"] if item["href"].startswith("//") else item["href"]
                products.append({"name": name, "price": "Prix AliExpress", "image_url": "", "url": url})
        if products:
            return products[:10]
    except Exception as e:
        print(f"⚠️ Scraping échoué : {e}")

    # Fallback fiable — produits trending connus
    print("⚠️ Utilisation liste fallback trending")
    return [
        {"name": "Lampe LED USB rechargeable portable", "price": "8.99€", "image_url": "", "url": "https://fr.aliexpress.com/w/wholesale-led-usb-lamp.html"},
        {"name": "Montre connectée sport waterproof", "price": "15.99€", "image_url": "", "url": "https://fr.aliexpress.com/w/wholesale-smart-watch.html"},
        {"name": "Écouteurs sans fil Bluetooth 5.0", "price": "12.99€", "image_url": "", "url": "https://fr.aliexpress.com/w/wholesale-bluetooth-earphones.html"},
        {"name": "Mini aspirateur de bureau USB", "price": "6.99€", "image_url": "", "url": "https://fr.aliexpress.com/w/wholesale-mini-vacuum.html"},
        {"name": "Support téléphone voiture magnétique", "price": "4.99€", "image_url": "", "url": "https://fr.aliexpress.com/w/wholesale-car-phone-holder.html"},
    ]

# ─── ÉTAPE 2 : SÉLECTION & SCRIPT IA ─────────────────────────────────────────
def select_product_and_write_script(products):
    print("🧠 Claude sélectionne le produit et écrit le script...")
    prompt = f"""Tu es un expert en marketing TikTok viral.
Voici une liste de produits AliExpress :
{json.dumps(products, ensure_ascii=False, indent=2)}

1. Choisis le produit avec le meilleur potentiel viral TikTok.
2. Écris un script vidéo de 30 secondes en français, ultra-accrocheur.
Format : accroche choc (3s) | problème/solution (15s) | démonstration (8s) | CTA urgent (4s).
3. Génère 5 hashtags viraux français.

Réponds UNIQUEMENT en JSON valide sans markdown :
{{
  "product": {{"name": "...", "price": "...", "url": "...", "image_url": ""}},
  "script": "texte complet du script",
  "angle": "angle marketing",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = re.sub(r'```json|```', '', response.content[0].text).strip()
    return json.loads(text)

# ─── ÉTAPE 3 : VOIX OFF ───────────────────────────────────────────────────────
def generate_voiceover(script_text, output_path):
    print("🎙️ Génération voix off...")
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "tts-1",
        "input": script_text,
        "voice": "nova",
        "speed": 1.0
    }
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(r.content)
        print(f"✅ Audio généré")
        return True
    else:
        print(f"⚠️ OpenAI TTS indisponible (429), création audio muet...")
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "35", "-q:a", "9", "-acodec", "libmp3lame", "-y", output_path
        ], capture_output=True)
        return False

# ─── ÉTAPE 4 : IMAGE PRODUIT ──────────────────────────────────────────────────
def download_image(image_url, output_path):
    print("🖼️ Préparation image...")
    try:
        if image_url and image_url.startswith("http"):
            r = requests.get(image_url, timeout=10)
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    # Fond dégradé noir si pas d'image
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "color=c=black:size=1080x1920:rate=30",
        "-t", "35", "-y", output_path
    ], capture_output=True)
    return False

# ─── ÉTAPE 5 : MONTAGE VIDÉO ─────────────────────────────────────────────────
def create_video(image_path, audio_path, product_name, product_price, output_path):
    print("🎬 Montage FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Vidéo créée")
    else:
        print(f"❌ FFmpeg erreur : {result.stderr[-300:]}")

# ─── ÉTAPE 6 : TIKTOK TOKEN ───────────────────────────────────────────────────
def get_tiktok_token():
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type": "client_credentials"
    })
    token = r.json().get("access_token", "")
    if token:
        print("✅ Token TikTok obtenu")
    else:
        print(f"❌ Token TikTok échoué : {r.text[:200]}")
    return token

# ─── ÉTAPE 7 : PUBLICATION TIKTOK ────────────────────────────────────────────
def post_to_tiktok(video_path, description):
    print("📱 Vidéo prête — copie manuelle sur TikTok")
    print(f"   Fichier : {video_path}")
    print(f"   Description : {description}")
    return True

# ─── PIPELINE PRINCIPAL ───────────────────────────────────────────────────────
def run_agent():
    print("\n🚀 AGENT TIKTOK DÉMARRÉ\n" + "="*40)
    with tempfile.TemporaryDirectory() as tmpdir:
        products = get_trending_products()
        print(f"✅ {len(products)} produits trouvés")

        data = select_product_and_write_script(products)
        product = data["product"]
        hashtags = " ".join(data["hashtags"])
        print(f"✅ Produit choisi : {product['name']}")
        print(f"✅ Script : {data['script'][:80]}...")

        audio_path = f"{tmpdir}/voix.mp3"
        generate_voiceover(data["script"], audio_path)

        image_path = f"{tmpdir}/produit.jpg"
        download_image(product.get("image_url", ""), image_path)

        video_path = f"{tmpdir}/video.mp4"
        create_video(image_path, audio_path, product["name"], product["price"], video_path)

        description = f"{data['angle']} 🔥 Lien en bio ! {hashtags}"
        post_to_tiktok(video_path, description)

        print(f"\n✅ CYCLE TERMINÉ")
        print(f"   Produit : {product['name']}")
        print(f"   Description : {description}")
# Upload vidéo sur Cloudinary
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(url=os.getenv("CLOUDINARY_URL"))
            upload = cloudinary.uploader.upload(video_path, resource_type="video", folder="tiktok-agent")
            video_url = upload["secure_url"]
            print(f"\n🌐 Vidéo en ligne : {video_url}")
        except Exception as e:
            print(f"⚠️ Upload Cloudinary échoué : {e}")

if __name__ == "__main__":
    run_agent()