import base64
import io
import re
from flask import Flask, jsonify, render_template_string, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# --- HTML FRONTEND (WEBSITE INTERFACE) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bale Image Generator</title>
    <link rel="manifest" href="/manifest.json">
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background-color: #f2f2f7; margin: 0; padding: 16px; color: #1c1c1e; }
        .card { background: #ffffff; border-radius: 14px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); max-width: 500px; margin: 0 auto; }
        h2 { margin-top: 0; font-size: 20px; text-align: center; }
        label { font-weight: 600; font-size: 14px; display: block; margin: 12px 0 6px; }
        input[type="file"], textarea { width: 100%; border: 1px solid #c7c7cc; border-radius: 8px; padding: 12px; font-size: 15px; }
        textarea { height: 110px; resize: none; }
        button { width: 100%; background: #007aff; color: white; border: none; border-radius: 10px; padding: 14px; font-size: 16px; font-weight: 600; margin-top: 16px; cursor: pointer; }
        button:active { background: #0056b3; }
        #outputArea { margin-top: 20px; text-align: center; display: none; }
        #outputImage { width: 100%; border-radius: 8px; margin-top: 10px; }
        .save-hint { font-size: 13px; color: #8e8e93; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Bale Watermark Generator</h2>
        <form id="baleForm">
            <label>Select Image(s)</label>
            <input type="file" id="imageInput" accept="image/*" multiple required>
            
            <label>Paste Caption</label>
            <textarea id="captionInput" placeholder="Paste your caption text here..." required></textarea>
            
            <button type="submit">Generate Watermarked Image</button>
        </form>

        <div id="outputArea">
            <label>Output Image</label>
            <img id="outputImage" src="" alt="Watermarked Result">
            <p class="save-hint">Long-press the image and tap <b>"Save to Photos"</b></p>
        </div>
    </div>

    <script>
        document.getElementById('baleForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('imageInput');
            const captionInput = document.getElementById('captionInput');
            
            if (!fileInput.files.length) return;

            const formData = new FormData();
            for (let file of fileInput.files) {
                formData.append('images', file);
            }
            formData.append('caption', captionInput.value);

            const res = await fetch('/process', { method: 'POST', body: formData });
            const data = await res.json();

            if (data.success) {
                const img = document.getElementById('outputImage');
                img.src = 'data:image/jpeg;base64,' + data.images[0];
                document.getElementById('outputArea').style.display = 'block';
                img.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error: ' + data.error);
            }
        });
    </script>
</body>
</html>
"""


# --- CAPTION PARSING LOGIC ---
def parse_caption(text):
  lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
  parsed = {"container": "", "item": "", "bale": None, "quantity_display": ""}
  quantity_parts = []

  for original_line in lines:
    line = original_line.upper()

    # Container Name matching (e.g., A-4 [25-26])
    m_cont = re.search(
        r"([A-Z0-9]+(?:-[A-Z0-9]+)+)\s*\[\s*(\d{2}-\d{2})\s*\]", line
    )
    if m_cont and not parsed["container"]:
      parsed["container"] = f"{m_cont.group(1)} [{m_cont.group(2)}]"

    # Bale Number extraction for ascending sorting (e.g., B.NO : 12)
    m_bale = re.search(r"B\.?\s*NO\s*:\s*(\d+)", line)
    if m_bale:
      parsed["bale"] = int(m_bale.group(1))

    # Quantity matching (e.g., [ 500 PCS ] or [ 10/20 SETS ])
    matches = list(
        re.finditer(
            r"\[\s*([^\]]+?)\s*(PCS|SETS|NO'?S|NO’S)\s*\]", line, re.IGNORECASE
        )
    )
    if matches:
      for i, g in enumerate(matches):
        unit = g.group(2).upper().replace(" ", "")
        if unit in ["NOS", "NO'S", "NO’S"]:
          unit = "NO'S"
        content = (
            g.group(1).strip().replace("/", ",").replace(" ", "").upper()
        )
        quantity_parts.append(f"[{content} {unit}]")

        next_start = (
            matches[i + 1].start() if i + 1 < len(matches) else len(line)
        )
        after_text = line[g.end() : next_start].strip().lstrip(" :;-").strip()
        if after_text and not after_text.startswith("["):
          moved = after_text.replace(" ", "").upper()
          if re.search(r"\d", moved):
            quantity_parts.append(f"[{moved}]")

    # Extract Item Name
    if (
        not parsed["item"]
        and not re.search(r"B\.?\s*NO", line)
        and not re.search(r"^\s*\[.*(?:PCS|SETS|NO'?S|NO’S).*?\]", line)
        and "CONTAINER" not in line
        and "FINANCIAL" not in line
        and not re.search(r"\bFY\d{2}-\d{2}\b", line)
        and not re.search(r"\b\d{2}-\d{2}\b", line)
    ):
      parsed["item"] = line.strip()

  parsed["quantity_display"] = "".join(quantity_parts)
  return parsed


# --- IMAGE PROCESSING & WATERMARKING ---
def process_single_image(image_bytes, caption):
  parsed = parse_caption(caption)
  base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
  width, height = base_img.size

  # Font sizing derived from canvas dimensions (3.5% of height)
  font_size = max(22, int(height * 0.035))
  try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
  except OSError:
    font = ImageFont.load_default()

  container_str = parsed["container"] if parsed["container"] else "CONTAINER"
  bale_str = f"B.NO:{parsed['bale']}" if parsed["bale"] else "B.NO:--"
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

  # Position in Bottom-Right Corner
  x = width - box_w - padding
  y = height - box_h - padding

  overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
  draw = ImageDraw.Draw(overlay)

  # Semi-transparent dark background (70% Opacity Black)
  draw.rectangle([x, y, x + box_w, y + box_h], fill=(0, 0, 0, 178))

  # Render Text Lines
  draw.text
  draw.text(
      (x + padding, y + padding + int(font_size * 1.2)),
      line2,
      fill=(255, 255, 255, 255),
      font=font,
  )

  final_img = Image.alpha_composite(base_img, overlay).convert("RGB")

  buffer = io.BytesIO()
  final_img.save(buffer, format="JPEG", quality=92)
  return buffer.getvalue(), parsed["bale"] or 0


# --- ROUTES ---
@app.route("/")
def index():
  return render_template_string(HTML_TEMPLATE)


@app.route("/process", methods=["POST"])
def process_images():
  caption = request.form.get("caption", "")
  files = request.files.getlist("images")

  processed_list = []
  for file in files:
    img_bytes = file.read()
    output_bytes, bale_num = process_single_image(img_bytes, caption)
    processed_list.append({"bale": bale_num, "bytes": output_bytes})

  # SORT IN ASCENDING ORDER BY BALE NUMBER (1, 2, 3... 202)
  processed_list.sort(key=lambda x: x["bale"])

  # Encode to Base64 to stream directly to iOS Web Browser
  b64_images = [
      base64.b64encode(item["bytes"]).decode("utf-8")
      for item in processed_list
  ]

  return jsonify({"success": True, "images": b64_images})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)