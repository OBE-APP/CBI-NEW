import base64
import io
import re
from flask import Flask, jsonify, render_template_string, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# =========================================================
# EMBEDDED HTML FRONTEND INTERFACE
# =========================================================
HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="manifest" href="manifest.json">

<title>CREATE CONTAINER IMAGES</title>

<style>
body{
    margin:0;
    background:#f3f4f6;
    color:#111827;
    font-family:Arial,Helvetica,sans-serif
}

header{
    background:#111827;
    color:white;
    padding:18px
}

main{
    max-width:1050px;
    margin:auto;
    padding:16px
}

.card{
    background:white;
    border:1px solid #ddd;
    border-radius:16px;
    padding:16px;
    margin-bottom:14px
}

button{
    padding:10px 13px;
    border:0;
    border-radius:9px;
    background:#111827;
    color:#fff;
    font-weight:bold;
    margin:3px;
    cursor:pointer
}

button.alt{
    background:#e5e7eb;
    color:#111827
}

button.green{
    background:#166534;
    color:#ffffff;
}

button.red{
    background:#b91c1c
}

button:disabled{
    opacity:.55;
    cursor:not-allowed
}

input,
textarea{
    width:100%;
    box-sizing:border-box;
    padding:10px;
    border:1px solid #ccc;
    border-radius:9px;
    font:inherit
}

textarea{
    min-height:130px
}

.row{
    display:flex;
    gap:8px;
    align-items:center;
    flex-wrap:wrap
}

.hidden{
    display:none
}

.item{
    border:1px solid #ddd;
    border-radius:12px;
    padding:12px;
    margin-top:9px
}

.thumb{
    width:90px;
    height:120px;
    object-fit:cover;
    border-radius:7px;
    background:#eeeeee
}

.thumb.loading{
    opacity:.45
}

.thumb.image-failed{
    opacity:.35
}

.ok{
    color:#166534
}

.err{
    color:#b91c1c
}

.muted{
    color:#6b7280
}

#lm{
    margin-top:12px
}
</style>
</head>

<body>

<header>
    <b>CREATE CONTAINER IMAGES</b>
    <div id="sync">Ready</div>
</header>

<main>

<div id="app">

    <div class="row">
        <button type="button" onclick="page('dash')">DASHBOARD</button>
        <button type="button" onclick="page('master')">CONTAINER MASTER</button>
        <button type="button" onclick="page('create')">CREATE IMAGE</button>
        <button type="button" onclick="page('photos')">CONTAINER PHOTOS</button>
    </div>

    <!-- DASHBOARD -->
    <section id="dash" class="card">
        <h2>CURRENT CONTAINER</h2>
        <div id="cur" style="font-size:24px;font-weight:bold">A-4 [25-26]</div>
        <p id="stats">Active Container Processing</p>
    </section>

    <!-- CREATE IMAGE -->
    <section id="create" class="card">
        <h2>CREATE FINAL JPEG</h2>
        <p>WORKING CONTAINER: <b id="cc">A-4 [25-26]</b></p>

        <label for="photo">SELECT PHOTO(S)</label>
        <input id="photo" type="file" accept="image/*" multiple required>
        <br><br>

        <label for="cap">CAPTION</label>
        <textarea id="cap" placeholder="Paste caption text here..." required></textarea>

        <div>
            <button type="button" onclick="processPhoto()">PROCESS / PREVIEW</button>
            <button type="button" class="alt" onclick="clearEntry()">CLEAR</button>
        </div>

        <div id="pr"></div>

        <div id="outputContainer"></div>

    </section>

</div>

</main>

<script>
"use strict";

const $ = id => document.getElementById(id);
let processedFiles = [];

function clearEntry() {
    $("photo").value = "";
    $("cap").value = "";
    $("outputContainer").innerHTML = "";
    $("pr").textContent = "";
    processedFiles = [];
}

async function processPhoto() {
    const fileInput = $("photo");
    const captionInput = $("cap");
    const pr = $("pr");
    const outputContainer = $("outputContainer");

    if (!fileInput.files.length) {
        alert("Please select at least one photo.");
        return;
    }

    pr.textContent = "Processing image(s)...";
    outputContainer.innerHTML = "";
    processedFiles = [];

    const formData = new FormData();
    for (let file of fileInput.files) {
        formData.append('images', file);
    }
    formData.append('caption', captionInput.value);

    try {
        const res = await fetch('/process', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.success) {
            pr.textContent = "";
            data.images.forEach((item, index) => {
                const baleNum = item.bale ? String(item.bale).padStart(3, '0') : '000';
                const fileName = `[${baleNum}] BALE.jpg`;
                
                // Convert Base64 back to Blob for Share/Download APIs
                const byteCharacters = atob(item.base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const imageBlob = new Blob([byteArray], { type: 'image/jpeg' });

                processedFiles.push({ blob: imageBlob, fileName: fileName });

                const cardHtml = `
                    <div class="item" style="margin-top:15px; text-align:center;">
                        <b>BALE NO: ${item.bale || '--'}</b><br>
                        <img src="data:image/jpeg;base64,${item.base64}" style="max-width:360px; width:100%; margin-top:10px; border-radius:8px;">
                        <div style="margin-top:10px;">
                            <button type="button" class="green" onclick="shareToPhotos(${index})">SHARE TO PHOTOS APP</button>
                            <button type="button" class="alt" onclick="downloadPreviewImage(${index})">DOWNLOAD JPEG</button>
                        </div>
                    </div>
                `;
                outputContainer.innerHTML += cardHtml;
            });
        } else {
            pr.textContent = "Error: " + data.error;
        }
    } catch (err) {
        pr.textContent = "Failed to process image: " + err.message;
    }
}

async function shareToPhotos(index) {
    const fileItem = processedFiles[index];
    if (!fileItem) return;

    const file = new File([fileItem.blob], fileItem.fileName, { type: "image/jpeg" });

    if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try {
            await navigator.share({
                files: [file],
                title: fileItem.fileName,
                text: "Watermarked Bale Image"
            });
        } catch (err) {
            if (err.name !== 'AbortError') alert("Sharing failed: " + err.message);
        }
    } else {
        alert("Direct iOS Share Sheet is not supported in this browser mode. Use the DOWNLOAD JPEG button.");
    }
}

