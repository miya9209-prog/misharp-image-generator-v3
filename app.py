import io
import os
import re
import json
import zipfile
from typing import List, Tuple

import streamlit as st
from PIL import Image

# -----------------
# 기본값 (A안)
# -----------------
APP_TITLE = "MISHARP 상세페이지 생성기 v3.3"
MAX_PER_PSD = 6
DEFAULT_GAP = 300
DEFAULT_TOP = 300
DEFAULT_BOTTOM = 300
DEFAULT_BG = (255, 255, 255)

Image.MAX_IMAGE_PIXELS = None


# -----------------
# 유틸
# -----------------
def clean_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^\w\-.()가-힣 ]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name or "misharp"


def is_image(name: str) -> bool:
    ext = os.path.splitext(name.lower())[1]
    return ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]


def open_image_bytes(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img.convert("RGBA")


def rgba_to_rgb_white(img_rgba: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    bg_img = Image.new("RGBA", img_rgba.size, bg + (255,))
    bg_img.alpha_composite(img_rgba)
    return bg_img.convert("RGB")


def make_stacked_jpg(images: List[Tuple[str, bytes]], gap: int, top: int, bottom: int) -> bytes:
    pil = []
    sizes = []
    max_w = 0

    for n, b in images:
        if not is_image(n):
            continue
        im = open_image_bytes(b)
        w, h = im.size
        max_w = max(max_w, w)
        pil.append(im)
        sizes.append((w, h))

    if not pil:
        raise ValueError("이미지(JPG/PNG/WEBP/GIF 등)를 1개 이상 올려주세요.")

    total_h = top + bottom + sum(h for _, h in sizes) + gap * (len(sizes) - 1)
    canvas = Image.new("RGB", (max_w, total_h), DEFAULT_BG)

    y = top
    for im, (w, h) in zip(pil, sizes):
        x = (max_w - w) // 2
        rgb = rgba_to_rgb_white(im, DEFAULT_BG)
        canvas.paste(rgb, (x, y))
        y += h + gap

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()


def build_jobs(images: List[Tuple[str, bytes]], gap: int, top: int, bottom: int, base_name: str):
    only = [(n, b) for n, b in images if is_image(n)]
    if not only:
        raise ValueError("이미지(JPG/PNG/WEBP/GIF 등)를 1개 이상 올려주세요.")

    # 전체 인덱스별 zip 내부 경로
    image_payloads = []
    for idx, (n, b) in enumerate(only, start=1):
        ext = os.path.splitext(n)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]:
            ext = ".jpg"
        image_payloads.append((idx, ext, b))

    jobs = []
    for start in range(0, len(only), MAX_PER_PSD):
        chunk = only[start:start + MAX_PER_PSD]

        # 사이즈 산출
        max_w = 0
        sizes = []
        for n, b in chunk:
            im = open_image_bytes(b)
            w, h = im.size
            max_w = max(max_w, w)
            sizes.append((w, h))

        total_h = top + bottom + sum(h for _, h in sizes) + gap * (len(sizes) - 1)

        # 각 이미지 배치 y 좌표
        y = top
        items = []
        for i, ((n, _), (w, h)) in enumerate(zip(chunk, sizes), start=1):
            global_idx = start + i
            ext = os.path.splitext(n)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]:
                ext = ".jpg"
            items.append({
                "zip_filename": f"images/image_{global_idx:03d}{ext}",
                "layer_name": f"IMAGE_{global_idx:03d}",
                "y": int(y),
            })
            y += h + gap

        part_no = (start // MAX_PER_PSD) + 1
        jobs.append({
            "version": "misharp_detailpage_job_v3",
            "base_name": base_name,
            "part_no": part_no,
            "layout": {
                "width": int(max_w),
                "total_height": int(total_h),
                "gap": int(gap),
                "top_margin": int(top),
                "bottom_margin": int(bottom),
                "center_align": True,
            },
            "images": items,
        })

    return jobs, image_payloads


def load_jsx_from_repo():
    """
    repo 루트/tools/misharp_detailpage.jsx 또는 repo 루트/misharp_detailpage.jsx를 우선 사용
    (없으면 빈 문자열)
    """
    candidates = [
        os.path.join(os.getcwd(), "tools", "misharp_detailpage.jsx"),
        os.path.join(os.getcwd(), "misharp_detailpage.jsx"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def make_zip_package(images: List[Tuple[str, bytes]], gap: int, top: int, bottom: int, base_name: str) -> bytes:
    jobs, image_payloads = build_jobs(images, gap, top, bottom, base_name)

    jsx_text = load_jsx_from_repo()
    if not jsx_text:
        raise ValueError("repo에 tools/misharp_detailpage.jsx 파일이 없습니다. (JSX를 먼저 추가해 주세요)")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # JSX 루트로
        z.writestr("misharp_detailpage.jsx", jsx_text)

        # README
        z.writestr(
            "README.txt",
            "\n".join([
                "MISHARP 상세페이지 패키지",
                "",
                "사용법",
                "1) ZIP 압축 해제",
                "2) Photoshop 실행",
                "3) 파일 > 스크립트 > 찾아보기... > misharp_detailpage.jsx 선택",
                "4) part_01, part_02... 순서대로 PSD가 자동 생성되어 '바로 열립니다'(Smart Object 유지).",
                "",
                f"- 기본 이미지 간격: {gap}px",
                f"- 상단/하단 여백: {top}px / {bottom}px",
                f"- 6장 초과 시 자동 분할 (A안)",
                "",
                "ⓒ misharpcompany. All rights reserved.",
                "본 프로그램은 미샵컴퍼니 내부 직원 전용입니다.",
            ])
        )

        # part 폴더들 + job.json + images
        for job in jobs:
            part = f"part_{job['part_no']:02d}"
            z.writestr(f"{part}/job.json", json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8"))

            # 이 파트가 필요한 이미지 번호만 넣기
            need_nums = []
            for it in job["images"]:
                base = os.path.basename(it["zip_filename"])
                m = re.search(r"image_(\d+)\.", base, re.IGNORECASE)
                if m:
                    need_nums.append(int(m.group(1)))
            need_set = set(need_nums)

            for idx, ext, data in image_payloads:
                if idx in need_set:
                    z.writestr(f"{part}/images/image_{idx:03d}{ext}", data)

    return buf.getvalue()


# -----------------
# Streamlit State
# -----------------
def init_state():
    if "file_list" not in st.session_state:
        st.session_state.file_list = []


def add_files(files):
    if not files:
        return
    for f in files:
        name = clean_filename(f.name)
        data = f.getvalue()
        st.session_state.file_list.append({"name": name, "data": data})


def move_item(i: int, d: int):
    lst = st.session_state.file_list
    j = i + d
    if 0 <= i < len(lst) and 0 <= j < len(lst):
        lst[i], lst[j] = lst[j], lst[i]


def remove_item(i: int):
    lst = st.session_state.file_list
    if 0 <= i < len(lst):
        lst.pop(i)


def clear_all():
    st.session_state.file_list = []


# -----------------
# UI
# -----------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.markdown(
        """
        <style>
        .block-container { max-width: 1040px; padding-top: 2.0rem; padding-bottom: 2.0rem; }
        h1 { font-size: 30px !important; font-weight: 600 !important; letter-spacing:-0.02em; }
        h2,h3,h4 { font-weight: 600 !important; }
        .muted { color: rgba(255,255,255,0.70); font-size: 13px; line-height: 1.6; }
        .card { border:1px solid rgba(255,255,255,0.10); border-radius:14px; padding:14px 16px; background: rgba(255,255,255,0.03); }
        .tiny { font-size: 11px; color: rgba(255,255,255,0.60); line-height: 1.55; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("MISHARP 상세페이지 생성기")
    st.markdown("<div class='muted'>여러 장 업로드 → <b>상세페이지 JPG</b> + <b>PSD 패키지(6장 단위 자동분할)</b></div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    # ✅ 파일명 입력칸 복구
    base_name = st.text_input("파일명(상품명) — 출력 파일명에 사용", value="misharp_detailpage")
    base_name = clean_filename(base_name)

    st.markdown("#### 1) 파일 업로드")
    uploaded = st.file_uploader(
        "JPG/PNG/WEBP/GIF 등 여러 장 업로드 (개수 제한 없음)",
        accept_multiple_files=True,
        type=None,
        label_visibility="collapsed",
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("업로드 목록에 추가", use_container_width=True):
            add_files(uploaded)
    with c2:
        if st.button("목록 전체 비우기", use_container_width=True, disabled=(len(st.session_state.file_list) == 0)):
            clear_all()

    st.markdown("#### 2) 여백 설정")
    gap = st.number_input("이미지들 간 여백(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)
    top = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP, step=10)
    bottom = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_BOTTOM, step=10)

    st.markdown("<div class='tiny'>기본값: 이미지 간격 300px / 상·하단 300px · 6장 초과 시 PSD 자동 분할(A안)</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 3) 업로드 목록 (순서 조정)")
    if len(st.session_state.file_list) == 0:
        st.info("업로드 후 ‘업로드 목록에 추가’를 눌러주세요.")
    else:
        for idx, it in enumerate(st.session_state.file_list):
            colL, colR = st.columns([0.18, 0.82], gap="small")
            with colL:
                up = st.button("↑", key=f"up_{idx}", disabled=(idx == 0))
                dn = st.button("↓", key=f"dn_{idx}", disabled=(idx == len(st.session_state.file_list) - 1))
                rm = st.button("삭제", key=f"rm_{idx}")
                if up:
                    move_item(idx, -1); st.rerun()
                if dn:
                    move_item(idx, +1); st.rerun()
                if rm:
                    remove_item(idx); st.rerun()

            with colR:
                st.markdown(f"**{idx+1:02d}.** {it['name']}")
                if is_image(it["name"]):
                    try:
                        im = open_image_bytes(it["data"])
                        st.image(rgba_to_rgb_white(im), use_container_width=True)
                    except Exception:
                        st.caption("미리보기 불가 (이미지 손상/형식 문제 가능)")
                else:
                    st.caption("이미지 외 파일(참고용) — 상세페이지 JPG/PSD엔 포함되지 않음")

    st.markdown("### 4) 생성")

    items = [(it["name"], it["data"]) for it in st.session_state.file_list]
    can_run = any(is_image(n) for n, _ in items)

    colA, colB = st.columns([1, 1], gap="large")
    with colA:
        make_jpg_flag = st.checkbox("상세페이지 JPG 생성", value=True)
    with colB:
        make_zip_flag = st.checkbox("PSD 패키지 ZIP 생성(JSX 포함)", value=True)

    if st.button("생성하기", type="primary", use_container_width=True, disabled=not can_run):
        try:
            if make_jpg_flag:
                jpg_bytes = make_stacked_jpg(items, int(gap), int(top), int(bottom))
                st.download_button(
                    "📥 상세페이지 JPG 다운로드",
                    data=jpg_bytes,
                    file_name=f"{base_name}.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )

            if make_zip_flag:
                zip_bytes = make_zip_package(items, int(gap), int(top), int(bottom), base_name)
                st.download_button(
                    "📥 PSD 패키지 ZIP 다운로드 (misharp_detailpage.jsx 포함)",
                    data=zip_bytes,
                    file_name=f"{base_name}_psd_package.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

            st.success("완료! 다운로드 버튼으로 받아가세요.")

        except Exception as e:
            st.error(f"생성 중 오류: {e}")

    st.markdown("---")
    st.markdown(
        """
<div class='tiny'>
ⓒ misharpcompany. All rights reserved.<br/>
본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.<br/>
본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.<br/><br/>
ⓒ misharpcompany. All rights reserved.<br/>
This program is the intellectual property of misharpcompany. Unauthorized copying, distribution, or use is strictly prohibited.<br/>
This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally.
</div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
