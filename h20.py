import customtkinter as ctk
import requests
from bs4 import BeautifulSoup
import os
from tkinter import filedialog
from urllib.parse import urljoin, urlparse
from PIL import Image
import shutil
import time

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("600x400")
app.title("Manga → PDF Downloader")

# Variables
url_var = ctk.StringVar()
folder_var = ctk.StringVar()
progress_var = ctk.DoubleVar()
convert_pdf = ctk.BooleanVar(value=True)
keep_images = ctk.BooleanVar(value=False)
is_running = False
scale_factor = 1.0  # Scale factor for UI scaling

def scale_up():
    """Increase UI scale"""
    global scale_factor
    if scale_factor < 2.0:
        scale_factor += 0.1
        scale_label.configure(text=f"{int(scale_factor * 100)}%")
        app.geometry(f"{int(600 * scale_factor)}x{int(400 * scale_factor)}")

def scale_down():
    """Decrease UI scale"""
    global scale_factor
    if scale_factor > 0.5:
        scale_factor -= 0.1
        scale_label.configure(text=f"{int(scale_factor * 100)}%")
        app.geometry(f"{int(600 * scale_factor)}x{int(400 * scale_factor)}")

def pick_folder():
    path = filedialog.askdirectory()
    if path:
        folder_var.set(path)

def get_chapter_name(url):
    path = urlparse(url).path.strip('/')
    if not path:
        return "chapter"
    parts = path.split('/')
    if len(parts) == 0 or not parts[-1]:  # Check if the last part exists
        return "chapter"
    return parts[-1].replace('-', '_').replace('/', '_')

def find_images(soup, base_url):
    """Try common manga reader patterns first"""
    candidates = []

    # Best selectors (most used in 2024-2026)
    selectors = [
        'img.wp-manga-chapter-img',
        'div.reading-content img',
        'div.page-break img',
        '#readerarea img',
        'img[alt*="page"]',
        'img[data-src*="manga"], img[src*="manga"]'
    ]

    for sel in selectors:
        for img in soup.select(sel):
            src = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
            if src and 'http' in src.lower():
                full = urljoin(base_url, src.strip())
                if full not in candidates:
                    candidates.append(full)

    # Fallback: any big image that looks like content
    if len(candidates) < 3:
        for img in soup.find_all('img'):
            src = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
            if not src or not src.strip():  # Ensure src is not empty
                continue
            full = urljoin(base_url, src.strip())
            if any(x in full.lower() for x in ['logo', 'banner', 'icon', 'avatar', 'button', 'footer']):
                continue
            if full not in candidates:
                candidates.append(full)

    return candidates

def images_to_pdf(folder, pdf_path):
    images = []
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith(('.jpg','jpeg','png','webp','gif')):
            try:
                img = Image.open(os.path.join(folder, f))
                if img.mode in ('RGBA', 'LA'):
                    bg = Image.new('RGB', img.size, (255,255,255))
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
            except:
                continue

    if not images:
        return False

    try:
        images[0].save(pdf_path, save_all=True, append_images=images[1:],
                       resolution=100.0, quality=90, optimize=True)
        for img in images:
            img.close()
        return True
    except:
        return False

