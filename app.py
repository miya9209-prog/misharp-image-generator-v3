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
# Copyright
# =========================
COPYRIGHT_KR = """ⓒ misharpcompany. All rights reserved.
본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.
본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.
"""

COPYRIGHT_EN = """ⓒ misharpcompany. All rights reserved.
This program is the intellectual property of misharpcompany. Unauthorized copying, distribution, or use is strictly prohibited.
This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally.
"""


# =========================
# Config
# =========================
st.set_page_config(page_title="MISHARP 상세페이지 생산기 v3.1", layout="wide")

DEFAULT_WIDTH = 900
DEFAULT_TOP = 120
DEFAULT_GAP = 80
DEFAULT_BOTTOM = 120

IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff"}


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
    # repo에 tools/misharp_detailpage.jsx로 두면 ZIP에 자동 포함
    path = os.path.join("tools", "misharp_detailpage.jsx")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def open_image_any(upload_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(upload_bytes))
    try:
        img.seek(0)  # gif 1프레임
    except Exception:
        pass
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    return img


def resize_to_width(img: Image.Image, width: int) -> Image.Image:
    # 비율 유지
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
    """
    여러 장 이미지를 '상단/사이/하단 여백' 규칙으로 1장 JPG로 합성
    returns: (jpg_bytes, meta)
    """
    resized_images: List[Tuple[str, Image.Image]] = []
    heights: List[int] = []

    for name, data in items:
        img = open_image_any(data)
        # 투명 처리 → 흰 배경 합성
        if img.mode == "RGBA":
            base = Image.new("RGBA", img.size, (255, 255, 255, 255))
            base.alpha_composite(img)
            img = base.convert("RGB")
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
        placements.append(
            {
                "index": idx,
                "filename": name,
                "y": y,
                "w": width,
                "h": img.size[1],
            }
        )
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
    if "items" not in st.session_state:
        st.session_state.items = []


def add_files(files):
    for f in files:
        if not is_image(f.name):
            # 이미지 외 파일은 여기서 제외 (요구: 여러 JPG로 상세페이지)
            # 필요하면 첨부파일 섹션을 별도로 만들 수 있음
            continue
        st.session_state.items.append(Item(name=f.name, data=f.getvalue()))


def move_item(i: int, d: int):
    items: List[Item] = st.session_state.items
    j = i + d
    if 0 <= i < len(items) and 0 <= j < len(items):
        items[i], items[j] = items[j], items[i]


def delete_item(i: int):
    items: List[Item] = st.session_state.items
    if 0 <= i < len(items):
        items.pop(i)


# =========================
# UI
# =========================
ensure_state()

st.title("MISHARP 상세페이지 생산기 v3.1")
st.caption("여러 장 JPG → (여백룰 적용) 1장 JPG 생성 + (Smart Object PSD는 Photoshop JSX로 생성)")

left, right = st.columns([1.05, 0.95], gap="large")

with left:
    st.subheader("1) 이미지 업로드 (여러 장 / 개수 제한 없음)")
    uploaded = st.file_uploader(
        "JPG/PNG/WEBP/GIF 등 이미지 여러 장을 올리세요",
        accept_multiple_files=True,
        type=None,
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("업로드 목록에 추가", type="primary", disabled=not uploaded):
            add_files(uploaded)
    with c2:
        if st.button("목록 전체 비우기", disabled=(len(st.session_state.items) == 0)):
            st.session_state.items = []

    st.divider()
    st.subheader("2) 상세페이지 룰(여백 설정)")
    width = st.number_input("상세페이지 폭(px)", min_value=600, max_value=1600, value=DEFAULT_WIDTH, step=10)
    top = st.number_input("최상단 흰여백(px)", min_value=0, max_value=600, value=DEFAULT_TOP, step=10)
    gap = st.number_input("사진 사이 여백(px)", min_value=0, max_value=600, value=DEFAULT_GAP, step=10)
    bottom = st.number_input("최하단 흰여백(px)", min_value=0, max_value=600, value=DEFAULT_BOTTOM, step=10)

    base_name = st.text_input("저장 베이스명", value="misharp_detail")

with right:
    st.subheader("3) 미리보기 / 순서 변경 / 삭제")
    items: List[Item] = st.session_state.items
    if not items:
        st.write("왼쪽에서 업로드 후 **업로드 목록에 추가**를 눌러주세요.")
    else:
        for i, it in enumerate(items):
            cols = st.columns([0.22, 0.48, 0.10, 0.10, 0.10])
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
                st.button("↓", key=f"down_{i}", on_click=move_item, args=(i, +1), disabled=(i == len(items)-1))
            with cols[4]:
                st.button("🗑", key=f"del_{i}", on_click=delete_item, args=(i,))

st.divider()
st.subheader("4) 결과물 생성")

items: List[Item] = st.session_state.items
base = safe_name(base_name)

if st.button("상세페이지 생성하기 (JPG + PSD패키지 ZIP)", type="primary", disabled=(len(items) == 0)):
    # 1) JPG 합성
    img_list = [(it.name, it.data) for it in items]
    detail_jpg, meta = composite_detail_jpg(
        img_list,
        width=int(width),
        top=int(top),
        gap=int(gap),
        bottom=int(bottom),
    )

    # 2) job.json (JSX가 그대로 PSD 만들 수 있게 placements 포함)
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
                # ZIP 안에서 JSX가 안정적으로 찾을 수 있게 정규화 파일명도 제공
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

    # 3) ZIP 패키지 만들기
    zip_buf = io.BytesIO()
    jsx_bytes = load_jsx_bytes()

    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 최종 jpg
        z.writestr(f"{base}.jpg", detail_jpg)

        # job.json
        z.writestr("job.json", job_bytes)

        # images/ 정규화된 jpg로 넣기 (포토샵 안정성)
        for idx, it in enumerate(items, start=1):
            img = open_image_any(it.data)
            # 투명 → 흰 배경 합성 후 JPG 저장
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

        # JSX 포함
        if jsx_bytes:
            z.writestr("misharp_detailpage.jsx", jsx_bytes)

        # 카피라이트 텍스트도 패키지에 동봉
        z.writestr("COPYRIGHT.txt", (COPYRIGHT_KR + "\n\n" + COPYRIGHT_EN).encode("utf-8"))

    # 4) 화면 표시 + 다운로드 버튼
    st.success("생성 완료! 아래에서 JPG와 ZIP을 다운로드하세요.")
    st.image(detail_jpg, caption=f"{base}.jpg (여백룰 적용)", use_container_width=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.download_button("상세페이지 JPG 다운로드", data=detail_jpg, file_name=f"{base}.jpg", mime="image/jpeg")
    with c2:
        st.download_button("job.json 다운로드", data=job_bytes, file_name=f"{base}_job.json", mime="application/json")
    with c3:
        st.download_button(
            "PSD 패키지 ZIP 다운로드 (추천)",
            data=zip_buf.getvalue(),
            file_name=f"{base}_package.zip",
            mime="application/zip",
        )

    st.markdown(
        """
### Photoshop에서 PSD 생성(레이어 살아있는 고급개체)
1) ZIP을 풀어 폴더에 `job.json`, `images/` 폴더가 있는지 확인  
2) 포토샵 → **파일 > 스크립트 > 찾아보기…** → `misharp_detailpage.jsx` 실행  
3) **ZIP을 푼 폴더**를 선택  
4) 같은 폴더에 `output.psd`, `output.jpg` 생성
"""
    )

st.divider()
st.markdown(COPYRIGHT_KR)
st.markdown("")
st.markdown(COPYRIGHT_EN)
