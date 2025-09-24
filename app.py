import os
import tempfile
import subprocess
from io import BytesIO
from flask import Flask, request, send_file, render_template, flash, redirect, url_for
import fitz  # PyMuPDF
from PIL import Image

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

TARGET_DPI = 300

# ---------- utilidades ----------
def pil_from_pixmap(pix):
    img_bytes = pix.tobytes(output="PNG")
    return Image.open(BytesIO(img_bytes))

def compute_target_pixels_for_image(bbox, page_rect):
    if bbox is None:
        width_in = page_rect.width / 72.0
        height_in = page_rect.height / 72.0
    else:
        width_in = bbox.width / 72.0
        height_in = bbox.height / 72.0
    return int(width_in * TARGET_DPI), int(height_in * TARGET_DPI)

def process_pdf_images(input_pdf_path, output_pdf_path):
    doc = fitz.open(input_pdf_path)
    modified = False

    for page in doc:
        page_images = page.get_images(full=True)
        if not page_images:
            continue

        for img_info in page_images:
            xref = img_info[0]
            try:
                bboxes = page.get_image_bbox(xref)
            except Exception:
                bboxes = None

            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue

            pil_img = pil_from_pixmap(pix)
            pix = None

            if bboxes:
                target_w, target_h = compute_target_pixels_for_image(bboxes[0], page.rect)
                rect = bboxes[0]
            else:
                target_w, target_h = compute_target_pixels_for_image(None, page.rect)
                rect = page.rect

            pil_img = pil_img.convert("L")  # grayscale
            if pil_img.width > target_w or pil_img.height > target_h:
                pil_img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

            out_buf = BytesIO()
            pil_img.save(out_buf, format="PNG", optimize=True)
            out_buf.seek(0)
            new_bytes = out_buf.read()

            try:
                page.insert_image(rect, stream=new_bytes)
                modified = True
            except Exception as e:
                print("Warning:", e)

    if modified:
        doc.save(output_pdf_path, garbage=4, deflate=True)
    else:
        doc.close()
        import shutil
        shutil.copy2(input_pdf_path, output_pdf_path)
        return True

    doc.close()
    return True

def run_ghostscript(input_pdf, output_pdf, preset="balanced"):
    presets = {
        "high_quality": [
            "-dPDFSETTINGS=/prepress",
            "-dColorImageResolution=300",
            "-dGrayImageResolution=300",
        ],
        "balanced": [
            "-dPDFSETTINGS=/ebook",
            "-dColorImageResolution=300",
            "-dGrayImageResolution=300",
        ],
        "max_compression": [
            "-dPDFSETTINGS=/screen",
            "-dColorImageResolution=150",
            "-dGrayImageResolution=150",
        ],
    }
    args = [
        "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-sColorConversionStrategy=Gray",
        "-dProcessColorModel=/DeviceGray",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        "-dCompressFonts=true",
        "-sOutputFile=" + output_pdf,
        input_pdf,
    ]
    args += presets.get(preset, presets["balanced"])

    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0
# --------------------------------

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No se subió archivo")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("Archivo inválido")
            return redirect(request.url)

        filename = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filename)

        with tempfile.TemporaryDirectory() as tmp:
            mid_pdf = os.path.join(tmp, "mid.pdf")
            out_pdf = os.path.join(tmp, "out.pdf")

            process_pdf_images(filename, mid_pdf)
            run_ghostscript(mid_pdf, out_pdf, preset="balanced")

            return send_file(out_pdf, as_attachment=True,
                             download_name="resultado_vucem.pdf")

    return render_template("upload.html")

if __name__ == "__main__":
    app.run(debug=True)
