import io
import json
import os
import zipfile
from datetime import datetime

import streamlit as st
from PIL import Image

st.set_page_config(page_title="MISHARP 이미지 생성기 v3.1", layout="centered")

st.title("MISHARP 이미지 생성기 v3.1")
st.caption("v3 동일 방식: Streamlit은 작업파일 생성(개별+ZIP) → Photoshop 스크립트가 PSD+JPG 출력")

TEMPLATE_PATH = os.path.join("assets", "template.psd")

if not os.path.exists(TEMPLATE_PATH):
    st.error("assets/template.psd 파일이 없습니다. repo에 템플릿 PSD를 업로드해 주세요.")
    st.stop()

with open(TEMPLATE_PATH, "rb") as f:
    template_psd_bytes = f.read()

# 입력 UI
up = st.file_uploader("치환할 이미지 업로드", type=["png", "jpg", "jpeg", "webp"])
product_name = st.text_input("상품명", value="", placeholder="예) 뮤 반오픈 카라 스트라이프 니트")

st.divider()
st.subheader("출력 옵션")
col1, col2 = st.columns(2)
with col1:
    out_basename = st.text_input("파일 베이스명", value="misharp_job", help="ZIP/파일명 기본값")
with col2:
    force_png = st.checkbox("입력 이미지를 PNG로 고정 저장", value=True, help="포토샵 스크립트 호환성↑")

st.info("결과 PSD/JPG는 웹에서 생성되지 않습니다. 다운로드한 작업파일을 포토샵 스크립트로 처리해 PSD+JPG를 얻는 구조입니다.")

def _to_png_bytes(upload_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(upload_bytes))
    # 투명/색공간 이슈 방지
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    # PNG로 저장
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "misharp_job"
    # 아주 간단한 정리(공백→_)
    s = s.replace(" ", "_")
    return "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", "."))[:80] or "misharp_job"

def build_package(upload_bytes: bytes, product_name: str):
    # input.png
    if force_png:
        input_png = _to_png_bytes(upload_bytes)
    else:
        # 그래도 포토샵 안정성을 위해 PNG 권장
        input_png = _to_png_bytes(upload_bytes)

    # job.json
    job = {
        "product_name": (product_name or "").strip(),
        "image_layer": "IMAGE_1",
        "text_layer": "상품명",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    job_json = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")

    # zip
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("template.psd", template_psd_bytes)
        z.writestr("input.png", input_png)
        z.writestr("job.json", job_json)
        # 스크립트도 같이 넣어주면 직원이 덜 헤맴
        jsx_path = os.path.join("tools", "misharp_apply.jsx")
        if os.path.exists(jsx_path):
            with open(jsx_path, "rb") as f:
                z.writestr("misharp_apply.jsx", f.read())

    return input_png, job_json, zbuf.getvalue()

disabled = up is None
gen = st.button("작업파일 생성", type="primary", disabled=disabled)

if gen and up is not None:
    base = _safe_filename(out_basename)
    input_png, job_json, zip_bytes = build_package(up.getvalue(), product_name)

    st.success("생성 완료! 아래에서 개별 다운로드 또는 ZIP 다운로드를 선택하세요.")
    st.caption("포토샵에서 misharp_apply.jsx 실행 → output.psd / output.jpg 생성")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "input.png 다운로드",
            data=input_png,
            file_name=f"{base}_input.png",
            mime="image/png",
        )
    with c2:
        st.download_button(
            "job.json 다운로드",
            data=job_json,
            file_name=f"{base}_job.json",
            mime="application/json",
        )
    with c3:
        st.download_button(
            "template.psd 다운로드",
            data=template_psd_bytes,
            file_name=f"{base}_template.psd",
            mime="application/octet-stream",
        )

    st.download_button(
        "ZIP 한 번에 다운로드 (추천)",
        data=zip_bytes,
        file_name=f"{base}.zip",
        mime="application/zip",
    )

    st.divider()
    st.subheader("포토샵 처리 방법(요약)")
    st.markdown(
        """
1) ZIP을 풀어서 한 폴더에 `template.psd`, `input.png`, `job.json`이 있도록 둡니다.  
2) 포토샵 실행 → **파일 > 스크립트 > 찾아보기…** → `misharp_apply.jsx` 선택  
3) 폴더 선택 창이 뜨면 위 폴더를 선택  
4) 같은 폴더에 `output.psd`, `output.jpg`가 생성됩니다.
        """.strip()
    )
