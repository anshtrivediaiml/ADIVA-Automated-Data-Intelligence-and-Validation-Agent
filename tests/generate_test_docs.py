"""
Generate test documents for Hindi and Gujarati OCR testing.
Creates realistic scanned-document-style PNG images using Nirmala.ttc font.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import random

FONT_PATH = r"C:\Windows\Fonts\Nirmala.ttc"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_documents")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────────

def make_font(size):
    return ImageFont.truetype(FONT_PATH, size)

def add_scan_noise(img):
    """Add subtle noise/grain to simulate a scanned document."""
    import random
    pixels = img.load()
    w, h = img.size
    for _ in range(w * h // 80):          # sprinkle ~1.25% noisy pixels
        x, y = random.randint(0, w-1), random.randint(0, h-1)
        v = random.randint(180, 240)
        pixels[x, y] = (v, v, v)
    return img

def new_page(w=1240, h=1754):            # A4 at ~150 dpi
    img = Image.new("RGB", (w, h), color=(252, 251, 248))   # off-white paper
    return img, ImageDraw.Draw(img)

def draw_line(draw, y, x1=80, x2=1160, color=(180, 180, 180)):
    draw.line([(x1, y), (x2, y)], fill=color, width=1)

def save(img, name):
    path = os.path.join(OUTPUT_DIR, name)
    add_scan_noise(img)
    img.save(path, dpi=(150, 150))
    print(f"  Saved: {path}")
    return path


# ── Document 1: Hindi Invoice ────────────────────────────────────────────────

def make_hindi_invoice():
    img, draw = new_page()

    # Header
    draw.rectangle([(0, 0), (1240, 110)], fill=(25, 60, 120))
    draw.text((60, 20), "कर चालान / TAX INVOICE", font=make_font(36), fill="white")
    draw.text((60, 65), "ADIVA व्यापार समाधान प्राइवेट लिमिटेड", font=make_font(22), fill=(200, 220, 255))

    y = 130
    # Company info block
    draw.text((60, y),   "विक्रेता का विवरण:", font=make_font(18), fill=(50, 50, 50))
    draw.text((60, y+28),"कंपनी: सूर्योदय ट्रेडर्स", font=make_font(16), fill=(80, 80, 80))
    draw.text((60, y+52),"पता: 42, व्यापार नगर, अहमदाबाद - 380001", font=make_font(16), fill=(80, 80, 80))
    draw.text((60, y+76),"GSTIN: 24AABCS1429B1ZB  |  दूरभाष: +91-79-2345-6789", font=make_font(16), fill=(80, 80, 80))

    draw.text((700, y),  "चालान संख्या:", font=make_font(18), fill=(50, 50, 50))
    draw.text((700, y+28),"INV-2026-00847", font=make_font(16), fill=(80, 80, 80))
    draw.text((700, y+52),"दिनांक: 19 फरवरी 2026", font=make_font(16), fill=(80, 80, 80))
    draw.text((700, y+76),"देय तिथि: 05 मार्च 2026", font=make_font(16), fill=(80, 80, 80))

    y = 290
    draw_line(draw, y)
    draw.text((60, y+10), "खरीदार का विवरण:", font=make_font(18), fill=(50, 50, 50))
    draw.text((60, y+38), "नाम: राजेश कुमार शर्मा", font=make_font(16), fill=(80, 80, 80))
    draw.text((60, y+62), "पता: B-12, शांति नगर, जयपुर - 302001, राजस्थान", font=make_font(16), fill=(80, 80, 80))
    draw.text((60, y+86), "GSTIN: 08AABCR1234C1ZD", font=make_font(16), fill=(80, 80, 80))

    # Table header
    y = 430
    draw.rectangle([(60, y), (1180, y+40)], fill=(230, 238, 255))
    cols = [60, 400, 600, 760, 920, 1060, 1180]
    headers = ["वस्तु / सेवा विवरण", "HSN", "मात्रा", "दर (₹)", "GST%", "राशि (₹)"]
    for i, h in enumerate(headers):
        draw.text((cols[i]+5, y+8), h, font=make_font(14), fill=(30, 30, 100))

    # Table rows
    items = [
        ("लैपटॉप कंप्यूटर (Core i7)", "8471", "2", "55,000", "18%", "1,10,000"),
        ("वायरलेस माउस", "8471", "5", "850",    "18%",  "4,250"),
        ("USB-C हब (7-in-1)", "8471", "3", "1,200",  "18%",  "3,600"),
        ("प्रिंटर कारतूस (काला)", "8443", "10","450",   "12%",  "4,500"),
        ("कार्यालय कुर्सी (एर्गोनॉमिक)", "9401","1","12,500","18%","12,500"),
    ]
    for idx, row in enumerate(items):
        ry = y + 40 + idx * 38
        bg = (248, 248, 255) if idx % 2 == 0 else (255, 255, 255)
        draw.rectangle([(60, ry), (1180, ry+38)], fill=bg)
        for ci, val in enumerate(row):
            draw.text((cols[ci]+5, ry+8), val, font=make_font(14), fill=(60, 60, 60))
        draw_line(draw, ry+38, color=(210, 210, 210))

    # Totals
    y = y + 40 + len(items)*38 + 20
    draw_line(draw, y)
    draw.text((800, y+10),  "उप-कुल:",       font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+10), "₹ 1,34,850",    font=make_font(16), fill=(50,50,50))
    draw.text((800, y+36),  "CGST (9%):",    font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+36), "₹ 12,136",      font=make_font(16), fill=(50,50,50))
    draw.text((800, y+62),  "SGST (9%):",    font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+62), "₹ 12,136",      font=make_font(16), fill=(50,50,50))
    draw.rectangle([(790, y+90), (1180, y+128)], fill=(25, 60, 120))
    draw.text((800, y+98),  "कुल देय राशि:", font=make_font(18), fill="white")
    draw.text((1020, y+98), "₹ 1,59,122",    font=make_font(18), fill="white")

    # Footer
    y = y + 160
    draw_line(draw, y)
    draw.text((60, y+10),  "राशि शब्दों में: एक लाख उनसठ हजार एक सौ बाईस रुपये मात्र", font=make_font(15), fill=(80,80,80))
    draw.text((60, y+40),  "नियम एवं शर्तें: भुगतान 15 दिनों के भीतर करें। विलंब पर 2% मासिक ब्याज लागू होगा।", font=make_font(14), fill=(100,100,100))
    draw.text((60, y+65),  "बैंक विवरण: SBI, खाता संख्या: 38291047563, IFSC: SBIN0001234", font=make_font(14), fill=(100,100,100))
    draw.text((900, y+80), "अधिकृत हस्ताक्षर", font=make_font(15), fill=(50,50,50))
    draw.text((900, y+105),"सूर्योदय ट्रेडर्स", font=make_font(14), fill=(80,80,80))

    return save(img, "hindi_invoice.png")


# ── Document 2: Gujarati Invoice ─────────────────────────────────────────────

def make_gujarati_invoice():
    img, draw = new_page()

    draw.rectangle([(0, 0), (1240, 110)], fill=(20, 100, 60))
    draw.text((60, 20), "કર ભરપાઈ / TAX INVOICE", font=make_font(36), fill="white")
    draw.text((60, 65), "ADIVA વ્યાપાર ઉકેલ પ્રાઇવેટ લિમિટેડ", font=make_font(22), fill=(180, 240, 200))

    y = 130
    draw.text((60, y),   "વેચાણકર્તાની વિગત:", font=make_font(18), fill=(50,50,50))
    draw.text((60, y+28),"કંપની: ઉષા ટ્રેડર્સ", font=make_font(16), fill=(80,80,80))
    draw.text((60, y+52),"સરનામું: 15, ઉદ્યોગ નગર, સુરત - 395003", font=make_font(16), fill=(80,80,80))
    draw.text((60, y+76),"GSTIN: 24AABCU5678D1ZE  |  ફોન: +91-261-234-5678", font=make_font(16), fill=(80,80,80))

    draw.text((700, y),   "ભરપાઈ નંબર:", font=make_font(18), fill=(50,50,50))
    draw.text((700, y+28),"INV-2026-00391", font=make_font(16), fill=(80,80,80))
    draw.text((700, y+52),"તારીખ: 19 ફેબ્રુઆરી 2026", font=make_font(16), fill=(80,80,80))
    draw.text((700, y+76),"ચૂકવણીની અંતિમ તારીખ: 05 માર્ચ 2026", font=make_font(16), fill=(80,80,80))

    y = 290
    draw_line(draw, y)
    draw.text((60, y+10), "ખરીદનારની વિગત:", font=make_font(18), fill=(50,50,50))
    draw.text((60, y+38), "નામ: ભાવિન પટેલ", font=make_font(16), fill=(80,80,80))
    draw.text((60, y+62), "સરનામું: C-7, ગ્રીન પાર્ક, વડોદરા - 390007, ગુજરાત", font=make_font(16), fill=(80,80,80))
    draw.text((60, y+86), "GSTIN: 24AABCP9876E1ZF", font=make_font(16), fill=(80,80,80))

    y = 430
    draw.rectangle([(60, y), (1180, y+40)], fill=(210, 240, 220))
    cols = [60, 400, 600, 760, 920, 1060, 1180]
    headers = ["માલ / સેવા વિગત", "HSN", "જથ્થો", "ભાવ (₹)", "GST%", "રકમ (₹)"]
    for i, h in enumerate(headers):
        draw.text((cols[i]+5, y+8), h, font=make_font(14), fill=(20, 80, 40))

    items = [
        ("સ્માર્ટફોન (128GB, 5G)", "8517", "3", "18,500", "18%", "55,500"),
        ("બ્લૂટૂથ ઇયરફોન",         "8518", "5", "2,200",  "18%", "11,000"),
        ("સ્ક્રીન ગાર્ડ (ટેમ્પર્ડ)", "7007","10","350",   "12%",  "3,500"),
        ("ફોન કવર (સિલિકોન)",       "3926","10","250",    "18%",  "2,500"),
        ("ચાર્જર (65W ફાસ્ટ)",      "8504", "3","1,800",  "18%",  "5,400"),
    ]
    for idx, row in enumerate(items):
        ry = y + 40 + idx * 38
        bg = (245, 255, 248) if idx % 2 == 0 else (255, 255, 255)
        draw.rectangle([(60, ry), (1180, ry+38)], fill=bg)
        for ci, val in enumerate(row):
            draw.text((cols[ci]+5, ry+8), val, font=make_font(14), fill=(60,60,60))
        draw_line(draw, ry+38, color=(200, 230, 210))

    y = y + 40 + len(items)*38 + 20
    draw_line(draw, y)
    draw.text((800, y+10),  "પેટા-કુલ:",       font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+10), "₹ 77,900",         font=make_font(16), fill=(50,50,50))
    draw.text((800, y+36),  "CGST (9%):",       font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+36), "₹ 7,011",          font=make_font(16), fill=(50,50,50))
    draw.text((800, y+62),  "SGST (9%):",       font=make_font(16), fill=(50,50,50))
    draw.text((1060, y+62), "₹ 7,011",          font=make_font(16), fill=(50,50,50))
    draw.rectangle([(790, y+90), (1180, y+128)], fill=(20, 100, 60))
    draw.text((800, y+98),  "કુલ ચૂકવવાની રકમ:", font=make_font(18), fill="white")
    draw.text((1040, y+98), "₹ 91,922",          font=make_font(18), fill="white")

    y = y + 160
    draw_line(draw, y)
    draw.text((60, y+10), "રકમ શબ્દોમાં: એકાણું હજાર નવસો બાવીસ રૂપિયા માત્ર", font=make_font(15), fill=(80,80,80))
    draw.text((60, y+40), "નિયમો: ચૂકવણી 15 દિવસમાં કરવી. વિલંબ પર 2% માસિક વ્યાજ લાગુ.", font=make_font(14), fill=(100,100,100))
    draw.text((60, y+65), "બેંક વિગત: SBI, ખાતા નં: 29384756102, IFSC: SBIN0005678", font=make_font(14), fill=(100,100,100))
    draw.text((900, y+80), "અધિકૃત સહી", font=make_font(15), fill=(50,50,50))
    draw.text((900, y+105),"ઉષા ટ્રેડર્સ", font=make_font(14), fill=(80,80,80))

    return save(img, "gujarati_invoice.png")


# ── Document 3: Hindi Resume ──────────────────────────────────────────────────

def make_hindi_resume():
    img, draw = new_page()

    draw.rectangle([(0, 0), (1240, 130)], fill=(60, 40, 100))
    draw.text((60, 18),  "प्रिया वर्मा", font=make_font(42), fill="white")
    draw.text((60, 72),  "सॉफ्टवेयर इंजीनियर | Python | FastAPI | Machine Learning", font=make_font(20), fill=(200, 180, 255))
    draw.text((60, 100), "📧 priya.verma@email.com  |  📞 +91-98765-43210  |  📍 बेंगलुरु, कर्नाटक", font=make_font(16), fill=(220, 210, 255))

    y = 150
    def section(title, yy):
        draw.rectangle([(60, yy), (1180, yy+34)], fill=(240, 235, 255))
        draw.text((70, yy+6), title, font=make_font(18), fill=(60, 40, 100))
        return yy + 44

    y = section("🎓 शैक्षणिक योग्यता", y)
    rows = [
        ("बी.टेक (कंप्यूटर विज्ञान)", "IIT दिल्ली", "2019–2023", "8.7 CGPA"),
        ("12वीं (PCM)",                "केंद्रीय विद्यालय, जयपुर", "2019", "94.2%"),
    ]
    for r in rows:
        draw.text((70,  y), r[0], font=make_font(15), fill=(40,40,40))
        draw.text((500, y), r[1], font=make_font(15), fill=(80,80,80))
        draw.text((850, y), r[2], font=make_font(15), fill=(80,80,80))
        draw.text((1050,y), r[3], font=make_font(15), fill=(20,100,40))
        y += 30

    y = section("💼 कार्य अनुभव", y + 10)
    draw.text((70, y),    "वरिष्ठ सॉफ्टवेयर इंजीनियर — Infosys Ltd., बेंगलुरु", font=make_font(16), fill=(40,40,40))
    draw.text((70, y+26), "जनवरी 2024 – वर्तमान", font=make_font(14), fill=(100,100,100))
    for bullet in [
        "• FastAPI और Python का उपयोग करके RESTful API विकसित किए",
        "• OCR और AI का उपयोग करके दस्तावेज़ प्रसंस्करण प्रणाली बनाई",
        "• माइक्रोसर्विस आर्किटेक्चर में 40% प्रदर्शन सुधार हासिल किया",
        "• 5 सदस्यों की टीम का नेतृत्व किया",
    ]:
        y += 26
        draw.text((80, y), bullet, font=make_font(14), fill=(60,60,60))
    y += 10

    draw.text((70, y+20), "जूनियर डेवलपर — TCS, पुणे", font=make_font(16), fill=(40,40,40))
    draw.text((70, y+46), "जुलाई 2023 – दिसंबर 2023", font=make_font(14), fill=(100,100,100))
    for bullet in [
        "• Django REST Framework में API endpoints लिखे",
        "• PostgreSQL डेटाबेस डिज़ाइन और ऑप्टिमाइज़ेशन",
    ]:
        y += 26
        draw.text((80, y+20), bullet, font=make_font(14), fill=(60,60,60))
    y += 50

    y = section("🛠 तकनीकी कौशल", y + 10)
    skills = [
        ("प्रोग्रामिंग भाषाएँ:", "Python, JavaScript, SQL, C++"),
        ("फ्रेमवर्क:",           "FastAPI, Django, React, TensorFlow"),
        ("डेटाबेस:",             "PostgreSQL, MongoDB, Redis"),
        ("उपकरण:",              "Git, Docker, Kubernetes, AWS"),
        ("AI/ML:",               "Scikit-learn, Pandas, NumPy, OCR"),
    ]
    for label, val in skills:
        draw.text((70,  y), label, font=make_font(15), fill=(60,40,100))
        draw.text((320, y), val,   font=make_font(15), fill=(60,60,60))
        y += 28

    y = section("🏆 उपलब्धियाँ", y + 10)
    for ach in [
        "• राष्ट्रीय हैकाथॉन 2023 में प्रथम स्थान (AI श्रेणी)",
        "• Google Summer of Code 2022 में चयनित",
        "• Infosys Insta Award Q1 2024 — उत्कृष्ट प्रदर्शन",
    ]:
        draw.text((70, y), ach, font=make_font(15), fill=(60,60,60))
        y += 28

    return save(img, "hindi_resume.png")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating test documents...")
    p1 = make_hindi_invoice()
    p2 = make_gujarati_invoice()
    p3 = make_hindi_resume()
    print(f"\nDone! 3 test documents saved to: {OUTPUT_DIR}")
    print("Files:")
    for p in [p1, p2, p3]:
        size_kb = os.path.getsize(p) // 1024
        print(f"  {os.path.basename(p)}  ({size_kb} KB)")
