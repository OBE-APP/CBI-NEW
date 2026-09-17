import base64
import io
import os
import re

from flask import Flask, jsonify, render_template_string, request
from PIL import Image, ImageDraw, ImageFont


app = Flask(__name__)


# =========================================================
# APPLICATION SETTINGS
# =========================================================

OUTPUT_WIDTH = 1200
OUTPUT_HEIGHT = 1600

# Exact required font size
FONT_SIZE = 60

# Light-grey background
BACKGROUND_COLOR = (242, 242, 242)

# Black text
TEXT_COLOR = (0, 0, 0)

# JPEG quality
JPEG_QUALITY = 92


# =========================================================
# FONT SETTINGS
# =========================================================
#
# IMPORTANT:
# Put a real Helvetica .ttf font file in the same folder
# as this Python file and name it:
#
#     Helvetica.ttf
#
# The code first looks for Helvetica.ttf beside this file.
#
# If it cannot find Helvetica, it will try a few common
# Helvetica locations.
#
# The final fallback is Liberation Sans / Arial only so
# that the application does not completely stop if the
# Helvetica file is missing.
#
# For the exact required Helvetica output, place:
#
#     Helvetica.ttf
#
# beside this Python file.
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "Helvetica.ttf"),
    os.path.join(BASE_DIR, "HelveticaNeue.ttf"),
    os.path.join(BASE_DIR, "HelveticaNeueLTStd-Roman.ttf"),

    # Common macOS locations
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Helvetica.dfont",

    # Common Linux locations if installed
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def load_font():
    """
    Load the 60 pt font.

    The preferred font is Helvetica.ttf located beside
    this Python file.
    """

    for font_path in FONT_CANDIDATES:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, FONT_SIZE)
            except Exception:
                pass

    # Last-resort fallback.
    #
    # This is intentionally only used if no TrueType font
    # can be loaded.
    return ImageFont.load_default()


# =========================================================
# EMBEDDED HTML FRONTEND INTERFACE
# =========================================================

HTML_TEMPLATE = """<!doctype html>
<html>

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

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

input[type="file"],
textarea {
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

    <label for="photo">
        SELECT PHOTO(S)
    </label>

    <input
        id="photo"
        type="file"
        accept="image/*"
        multiple
        required
    >

    <label for="cap">
        CAPTION (Exact Text)
    </label>

    <textarea
        id="cap"
        placeholder="Paste exact text here."
        required
    ></textarea>

    <div>

        <button
            type="button"
            onclick="processPhoto()"
        >
            PROCESS IMAGE
        </button>

        <button
            type="button"
            class="alt"
            onclick="clearEntry()"
        >
            CLEAR
        </button>

    </div>

    <div
        id="pr"
        style="margin-top:10px; font-weight:bold;"
    ></div>

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

        formData.append("images", file);

    }


    formData.append(
        "caption",
        captionInput.value
    );


    try {

        const res = await fetch(
            "/process",
            {
                method: "POST",
                body: formData
            }
        );


        const data = await res.json();


        if (data.success) {

            pr.textContent = "";


            data.images.forEach(
                (item, index) => {

                    const baleNum =
                        item.bale
                        ? String(item.bale).padStart(3, "0")
                        : "000";


                    const fileName =
                        `[${baleNum}] BALE.jpg`;


                    const byteCharacters =
                        atob(item.base64);


                    const byteNumbers =
                        new Array(
                            byteCharacters.length
                        );


                    for (
                        let i = 0;
                        i < byteCharacters.length;
                        i++
                    ) {

                        byteNumbers[i] =
                            byteCharacters.charCodeAt(i);

                    }


                    const byteArray =
                        new Uint8Array(byteNumbers);


                    const imageBlob =
                        new Blob(
                            [byteArray],
                            {
                                type: "image/jpeg"
                            }
                        );


                    processedFiles.push({

                        blob: imageBlob,

                        fileName: fileName

                    });


                    const cardHtml = `

                        <div class="item">

                            <b>
                                FILE: ${fileName}
                            </b>

                            <br>

                            <img
                                class="img-preview"
                                src="data:image/jpeg;base64,${item.base64}"
                            >

                            <div>

                                <button
                                    type="button"
                                    class="green"
                                    onclick="shareToPhotos(${index})"
                                >
                                    SHARE TO FILES/PHOTOS
                                </button>

                                <button
                                    type="button"
                                    class="alt"
                                    onclick="downloadPreviewImage(${index})"
                                >
                                    DOWNLOAD JPEG
                                </button>

                            </div>

                        </div>

                    `;


                    outputContainer.innerHTML +=
                        cardHtml;

                }
            );


        } else {

            pr.textContent =
                "Error: " + data.error;

        }


    } catch (err) {

        pr.textContent =
            "Failed to process image: " + err.message;

    }

}


async function shareToPhotos(index) {

    const fileItem =
        processedFiles[index];


    if (!fileItem) {
        return;
    }


    const file =
        new File(
            [fileItem.blob],
            fileItem.fileName,
            {
                type: "image/jpeg"
            }
        );


    if (
        navigator.canShare &&
        navigator.canShare({
            files: [file]
        })
    ) {

        try {

            await navigator.share({

                files: [file],

                title: fileItem.fileName

            });


        } catch (err) {

            if (err.name !== "AbortError") {

                alert(
                    "Sharing failed: " +
                    err.message
                );

            }

        }


    } else {

        alert(
            "Share API not supported. " +
            "Use the DOWNLOAD button."
        );

    }

}


function downloadPreviewImage(index) {

    const fileItem =
        processedFiles[index];


    if (!fileItem) {
        return;
    }


    const a =
        document.createElement("a");


    a.href =
        URL.createObjectURL(
            fileItem.blob
        );


    a.download =
        fileItem.fileName;


    document.body.appendChild(a);


    a.click();


    document.body.removeChild(a);


    setTimeout(
        () => {
            URL.revokeObjectURL(a.href);
        },
        1000
    );

}

</script>

</body>

</html>
"""


