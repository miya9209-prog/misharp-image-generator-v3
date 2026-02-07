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
st.info("이 앱은 PSD를 만들지 않습니다. 포토샵 스크립트 실행 시 템플릿 PSD를 직접 선택합니다.")

# 입력
up = st.file_uploader("치환할 이미지 업로드", type=["png", "jpg", "jpeg", "webp"])
product_name = st.text_input("상품명", value="", placeholder="예) 뮤 반오픈 카라 스트라이프 니트")

st.divider()
col1, col2 = st.columns(2)
with col1:
    base_name = st.text_input("파일 베이스명", value="misharp_job", help="다운로드 파일명 앞부분")
with col2:
    keep_original_ext = st.checkbox("업로드한 이미지 확장자 유지(권장)", value=True)

def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "misharp_job"
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", "."))[:80]
    return s or "misharp_job"

def _detect_ext(filename: str) -> str:
    fn = (filename or "").lower()
    if fn.endswith(".png"):
        return "png"
    if fn.endswith(".webp"):
        return "webp"
    if fn.endswith(".jpg") or fn.endswith(".jpeg"):
        return "jpg"
    return "png"

def _normalize_image_bytes(upload_bytes: bytes, ext: str) -> bytes:
    """
    webp는 포토샵/환경에 따라 불편할 수 있어 PNG로 변환 옵션을 원하면 바꿀 수 있음.
    여기서는 '확장자 유지'가 체크돼도 내부는 원본 그대로 두고,
    ZIP에는 그대로 담는다.
    """
    return upload_bytes

def _load_jsx_bytes() -> bytes | None:
    path = os.path.join("tools", "misharp_apply.jsx")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None

gen = st.button("작업파일 생성", type="primary", disabled=(up is None))

if gen and up is not None:
    base = _safe_filename(base_name)

    ext = _detect_ext(up.name) if keep_original_ext else "png"
    img_bytes = _normalize_image_bytes(up.getvalue(), ext)

    # job.json
    job = {
        "product_name": (product_name or "").strip(),
        "image_layer": "IMAGE_1",
        "text_layer": "상품명",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    job_json = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")

    jsx_bytes = _load_jsx_bytes()

    # ZIP 만들기
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"image.{ext}", img_bytes)
        z.writestr("job.json", job_json)
        if jsx_bytes:
            z.writestr("misharp_apply.jsx", jsx_bytes)

    st.success("완료! 아래에서 개별 다운로드 또는 ZIP 다운로드를 선택하세요.")
    st.caption("포토샵 스크립트는 ‘PSD 선택 → 이미지 선택 → job.json 선택 → 저장 폴더 선택’ 순서로 실행됩니다.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            f"이미지 다운로드 (image.{ext})",
            data=img_bytes,
            file_name=f"{base}_image.{ext}",
            mime="application/octet-stream",
        )
    with c2:
        st.download_button(
            "job.json 다운로드",
            data=job_json,
            file_name=f"{base}_job.json",
            mime="application/json",
        )
    with c3:
        if jsx_bytes:
            st.download_button(
                "Photoshop 스크립트 다운로드 (jsx)",
                data=jsx_bytes,
                file_name="misharp_apply.jsx",
                mime="application/octet-stream",
            )
        else:
            st.write("jsx 파일 없음")

    st.download_button(
        "ZIP 한 번에 다운로드 (추천)",
        data=zbuf.getvalue(),
        file_name=f"{base}.zip",
        mime="application/zip",
    )

    st.divider()
    st.markdown(
        """
### 포토샵 실행 순서 (v3 동일)
1) 포토샵 → **파일 > 스크립트 > 찾아보기…** → `misharp_apply.jsx`
2) 순서대로 선택:
   - 템플릿 PSD
   - 치환 이미지 (`*_image.png/jpg/webp` 또는 zip 안의 `image.*`)
   - `job.json`
   - 저장 폴더
3) `output.psd`, `output.jpg` 생성
        """.strip()
    )
