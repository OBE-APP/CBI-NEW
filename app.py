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
<title>CREATE CONTAINER IMAGES</title>

<style>
body {
    margin: 0;
    background: #f3f4f6;
    color: #111827;
    font-family: Arial, Helvetica, sans-serif;
}

header {
    background: #111827;
    color: white;
    padding: 18px;
    font-weight: bold;
}

main {
    max-width: 800px;
    margin: auto;
    padding: 16px;
}

.card {
    background: white;
    border: 1px solid #ddd;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 14px;
}

button {
    padding: 12px 16px;
    border: 0;
    border-radius: 8px;
    background: #111827;
    color: #fff;
    font-weight: bold;
    cursor: pointer;
    margin-right: 8px;
    margin-bottom: 8px;
}

button.alt {
    background: #e5e7eb;
    color: #111827;
}

button.green {
    background: #166534;
    color: #ffffff;
}

input[type="file"], textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 12px;
    border: 1px solid #ccc;
    border-radius: 8px;
    font-family: inherit;
    font-size: 16px;
    margin-top: 8px;
    margin-bottom: 16px;
}

textarea {
    min-height: 180px;
    resize: vertical;
}

label {
    font-weight: bold;
    font-size: 14px;
}

.item {
    border: 1px solid #ddd;
    border-radius: 12px;
    padding: 16px;
    margin-top: 20px;
    background: #fafafa;
    text-align: center;
}

.img-preview {
    max-width: 100%;
    height: auto;
    border: 1px solid #ccc;
    border-radius: 4px;
    margin-top: 10px;
    margin-bottom: 15px;
}
</style>
</head>

<body>

<header>
    CREATE CONTAINER IMAGES
</header>

<main>
    <section class="card">
        <label for="photo">SELECT PHOTO(S)</label>
        <input id="photo" type="file" accept="image/*" multiple required>

        <label for="cap">CAPTION (Exact Text)</label>
        <textarea id="cap" placeholder="Paste exact text here. Each line will print exactly as entered." required></textarea>

        <div>
            <button type="button" onclick="processPhoto()">PROCESS IMAGE</button>
            <button type="button" class="alt" onclick="clearEntry()">CLEAR</button>
        </div>

        <div id="pr" style="margin-top:10px; font-weight:bold;"></div>
        <div id="outputContainer"></div>
    </section>
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
    if (!captionInput.value.trim()) {
        alert("Please enter a caption.");
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
                
                const byteCharacters = atob(item.base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const imageBlob = new Blob([byteArray], { type: 'image/jpeg' });

                processedFiles.push({ blob: imageBlob, fileName: fileName });

                const cardHtml = `
                    <div class="item">
                        <b>FILE: ${fileName}</b><br>
                        <img class="img-preview" src="data:image/jpeg;base64,${item.base64}">
                        <div>
                            <button type="button" class="green" onclick="shareToPhotos(${index})">SHARE TO FILES/PHOTOS</button>
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
                title: fileItem.fileName
            });
        } catch (err) {
            if (err.name !== 'AbortError') alert("Sharing failed: " + err.message);
        }
    } else {
        alert("Share API not supported. Use the DOWNLOAD button.");
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
# PILLOW IMAGE OVERLAY PROCESSING
# =========================================================
def process_single_image(image_bytes, caption_text):
    # Load original image
    base_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = base_img.size

    # Extract Bale Number JUST for filename sorting (Best effort)
    bale_num = 0
    m_bale = re.search(r'B\.?\s*NO\s*:\s*(\d+)', caption_text, re.IGNORECASE)
    if m_bale:
        bale_num = int(m_bale.group(1))

    # Font setup: Attempt Helvetica, fallback to default Arial/Sans
    # Font size is scaled based on image width to remain legible
    font_size = max(24, int(orig_w * 0.04))
    try:
        font = ImageFont.truetype("Helvetica.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    # Create dummy image to calculate exact text dimensions
    dummy_img = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy_img)
    
    # Calculate dimensions of the multiline text block
    left, top, right, bottom = draw_dummy.multiline_textbbox((0, 0), caption_text, font=font, spacing=15)
    text_w = right - left
    text_h = bottom - top

    # Define padding around the text
    padding = int(font_size * 0.8)
    
    # Calculate new image dimensions (White background Canvas)
    # Width is the wider of the two (text or original image) + padding
    new_w = max(orig_w, text_w + (padding * 2))
    # Height is Text Block + Padding + Original Image Height
    new_h = orig_h + text_h + (padding * 3)

    # Create the final canvas with a white background
    final_img = Image.new("RGB", (new_w, new_h), (255, 255, 255))
    draw = ImageDraw.Draw(final_img)

    # Draw exact verbatim multiline text at the top left in BLACK
    draw.multiline_text((padding, padding), caption_text, fill=(0, 0, 0), font=font, spacing=15)

    # Paste the original image below the text block
    # Center the image horizontally if the text block made the canvas wider
    img_x = (new_w - orig_w) // 2
    img_y = text_h + (padding * 2)
    final_img.paste(base_img, (img_x, img_y))

    # Save to buffer
    buffer = io.BytesIO()
    final_img.save(buffer, format="JPEG", quality=92)
    
    return buffer.getvalue(), bale_num

# =========================================================
# FLASK ROUTES
# =========================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_images():
    try:
        # The exact text exactly as pasted
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

        # Ascending Sort Logic by Bale Number
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