# =========================================================
# BALE NUMBER EXTRACTION
# =========================================================
#
# IMPORTANT:
#
# ONLY THE BALE NUMBER IS READ FROM THE CAPTION.
#
# Nothing else in the caption is validated.
#
# Examples accepted:
#
# B.NO:37
# B. NO: 37
# B NO:37
# BNO:37
#
# The rest of the caption is simply converted to uppercase
# and printed.
# =========================================================

def extract_bale_number(caption_text):

    bale_num = 0

    match = re.search(
        r"B\s*\.?\s*NO\s*:\s*(\d+)",
        caption_text,
        re.IGNORECASE
    )

    if match:

        bale_num = int(
            match.group(1)
        )

    return bale_num


# =========================================================
# CONVERT CAPTION TO UPPERCASE
# =========================================================

def prepare_caption(caption_text):

    if caption_text is None:
        return ""

    # Convert EVERYTHING to uppercase.
    #
    # We do not validate the other lines.
    # We do not search for PCS, SETS, ITEM, CONTAINER etc.
    #
    # Only bale number extraction is performed separately.

    return caption_text.upper()


# =========================================================
# CALCULATE PRODUCT IMAGE SIZE
# =========================================================

def calculate_fitted_image_size(
    original_width,
    original_height,
    available_width,
    available_height
):
    """
    Calculate the largest proportional image size that
    fits completely inside the available area.

    IMPORTANT:
    The image is NEVER cropped.

    It is only reduced proportionally if necessary.
    """

    if original_width <= 0 or original_height <= 0:

        return 1, 1


    width_ratio = (
        available_width /
        original_width
    )

    height_ratio = (
        available_height /
        original_height
    )


    scale = min(
        width_ratio,
        height_ratio
    )


    # Never enlarge an image unnecessarily.
    #
    # If the original image is smaller than the available
    # area, retain its original resolution.
    scale = min(
        scale,
        1.0
    )


    new_width = max(
        1,
        int(original_width * scale)
    )


    new_height = max(
        1,
        int(original_height * scale)
    )


    return new_width, new_height


# =========================================================
# CREATE FINAL 1200 × 1600 IMAGE
# =========================================================