function downloadPreviewImage(index) {
    const fileItem = processedFiles[index];
    if (!fileItem) return;

    const a = document.createElement("a");
    a.href = URL.createObjectURL(fileItem.blob);
    a.download = fileItem.fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
</script>
</body>
</html>
"""

# =========================================================
# CAPTION PARSER LOGIC
# =========================================================
function parse_caption(text):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    parsed = {
        "container": "",
        "item": "",
        "bale": None,
        "quantity_display": ""
    }
    quantity_parts = []

    for original_line in lines:
        line = original_line.upper()

        # Container Name (e.g., A-4 [25-26])
        m_cont = re.search(r'([A-Z0-9]+(?:-[A-Z0-9]+)+)\s*\[\s*(\d{2}-\d{2})\s*\]', line)
        if m_cont and not parsed["container"]:
            parsed["container"] = f"{m_cont.group(1)} [{m_cont.group(2)}]"

        # Bale Number for Ascending Sort (e.g., B.NO : 12)
        m_bale = re.search(r'B\.?\s*NO\s*:\s*(\d+)', line)
        if m_bale:
            parsed["bale"] = int(m_bale.group(1))

        # Quantity brackets parsing (e.g., [ 500 PCS ])
        matches = list(re.finditer(r'\[\s*([^\]]+?)\s*(PCS|SETS|NO\'?S|NO’S)\s*\]', line, re.IGNORECASE))
        if matches:
            for i, g in enumerate(matches):
                unit = g.group(2).upper().replace(" ", "")
                if unit in ["NOS", "NO'S", "NO’S"]:
                    unit = "NO'S"
                content = g.group(1).strip().replace("/", ",").replace(" ", "").upper()
                quantity_parts.append(f"[{content} {unit}]")

                next_start = matches[i + 1].start() if i + 1 < len(matches) else len(line)
                after_text = line[g.end():next_start].strip().lstrip(" :;-").strip()
                if after_text and not after_text.startswith("["):
                    moved = after_text.replace(" ", "").upper()
                    if re.search(r'\d', moved):
                        quantity_parts.append(f"[{moved}]")

        # Item Name extraction
        if (not parsed["item"] and 
            not re.search(r'B\.?\s*NO', line) and 
            not re.search(r'^\s*\[.*(?:PCS\vert{}SETS\vert{}NO\'?S\vert{}NO’S).*?\]', line) and 
            "CONTAINER" not in line and 
            "FINANCIAL" not in line and 
            not re.search(r'\bFY\d{2}-\d{2}\b', line) and 
            not re.search(r'\b\d{2}-\d{2}\b', line)):
            parsed["item"] = line.strip()

    parsed["quantity_display"] = "".join(quantity_parts)
    return parsed

# =========================================================
# PILLOW IMAGE OVERLAY PROCESSING
# =========================================================
def process_single_image(image_bytes, caption):
    parsed = parse_caption(caption)
    base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = base_img.size

    font_size = max(22, int(height * 0.035))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    container_str = parsed["container"] if parsed["container"] else "CONTAINER"
    bale_str = f"B.NO:{parsed['bale']}" if parsed['bale'] else "B.NO:--"
    line1 = f"{container_str} {bale_str}"
    line2 = f"{parsed['item']} {parsed['quantity_display']}".strip()

    left1, top1, right1, bottom1 = font.getbbox(line1)
    left2, top2, right2, bottom2 = font.getbbox(line2)

    w1, h1 = right1 - left1, bottom1 - top1
    w2, h2 = right2 - left2, bottom2 - top2

    max_text_w = max(w1, w2)
    padding = int(font_size * 0.6)

    box_w = max_text_w + (padding * 2)
    box_h = int((font_size * 2.4) + (padding * 2))

    x = width - box_w - padding
    y = height - box_h - padding

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 70% Opacity Dark Background Box
    draw.rectangle([x, y, x + box_w, y + box_h], fill=(0, 0, 0, 178))

    # Draw White Overlay Text
    draw.text((x + padding, y + padding), line1, fill=(255, 255, 255, 255), font=font)
    draw.text((x + padding, y + padding + int(font_size * 1.2)), line2, fill=(255, 255, 255, 255), font=font)

    final_img = Image.alpha_composite(base_img, overlay).convert("RGB")

    buffer = io.BytesIO()
    final_img.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue(), parsed["bale"] or 0

# =========================================================
# FLASK ROUTES
# =========================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_images():
    try:
        caption = request.form.get('caption', '')
        files = request.files.getlist('images')

        processed_list = []
        for file in files:
            img_bytes = file.read()
            output_bytes, bale_num = process_single_image(img_bytes, caption)
            processed_list.append({
                "bale": bale_num,
                "bytes": output_bytes
            })

        # Ascending sort logic by Bale Number (1, 2, 3... 202)
        processed_list.sort(key=lambda x: x["bale"])

        response_images = []
        for item in processed_list:
            b64_str = base64.b64encode(item["bytes"]).decode('utf-8')
            response_images.append({
                "bale": item["bale"],
                "base64": b64_str
            })

        return jsonify({"success": True, "images": response_images})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