def start_download():
    global is_running
    if is_running:
        status_label.configure(text="Already running bro...", text_color="orange")
        return

    url = url_var.get().strip()
    folder = folder_var.get().strip()

    if not url or not url.startswith('http'):
        status_label.configure(text="Put a real URL man", text_color="red")
        return
    if not folder:
        status_label.configure(text="Choose a folder first", text_color="red")
        return

    is_running = True
    download_btn.configure(state="disabled")
    status_label.configure(text="Fetching page...", text_color="yellow")
    progress_var.set(0)
    app.update()

    try:
        headers = {'User-Agent': 'Mozilla/5.0 Chrome/120'}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, 'html.parser')
        images = find_images(soup, url)

        if not images:
            status_label.configure(text="No images found — site not supported or blocked", text_color="red")
            return

        chapter = get_chapter_name(url)
        chap_folder = os.path.join(folder, chapter)
        os.makedirs(chap_folder, exist_ok=True)

        total_images.configure(text=f"Found {len(images)} pages")
        status_label.configure(text=f"Downloading {len(images)} pages...", text_color="cyan")

        for i, img_url in enumerate(images, 1):
            try:
                ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                fname = f"page_{i:03d}{ext}"
                path = os.path.join(chap_folder, fname)

                with requests.get(img_url, headers=headers, stream=True, timeout=15) as resp:
                    resp.raise_for_status()
                    with open(path, 'wb') as f:
                        for chunk in resp.iter_content(16*1024):
                            f.write(chunk)

                progress_var.set((i / len(images)) * 0.8)
                current_image.configure(text=f"Page {i}/{len(images)}")
                app.update()
                time.sleep(0.25)   # be nice to servers

            except:
                continue

        # PDF part
        if convert_pdf.get() and images:
            pdf_file = os.path.join(folder, f"{chapter}.pdf")
            status_label.configure(text="Making PDF...", text_color="cyan")
            app.update()

            if images_to_pdf(chap_folder, pdf_file):
                progress_var.set(1.0)
                if not keep_images.get():
                    shutil.rmtree(chap_folder, ignore_errors=True)
                    msg = f"Done! → {chapter}.pdf"
                else:
                    msg = f"Done! PDF + images in {chapter}/"
                status_label.configure(text=msg, text_color="green")
            else:
                status_label.configure(text="PDF failed — but images are saved", text_color="orange")

        else:
            status_label.configure(text=f"Done! Images saved in {chapter}/", text_color="green")
            progress_var.set(1.0)

    except Exception as e:
        status_label.configure(text=f"Failed: {str(e)}", text_color="red")
        progress_var.set(0)

    finally:
        is_running = False
        download_btn.configure(state="normal")

def reset():
    url_var.set("")
    folder_var.set("")
    progress_var.set(0)
    total_images.configure(text="Found: 0")
    current_image.configure(text="")
    status_label.configure(text="Cleared", text_color="gray")

# ── UI ────────────────────────────────────────────────

ctk.CTkLabel(app, text="Manga Chapter → PDF", font=("Arial", 22, "bold")).pack(pady=12)

ctk.CTkLabel(app, text="Chapter URL").pack()
ctk.CTkEntry(app, width=520, textvariable=url_var,
             placeholder_text="https://mangaread.org/manga-name/chapter-123/").pack(pady=6)

ctk.CTkButton(app, text="Choose Folder", command=pick_folder).pack(pady=8)
ctk.CTkLabel(app, textvariable=folder_var, wraplength=500, text_color="gray").pack()

frame = ctk.CTkFrame(app, fg_color="transparent")
frame.pack(pady=10)
ctk.CTkCheckBox(frame, text="Make PDF", variable=convert_pdf).pack(side="left", padx=20)
ctk.CTkCheckBox(frame, text="Keep images", variable=keep_images).pack(side="left", padx=20)

total_images = ctk.CTkLabel(app, text="Found: 0")
total_images.pack()
current_image = ctk.CTkLabel(app, text="")
current_image.pack()

ctk.CTkProgressBar(app, width=520, variable=progress_var).pack(pady=12)

btn_frame = ctk.CTkFrame(app, fg_color="transparent")
btn_frame.pack(pady=10)

# Scale controls
scale_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
scale_frame.pack(side="left", padx=(0, 20))
ctk.CTkLabel(scale_frame, text="Scale:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
ctk.CTkButton(scale_frame, text="−", width=35, height=30, command=scale_down, 
              font=ctk.CTkFont(size=14)).pack(side="left", padx=3)
ctk.CTkButton(scale_frame, text="+", width=35, height=30, command=scale_up, 
              font=ctk.CTkFont(size=14)).pack(side="left", padx=3)
scale_label = ctk.CTkLabel(scale_frame, text="100%", font=ctk.CTkFont(size=12, weight="bold"))
scale_label.pack(side="left", padx=5)

download_btn = ctk.CTkButton(btn_frame, text="Download", command=start_download,
                             fg_color="#2ecc71", hover_color="#27ae60", width=180)
download_btn.pack(side="left", padx=10)
ctk.CTkButton(btn_frame, text="Clear", command=reset,
              fg_color="#e74c3c", hover_color="#c0392b", width=140).pack(side="left")

status_label = ctk.CTkLabel(app, text="Ready", font=("Arial", 13))
status_label.pack(pady=12)

app.mainloop()