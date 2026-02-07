import io
import json
import zipfile
from datetime import datetime

import streamlit as st
from PIL import Image

# =========================
# MISHARP 이미지 생성기 v3.1
# (v3 동일 방식)
# - Streamlit: 작업파일 생성(이미지 + job.json + (선택) ZIP)
# - Photoshop JSX: PSD 선택 + 이미지 선택 + job.json 선택 → PSD+JPG 출력
# =========================

st.set_page_config(page_title="MISHARP 이미지 생성기 v3.1", layout="centered")

st.title("MISHARP 이미지 생성기 v3.1")
st.caption("v3 동일 방식: Streamlit은 작업파일 생성(개별+ZIP) → Photoshop 스크립트가 PSD+JPG 출력")
st.info("중요: 이 앱은 PSD를 생성/보관하지 않습니다. 템플릿 PSD는 포토샵 스크립트 실행 시 직접 선택합니다.")

# ---------- 입력 UI ----------
up = st.file_uploader("치환할 이미지 업로드", type=["png", "jpg", "jpeg", "webp"])
product_name = st.text_input("상품명", value="", placeholder="예) 뮤 반오픈 카라 스트라이프 니트")

st.divider()
st.subheader("작업파일 생성 옵션")

col1, col2 = st.columns(2)
with col1:
    base_name = st.text_input("파일 베이스명", value="misharp_job", help="다운로드 파일명 앞부분(예: misharp_job_input.png)")
with col2:
    force_png = st.checkbox("이미지를 PNG로 변환해 저장", value=True, help="포토샵 처리 호환성/안정성↑")

def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "misharp_job"
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", "."))[:80]
    return s or "misharp_job"

def _to_png_bytes(upload_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(upload_bytes))
    # 색공간/투명도 이슈 방지
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def build_outputs(upload_bytes: bytes, product_name: str):
    # (1) 이미지 bytes (PNG 권장)
    input_png = _to_png_bytes(upload_bytes) if force_png else _to_png_bytes(upload_bytes)

    # (2) job.json bytes
    job = {
        "product_name": (product_name or "").strip(),
        # 아래 값은 참고용(포토샵 스크립트는 고정 레이어명 사용)
        "image_layer": "IMAGE_1",
        "text_layer": "상품명",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    job_json = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")

    # (3) ZIP bytes (input + job만 포함)
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("input.png", input_png)
        z.writestr("job.json", job_json)

    return input_png, job_json, zbuf.getvalue()

disabled = up is None
gen = st.button("작업파일 생성", type="primary", disabled=disabled)

if gen and up is not None:
    base = _safe_filename(base_name)
    input_png, job_json, zip_bytes = build_outputs(up.getvalue(), product_name)

    st.success("생성 완료! 아래에서 개별 다운로드 또는 ZIP 다운로드를 선택하세요.")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "이미지 다운로드 (input.png)",
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

    st.download_button(
        "ZIP 한 번에 다운로드 (추천)",
        data=zip_bytes,
        file_name=f"{base}.zip",
        mime="application/zip",
    )

    st.divider()
    st.subheader("포토샵 처리 방법 (v3 동일)")
    st.markdown(
        """
**Photoshop에서 스크립트 실행 순서**
1) 포토샵 실행 → **파일 > 스크립트 > 찾아보기…** → `misharp_apply.jsx` 선택  
2) 창이 뜨면 순서대로 선택  
   - **템플릿 PSD 선택**  
   - **치환할 이미지 선택** (`*_input.png` 또는 zip에서 나온 `input.png`)  
   - **job.json 선택** (`*_job.json` 또는 zip에서 나온 `job.json`)  
3) 저장 폴더 선택 → `output.psd`, `output.jpg` 생성 완료
        """.strip()
    )

st.caption("※ ZIP을 받았다면 압축을 풀어 `input.png`, `job.json`만 사용하면 됩니다. (PSD는 포토샵에서 직접 선택)")