def process_single_image(
    image_bytes,
    caption_text
):

    # -----------------------------------------------------
    # LOAD ORIGINAL PRODUCT IMAGE
    # -----------------------------------------------------

    base_img = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")


    orig_w, orig_h = base_img.size


    # -----------------------------------------------------
    # BALE NUMBER
    #
    # ONLY THIS INFORMATION IS EXTRACTED FROM THE CAPTION.
    # -----------------------------------------------------

    bale_num = extract_bale_number(
        caption_text
    )


    # -----------------------------------------------------
    # CONVERT ALL PRINTED TEXT TO CAPITAL LETTERS
    # -----------------------------------------------------

    caption_text = prepare_caption(
        caption_text
    )


    # -----------------------------------------------------
    # LOAD 60 PT HELVETICA
    # -----------------------------------------------------

    font = load_font()


    # -----------------------------------------------------
    # FIXED FINAL CANVAS
    #
    # EXACTLY:
    #
    # WIDTH  = 1200
    # HEIGHT = 1600
    #
    # 3:4
    # -----------------------------------------------------

    canvas_w = OUTPUT_WIDTH
    canvas_h = OUTPUT_HEIGHT


    # -----------------------------------------------------
    # CREATE LIGHT-GREY BACKGROUND
    # -----------------------------------------------------

    final_img = Image.new(
        "RGB",
        (canvas_w, canvas_h),
        BACKGROUND_COLOR
    )


    draw = ImageDraw.Draw(
        final_img
    )


    # -----------------------------------------------------
    # TEXT AREA
    # -----------------------------------------------------
    #
    # Text is centered horizontally.
    #
    # The text remains at 60 pt.
    #
    # We calculate the actual height required by the entire
    # caption.
    # -----------------------------------------------------

    text_bbox = draw.multiline_textbbox(
        (0, 0),
        caption_text,
        font=font,
        spacing=0,
        align="center"
    )


    text_left = text_bbox[0]
    text_top = text_bbox[1]
    text_right = text_bbox[2]
    text_bottom = text_bbox[3]


    text_w = (
        text_right -
        text_left
    )


    text_h = (
        text_bottom -
        text_top
    )


    # -----------------------------------------------------
    # HORIZONTAL TEXT POSITION
    # -----------------------------------------------------

    text_x = (
        canvas_w - text_w
    ) // 2


    # -----------------------------------------------------
    # TOP MARGIN
    # -----------------------------------------------------
    #
    # Small controlled margin so the text sits near the top
    # without touching the edge.
    # -----------------------------------------------------

    top_margin = 35


    text_y = top_margin - text_top


    # -----------------------------------------------------
    # DRAW CAPTION
    # -----------------------------------------------------

    draw.multiline_text(
        (text_x, text_y),
        caption_text,
        fill=TEXT_COLOR,
        font=font,
        spacing=0,
        align="center"
    )


    # -----------------------------------------------------
    # REDUCED GAP BETWEEN TEXT AND PRODUCT IMAGE
    # -----------------------------------------------------
    #
    # This is deliberately small.
    #
    # If you later want to make the gap even smaller/larger,
    # change only this number.
    # -----------------------------------------------------

    GAP = 5


    # -----------------------------------------------------
    # PRODUCT IMAGE AVAILABLE AREA
    # -----------------------------------------------------
    #
    # The product image must:
    #
    # 1. Never be cropped
    # 2. Stay proportional
    # 3. Remain inside the 1200 × 1600 canvas
    # 4. Sit below the caption
    #
    # We reserve a small bottom margin as well.
    # -----------------------------------------------------

    bottom_margin = 20


    image_area_top = (
        top_margin +
        text_h +
        GAP
    )


    image_area_bottom = (
        canvas_h -
        bottom_margin
    )


    image_area_height = (
        image_area_bottom -
        image_area_top
    )


    image_area_width = canvas_w


    # -----------------------------------------------------
    # SAFETY CHECK
    # -----------------------------------------------------

    if image_area_height < 1:

        image_area_height = 1


    # -----------------------------------------------------
    # FIT PRODUCT IMAGE WITHOUT CROPPING
    # -----------------------------------------------------

    fitted_w, fitted_h = (
        calculate_fitted_image_size(
            orig_w,
            orig_h,
            image_area_width,
            image_area_height
        )
    )


    # -----------------------------------------------------
    # RESIZE PRODUCT IMAGE
    # -----------------------------------------------------
    #
    # LANCZOS gives high-quality resizing.
    # -----------------------------------------------------

    resized_img = base_img.resize(
        (fitted_w, fitted_h),
        Image.Resampling.LANCZOS
    )


    # -----------------------------------------------------
    # CENTER PRODUCT IMAGE HORIZONTALLY
    # -----------------------------------------------------

    img_x = (
        canvas_w -
        fitted_w
    ) // 2


    # -----------------------------------------------------
    # CENTER PRODUCT IMAGE VERTICALLY IN AVAILABLE AREA
    # -----------------------------------------------------

    img_y = (
        image_area_top +
        (
            image_area_height -
            fitted_h
        ) // 2
    )


    # -----------------------------------------------------
    # PASTE PRODUCT IMAGE
    # -----------------------------------------------------

    final_img.paste(
        resized_img,
        (img_x, img_y)
    )


    # -----------------------------------------------------
    # SAVE AS JPEG
    # -----------------------------------------------------

    buffer = io.BytesIO()


    final_img.save(
        buffer,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True
    )


    # -----------------------------------------------------
    # RETURN JPEG BYTES + BALE NUMBER
    # -----------------------------------------------------

    return (
        buffer.getvalue(),
        bale_num
    )


# =========================================================
# FLASK ROUTES
# =========================================================

@app.route("/")
def index():

    return render_template_string(
        HTML_TEMPLATE
    )


# =========================================================
# PROCESS IMAGES
# =========================================================

@app.route(
    "/process",
    methods=["POST"]
)
def process_images():

    try:

        # -------------------------------------------------
        # GET CAPTION
        # -------------------------------------------------

        caption = request.form.get(
            "caption",
            ""
        )


        # -------------------------------------------------
        # GET SELECTED IMAGES
        # -------------------------------------------------

        files = request.files.getlist(
            "images"
        )


        # -------------------------------------------------
        # PROCESS ALL IMAGES
        # -------------------------------------------------

        processed_list = []


        for file in files:

            img_bytes = file.read()


            output_bytes, bale_num = (
                process_single_image(
                    img_bytes,
                    caption
                )
            )


            processed_list.append({

                "bale": bale_num,

                "bytes": output_bytes

            })


        # -------------------------------------------------
        # SORT BY BALE NUMBER
        #
        # ONLY BALE NUMBER IS USED FOR SORTING.
        # -------------------------------------------------

        processed_list.sort(
            key=lambda x: x["bale"]
        )


        # -------------------------------------------------
        # PREPARE JSON RESPONSE
        # -------------------------------------------------

        response_images = []


        for item in processed_list:

            b64_str = base64.b64encode(
                item["bytes"]
            ).decode("utf-8")


            response_images.append({

                "bale": item["bale"],

                "base64": b64_str

            })


        return jsonify({

            "success": True,

            "images": response_images

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        })


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
