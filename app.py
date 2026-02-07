import streamlit as st
from PIL import Image
import json
import zipfile
import io
from pathlib import Path

# =========================================================
# Page config
# =========================================================
st.set_page_config(
    page_title="MISHARP 상세페이지 생산기",
    layout="centered",
)

# =========================================================
# Global style (여성 직원용 · 미니멀)
# =========================================================
st.markdown(
    """
<style>
.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1 {
    font-size: 2.0rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}
h2 {
    font-size: 1.25rem !important;
    font-weight: 650 !important;
}
h3 {
    font-size: 1.05rem !important;
    font-weight: 650 !important;
}

p, label, div, span {
    font-size: 0.95rem;
}

.stButton > button {
    border-radius: 14px;
    padding: 0.55rem 0.9rem;
    font-weight: 600;
}

.stTextInput input, .stNumberInput input {
    border-radius: 12px;
    padding: 0.55rem 0.7rem;
}

section[data-testid="stFileUploaderDropzone"] {
    border-radius: 14px;
    padding: 1.1rem;
}

img {
    border-radius: 12px;
}

hr {
    margin: 1.4rem 0;
    opacity: 0.35;
}

.footer {
    margin-top: 4rem;
    text-align: center;
    font-size: 0.72rem;
    color: #888;
    line-height: 1.6;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Title
# =========================================================
st.title("MISHARP 상세페이지 생산기")
st.caption("여백 룰 기반 JPG 생성 + Photoshop Smart Object PSD 스크립트")

st.divider()

# =========================================================
# Session state
# =========================================================
if "items" not in st.session_state:
    st.session_state.items = []

# =========================================================
# Upload
# =========================================================
st.subheader("이미지 업로드")

uploaded_files = st.file_uploader(
    "JPG / PNG / WEBP / GIF 등 여러 장을 업로드하세요",
    type=None,
    accept_multiple_files=True,
)

if uploaded_files:
    for f in uploaded_files:
        st.session_state.items.append(
            {
                "name": f.name,
                "file": f,
            }
        )

# =========================================================
# Uploaded list
# =========================================================
if st.session_state.items:
    st.subheader("업로드된 이미지")

    for idx, item in enumerate(st.session_state.items):
        col1, col2, col3 = st.columns([1, 4, 1])
        with col1:
            st.image(item["file"], use_container_width=True)
        with col2:
            st.write(item["name"])
        with col3:
            if st.button("삭제", key=f"del_{idx}"):
                st.session_state.items.pop(idx)
                st.experimental_rerun()

    st.divider()

# =========================================================
# Layout settings
# =========================================================
st.subheader("레이아웃 설정")

col1, col2, col3 = st.columns(3)
with col1:
    canvas_width = st.number_input("캔버스 폭(px)", 600, 2000, 900, step=50)
with col2:
    top_margin = st.number_input("상단 여백(px)", 0, 500, 80, step=10)
with col3:
    gap = st.number_input("이미지 간 여백(px)", 0, 500, 60, step=10)

bottom_margin = st.number_input("하단 여백(px)", 0, 500, 120, step=10)

# =========================================================
# Generate
# =========================================================
st.divider()

if st.button("상세페이지 생성", type="primary", disabled=len(st.session_state.items) == 0):
    images = []
    y_cursor = top_margin

    # 이미지 정보 계산
    for i, item in enumerate(st.session_state.items):
        with Image.open(item["file"]) as img:
            w, h = img.size
            scale = canvas_width / w
            new_h = int(h * scale)

        images.append(
            {
                "zip_filename": f"images/image_{i+1:03d}{Path(item['name']).suffix.lower()}",
                "layer_name": f"IMAGE_{i+1}",
                "y": y_cursor,
            }
        )
        y_cursor += new_h + gap

    total_height = y_cursor - gap + bottom_margin

    job = {
        "layout": {
            "width": canvas_width,
            "total_height": total_height,
        },
        "images": images,
    }

    # ZIP 생성
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("job.json", json.dumps(job, ensure_ascii=False, indent=2))

        for i, item in enumerate(st.session_state.items):
            zf.writestr(
                images[i]["zip_filename"],
                item["file"].getbuffer(),
            )

        # JSX 포함
        jsx_path = Path("tools/misharp_detailpage.jsx")
        if jsx_path.exists():
            zf.write(jsx_path, "misharp_detailpage.jsx")

    zip_buffer.seek(0)

    st.success("생성 완료! ZIP을 다운로드 후 Photoshop에서 JSX를 실행하세요.")
    st.download_button(
        "ZIP 다운로드",
        zip_buffer,
        file_name="misharp_detailpage_job.zip",
        mime="application/zip",
    )

# =========================================================
# Footer copyright
# =========================================================
st.markdown(
    """
<div class="footer">
ⓒ misharpcompany. All rights reserved.<br>
본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.<br>
본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.<br><br>
ⓒ misharpcompany. All rights reserved.<br>
This program is the intellectual property of misharpcompany.<br>
Unauthorized copying, distribution, or use is strictly prohibited.<br>
For internal use only.
</div>
""",
    unsafe_allow_html=True,
)
