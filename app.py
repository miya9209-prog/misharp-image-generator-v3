import io
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageOps


# =========================
# Page Config
# =========================
st.set_page_config(page_title="MISHARP 상세페이지 생산기", layout="centered")

# =========================
# Minimal UI Style (여자 직원용 톤다운)
# =========================
st.markdown(
    """
<style>
.block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 3rem; }

h1 { font-size: 2.0rem !important; font-weight: 700 !important; letter-spacing: -0.02em; }
h2 { font-size: 1.18rem !important; font-weight: 650 !important; letter-spacing: -0.01em; }
h3 { font-size: 1.02rem !important; font-weight: 650 !important; letter-spacing: -0.01em; }

p, label, div, span { font-size: 0.95rem; }

.stButton>button { border-radius: 14px; padding: 0.55rem 0.9rem; font-weight: 600; }
.stTextInput input, .stNumberInput input { border-radius: 12px !important; padding: 0.55rem 0.7rem !important; }
section[data-testid="stFileUploaderDropzone"] { border-radius: 14px; padding: 1.1rem; }

img { border-radius: 12px; }
hr { margin: 1.4rem 0; opacity: 0.35; }

.footer {
    margin-top: 3.2rem;
    text-align: center;
    font-size: 0.72rem;
    color: #8b8b8b;
    line-height: 1.65;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Copyright
# =========================
COPYRIGHT_KR = """ⓒ misharpcompany. All rights reserved.
본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.
본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.
"""

COPYRIGHT_EN = """ⓒ misharpcompany. All rights reserved.
This program is the intellectual property of misharpcompany.
Unauthorized copying, distribution, or use is strictly prohibited.
This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally.
"""

# =========================
# Config
# =========================
DEFAULT_WIDTH = 900
DEFAULT_TOP = 120
DEFAULT_GAP = 300
DEFAULT_BOTTOM = 120

IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff"}

# ✅ 핵심: session_state 키는 충돌 없는 이름 사용
STATE_KEY = "misharp_items"


# =========================
# Helpers
# =========================
def safe_name(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "misharp_detail"
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", ".", "(", ")", "[", "]"))
    return (s[:80] or "misharp_detail")


def ext_of(filename: str) -> str:
    fn = (filename or "").lower()
    if "." in fn:
        return fn.rsplit(".", 1)[-1]
    return ""


def is_image(filename: str) -> bool:
    return ext_of(filename) in IMAGE_EXTS


def load_jsx_bytes() -> Optional[bytes]:
    # repo: tools/misharp_detailpage.jsx (정확히)
    path = os.path.join("tools", "misharp_detailpage.jsx")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def open_image_any(upload_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(upload_bytes))
    try:
        img.seek(0)  # GIF 1프레임
    except Exception:
        pass
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    return img


def resize_to_width(img: Image.Image, width: int) -> Image.Image:
    w, h = img.size
    if w == width:
        return img
    scale = width / float(w)
    nh = int(round(h * scale))
    return img.resize((width, max(1, nh)), Image.LANCZOS)


def composite_detail_jpg(
    items: List[Tuple[str, bytes]],
    width: int,
    top: int,
    gap: int,
    bottom: int,
    bg=(255, 255, 255),
) -> Tuple[bytes, dict]:
    resized_images: List[Tuple[str, Image.Image]] = []
    heights: List[int] = []

    for name, data in items:
        img = open_image_any(data)

        # 투명 → 흰 배경 합성
        if img.mode == "RGBA":
            base_rgba = Image.new("RGBA", img.size, (255, 255, 255, 255))
            base_rgba.alpha_composite(img)
            img = base_rgba.convert("RGB")
        else:
            img = img.convert("RGB")

        img = resize_to_width(img, width)
        resized_images.append((name, img))
        heights.append(img.size[1])

    n = len(resized_images)
    total_h = top + bottom + sum(heights) + (gap * (n - 1) if n > 1 else 0)

    canvas = Image.new("RGB", (width, total_h), bg)

    y = top
    placements = []
    for idx, (name, img) in enumerate(resized_images, start=1):
        canvas.paste(img, (0, y))
        placements.append({"index": idx, "filename": name, "y": y, "w": width, "h": img.size[1]})
        y += img.size[1] + gap

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=95, optimize=True)

    meta = {
        "width": width,
        "top": top,
        "gap": gap,
        "bottom": bottom,
        "total_height": total_h,
        "placements": placements,
    }
    return buf.getvalue(), meta


# =========================
# State
# =========================
@dataclass
class Item:
    name: str
    data: bytes


def ensure_state():
    if STATE_KEY not in st.session_state or st.session_state.get(STATE_KEY) is None:
        st.session_state[STATE_KEY] = []


def get_items() -> List[Item]:
    ensure_state()
    items = st.session_state.get(STATE_KEY, [])
    if items is None:
        items = []
        st.session_state[STATE_KEY] = items
    return items


def add_files(files):
    items = get_items()
    for f in files:
        if not is_image(f.name):
            continue
        items.append(Item(name=f.name, data=f.getvalue()))
    st.session_state[STATE_KEY] = items


def move_item(i: int, d: int):
    items = get_items()
    j = i + d
    if 0 <= i < len(items) and 0 <= j < len(items):
        items[i], items[j] = items[j], items[i]
    st.session_state[STATE_KEY] = items


def delete_item(i: int):
    items = get_items()
    if 0 <= i < len(items):
        items.pop(i)
    st.session_state[STATE_KEY] = items


def clear_items():
    st.session_state[STATE_KEY] = []


# =========================
# UI
# =========================
ensure_state()

st.title("MISHARP 상세페이지 생산기")
st.caption("여백 룰 적용 JPG 생성 + Photoshop(스크립트)로 Smart Object PSD 생성")
st.divider()

# 1) Upload
st.subheader("이미지 업로드")
uploaded = st.file_uploader(
    "JPG / PNG / WEBP / GIF 등 여러 장을 업로드하세요",
    accept_multiple_files=True,
    type=None,
)

items_now = get_items()

c1, c2 = st.columns([1, 1])
with c1:
    if st.button("업로드 목록에 추가", type="primary", disabled=not uploaded):
        add_files(uploaded)
        st.rerun()

with c2:
    if st.button("목록 전체 비우기", disabled=(len(items_now) == 0)):
        clear_items()
        st.rerun()

# 2) Preview + ordering
st.divider()
st.subheader("업로드된 이미지 (순서/삭제)")

items_now = get_items()
if not items_now:
    st.write("업로드 후 **업로드 목록에 추가**를 눌러주세요.")
else:
    for i, it in enumerate(items_now):
        cols = st.columns([0.22, 0.50, 0.10, 0.10, 0.08])
        with cols[0]:
            try:
                thumb = open_image_any(it.data)
                thumb.thumbnail((240, 240))
                tb = io.BytesIO()
                thumb.save(tb, format="PNG", optimize=True)
                st.image(tb.getvalue(), use_container_width=True)
            except Exception:
                st.write("IMG")

        with cols[1]:
            st.write(f"**{i+1}. {it.name}**")
            st.caption(f"{len(it.data):,} bytes")

        with cols[2]:
            st.button("↑", key=f"up_{i}", on_click=move_item, args=(i, -1), disabled=(i == 0))
        with cols[3]:
            st.button("↓", key=f"down_{i}", on_click=move_item, args=(i, +1), disabled=(i == len(items_now) - 1))
        with cols[4]:
            st.button("✕", key=f"del_{i}", on_click=delete_item, args=(i,))

# 3) Layout rule
st.divider()
st.subheader("레이아웃 설정")

colA, colB, colC, colD = st.columns(4)
with colA:
    width = st.number_input("폭(px)", min_value=600, max_value=1600, value=DEFAULT_WIDTH, step=10)
with colB:
    top = st.number_input("상단여백(px)", min_value=0, max_value=600, value=DEFAULT_TOP, step=10)
with colC:
    gap = st.number_input("사이여백(px)", min_value=0, max_value=600, value=DEFAULT_GAP, step=10)
with colD:
    bottom = st.number_input("하단여백(px)", min_value=0, max_value=600, value=DEFAULT_BOTTOM, step=10)

base_name = st.text_input("저장 베이스명", value="misharp_detail")
base = safe_name(base_name)

# 4) Generate
st.divider()
st.subheader("출력")

items_now = get_items()
if st.button("생성하기 (JPG + PSD 패키지 ZIP)", type="primary", disabled=(len(items_now) == 0)):
    img_list = [(it.name, it.data) for it in items_now]

    # (A) 상세페이지 1장 JPG 생성
    detail_jpg, meta = composite_detail_jpg(
        img_list,
        width=int(width),
        top=int(top),
        gap=int(gap),
        bottom=int(bottom),
    )

    # (B) job.json 생성 (PS JSX가 바로 읽어서 PSD 생성)
    job = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "layout": {
            "width": int(width),
            "top": int(top),
            "gap": int(gap),
            "bottom": int(bottom),
            "total_height": int(meta["total_height"]),
            "background": "#FFFFFF",
        },
        "images": [
            {
                "index": p["index"],
                "original_filename": p["filename"],
                "zip_filename": f"images/image_{p['index']:03d}.jpg",
                "y": int(p["y"]),
                "w": int(p["w"]),
                "h": int(p["h"]),
                "layer_name": f"IMAGE_{p['index']:03d}",
            }
            for p in meta["placements"]
        ],
        "outputs": {
            "detail_jpg": f"{base}.jpg",
            "psd": "output.psd",
            "jpg_from_psd": "output.jpg",
        },
    }
    job_bytes = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")

    # (C) ZIP 패키지 생성: detail.jpg + job.json + images/ + jsx + copyright
    zip_buf = io.BytesIO()
    jsx_bytes = load_jsx_bytes()

    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 결과 JPG
        z.writestr(f"{base}.jpg", detail_jpg)

        # job.json
        z.writestr("job.json", job_bytes)

        # images/ (폭에 맞춰 정규화 JPG로 저장)
        for idx, it in enumerate(items_now, start=1):
            img = open_image_any(it.data)
            if img.mode == "RGBA":
                base_rgba = Image.new("RGBA", img.size, (255, 255, 255, 255))
                base_rgba.alpha_composite(img)
                img_rgb = base_rgba.convert("RGB")
            else:
                img_rgb = img.convert("RGB")

            img_rgb = resize_to_width(img_rgb, int(width))

            buf = io.BytesIO()
            img_rgb.save(buf, format="JPEG", quality=95, optimize=True)
            z.writestr(f"images/image_{idx:03d}.jpg", buf.getvalue())

        # JSX 포함(레포에 존재할 때만)
        if jsx_bytes:
            z.writestr("misharp_detailpage.jsx", jsx_bytes)

        # copyright
        z.writestr("COPYRIGHT.txt", (COPYRIGHT_KR + "\n\n" + COPYRIGHT_EN).encode("utf-8"))

    st.success("완료! 아래에서 JPG/ZIP을 다운로드하세요.")
    st.image(detail_jpg, caption=f"{base}.jpg (여백룰 적용)", use_container_width=True)

    btn1, btn2 = st.columns([1, 1])
    with btn1:
        st.download_button("상세페이지 JPG 다운로드", data=detail_jpg, file_name=f"{base}.jpg", mime="image/jpeg")
    with btn2:
        st.download_button(
            "PSD 패키지 ZIP 다운로드",
            data=zip_buf.getvalue(),
            file_name=f"{base}_package.zip",
            mime="application/zip",
        )

    st.markdown(
        """
**Photoshop PSD 생성 방법**
- ZIP을 풀면 `misharp_detailpage.jsx` / `job.json` / `images/`가 있습니다.
- Photoshop → 파일 > 스크립트 > 찾아보기… → `misharp_detailpage.jsx` 실행
- Smart Object 레이어가 살아있는 PSD가 생성됩니다.
"""
    )

# Footer
st.markdown(
    f"""
<div class="footer">
{COPYRIGHT_KR.replace("\n","<br>")}
<br><br>
{COPYRIGHT_EN.replace("\n","<br>")}
</div>
""",
    unsafe_allow_html=True,
)
