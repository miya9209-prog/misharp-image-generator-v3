import io
import zipfile
import tempfile
from pathlib import Path
from typing import List, Tuple

import streamlit as st


st.set_page_config(
    page_title="MISHARP 상세페이지 생성기 v3 (CS5 PSD 패키지)",
    layout="wide",
)

APP_TITLE = "MISHARP 상세페이지 생성기 v3 (Photoshop CS5 PSD 패키지)"
CS5_JSX_REL_PATH = Path("ps_cs5") / "misharp_detailpage_cs5.jsx"


# -----------------------------
# Helpers
# -----------------------------
def _is_image_filename(name: str) -> bool:
    name_l = name.lower()
    return name_l.endswith(".jpg") or name_l.endswith(".jpeg") or name_l.endswith(".png")


def _safe_filename(name: str) -> str:
    # keep it simple; avoid path traversal
    return Path(name).name.replace("\\", "_").replace("/", "_")


def extract_images_from_zip(zip_bytes: bytes) -> List[Tuple[str, bytes]]:
    """
    Return list of (filename, data) for images inside the zip.
    - ignores non-images
    - flattens paths
    """
    out: List[Tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            fname = _safe_filename(info.filename)
            if not _is_image_filename(fname):
                continue
            data = zf.read(info.filename)
            if data:
                out.append((fname, data))
    # sort by filename for deterministic behavior
    out.sort(key=lambda x: x[0].lower())
    return out


def build_cs5_psd_package_zip(
    images: List[Tuple[str, bytes]],
    top: int,
    gap: int,
    bottom: int,
) -> bytes:
    """
    Creates a zip:
      - misharp_detailpage_cs5.jsx (patched margins)
      - images/ (uploaded)
      - README.txt

    Returns zip as bytes.
    """
    # locate jsx template in repo
    jsx_path = Path(__file__).parent / CS5_JSX_REL_PATH
    if not jsx_path.exists():
        raise FileNotFoundError(f"Missing JSX template: {jsx_path.as_posix()}")

    jsx_text = jsx_path.read_text(encoding="utf-8", errors="ignore")

    # Patch ONLY numeric lines (CS5 safe) - do not introduce JSON or modern syntax
    # These exact strings must exist in the JSX template.
    jsx_text = jsx_text.replace("var TOP_MARGIN = 80;", f"var TOP_MARGIN = {int(top)};")
    jsx_text = jsx_text.replace("var GAP = 70;", f"var GAP = {int(gap)};")
    jsx_text = jsx_text.replace("var BOTTOM_MARGIN = 120;", f"var BOTTOM_MARGIN = {int(bottom)};")

    readme = (
        "[MISHARP 상세페이지 생성기 사용법]\n\n"
        "1. ZIP을 풉니다.\n"
        "2. ZIP 안에 misharp_detailpage_cs5.jsx / images/ / README.txt 가 있습니다.\n"
        "3. Photoshop CS5 실행 → 파일 > 스크립트 > 찾아보기…\n"
        "4. misharp_detailpage_cs5.jsx 실행\n"
        "5. 이미지 폴더 선택 → ZIP 안의 images 폴더를 선택\n"
        "6. 저장 폴더 선택 → Smart Object 레이어가 살아있는 PSD + JPG가 생성됩니다.\n\n"
        "※ 본 생성기는 미샵 내부 직원 전용이며 외부 유출을 금합니다.\n"
    )

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pkg = td / "psd_package"
        img_dir = pkg / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        (pkg / "misharp_detailpage_cs5.jsx").write_text(jsx_text, encoding="utf-8")
        (pkg / "README.txt").write_text(readme, encoding="utf-8")

        for name, data in images:
            (img_dir / _safe_filename(name)).write_bytes(data)

        # write to bytes
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in pkg.rglob("*"):
                zf.write(f, arcname=str(f.relative_to(pkg)))
        buf.seek(0)
        return buf.read()


def ensure_session_state():
    if "images" not in st.session_state:
        st.session_state.images = []  # list[(name, bytes)]
    if "uploaded_notice" not in st.session_state:
        st.session_state.uploaded_notice = ""


def add_images(items: List[Tuple[str, bytes]]):
    # Avoid overwriting same names by auto-suffix
    existing = {name.lower(): 0 for name, _ in st.session_state.images}
    for name, data in items:
        base = Path(name).stem
        ext = Path(name).suffix
        new_name = name
        k = existing.get(new_name.lower(), 0)
        if k > 0:
            # if already exists, add suffix
            idx = k + 1
            new_name = f"{base}_{idx}{ext}"
        existing[new_name.lower()] = existing.get(new_name.lower(), 0) + 1
        st.session_state.images.append((new_name, data))


def move_item(idx: int, direction: int):
    # direction: -1 up, +1 down
    imgs = st.session_state.images
    j = idx + direction
    if j < 0 or j >= len(imgs):
        return
    imgs[idx], imgs[j] = imgs[j], imgs[idx]
    st.session_state.images = imgs


def remove_item(idx: int):
    imgs = st.session_state.images
    if 0 <= idx < len(imgs):
        imgs.pop(idx)
    st.session_state.images = imgs


# -----------------------------
# UI
# -----------------------------
ensure_session_state()

st.title(APP_TITLE)
st.caption("업로드한 이미지를 Photoshop CS5에서 실행 가능한 PSD 패키지 ZIP으로 만들어드립니다. (JSON 없음)")

colL, colR = st.columns([1.1, 1.0], gap="large")

with colL:
    st.subheader("1) 이미지 업로드")

    tab1, tab2 = st.tabs(["JPG/PNG 여러 장 업로드", "ZIP 업로드"])

    with tab1:
        up_files = st.file_uploader(
            "이미지 선택",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="uploader_images",
        )
        if up_files:
            items = [(f.name, f.getbuffer().tobytes()) for f in up_files]
            add_images(items)
            st.session_state.uploaded_notice = f"이미지 {len(items)}개 추가됨"

    with tab2:
        up_zip = st.file_uploader(
            "ZIP 선택 (안에 JPG/PNG 포함)",
            type=["zip"],
            accept_multiple_files=False,
            key="uploader_zip",
        )
        if up_zip:
            extracted = extract_images_from_zip(up_zip.getbuffer().tobytes())
            add_images(extracted)
            st.session_state.uploaded_notice = f"ZIP에서 이미지 {len(extracted)}개 추출되어 추가됨"

    if st.session_state.uploaded_notice:
        st.success(st.session_state.uploaded_notice)
        st.session_state.uploaded_notice = ""

    st.divider()
    st.subheader("2) 업로드 목록 / 순서 조정")

    if len(st.session_state.images) == 0:
        st.info("아직 이미지가 없습니다. 위에서 업로드하세요.")
    else:
        st.write(f"현재 이미지: **{len(st.session_state.images)}개**")

        # quick sort buttons
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("파일명 A→Z 정렬"):
                st.session_state.images.sort(key=lambda x: x[0].lower())
        with c2:
            if st.button("목록 전체 삭제"):
                st.session_state.images = []
        with c3:
            st.caption("※ Photoshop에서 보이는 순서 = 여기 목록 순서입니다.")

        st.divider()

        for i, (name, data) in enumerate(st.session_state.images):
            row = st.columns([0.12, 0.12, 0.12, 0.52, 0.12])
            with row[0]:
                st.button("▲", key=f"up_{i}", on_click=move_item, args=(i, -1), disabled=(i == 0))
            with row[1]:
                st.button("▼", key=f"dn_{i}", on_click=move_item, args=(i, +1), disabled=(i == len(st.session_state.images) - 1))
            with row[2]:
                st.button("🗑", key=f"rm_{i}", on_click=remove_item, args=(i,))
            with row[3]:
                st.write(name)
            with row[4]:
                st.write(f"{len(data)//1024} KB")

with colR:
    st.subheader("3) 레이아웃 설정 (CS5 패키지용)")
    top = st.slider("상단 여백 (px)", min_value=0, max_value=300, value=80, step=5)
    gap = st.slider("이미지 사이 여백 (px)", min_value=0, max_value=300, value=70, step=5)
    bottom = st.slider("하단 여백 (px)", min_value=0, max_value=400, value=120, step=5)

    st.divider()
    st.subheader("4) CS5 PSD 패키지 ZIP 다운로드")

    out_name = st.text_input("ZIP 파일명 (확장자 제외)", value="misharp_psd_package")

    can_build = len(st.session_state.images) > 0
    if not can_build:
        st.warning("먼저 이미지를 업로드하세요.")
    else:
        st.caption("ZIP 안에는 `misharp_detailpage_cs5.jsx` + `images/` + `README.txt`가 들어갑니다.")

    if st.button("ZIP 만들기"):
        if not can_build:
            st.error("이미지가 없습니다.")
        else:
            try:
                zip_bytes = build_cs5_psd_package_zip(
                    images=st.session_state.images,
                    top=top,
                    gap=gap,
                    bottom=bottom,
                )
                st.success("ZIP 생성 완료! 아래 버튼으로 다운로드하세요.")
                st.download_button(
                    label="⬇️ CS5 PSD 패키지 ZIP 다운로드",
                    data=zip_bytes,
                    file_name=f"{out_name}.zip",
                    mime="application/zip",
                )
            except Exception as e:
                st.error(f"ZIP 생성 실패: {e}")

    st.divider()
    st.subheader("직원 사용법 (요약)")
    st.code(
        "1) ZIP 풀기\n"
        "2) Photoshop CS5 → 파일 > 스크립트 > 찾아보기…\n"
        "3) misharp_detailpage_cs5.jsx 실행\n"
        "4) images 폴더 선택\n"
        "5) 저장 폴더 선택 → PSD + JPG 생성",
        language="text",
    )
