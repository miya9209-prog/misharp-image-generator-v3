import io
import os
import re
import json
import math
import shutil
import zipfile
import tempfile
from datetime import datetime
from typing import List, Tuple

import streamlit as st
from PIL import Image

# =========================
# Utilities
# =========================
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def sanitize_name(name: str) -> str:
    name = re.sub(r"[^\w\-.가-힣 ]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:120] if name else "misharp_detailpage"


def natural_key(s: str):
    # natural sort: image_2 < image_10
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_images_recursive(root_dir: str) -> List[str]:
    """Find images recursively. Fixes ZIP structures like images/images/..."""
    out = []
    for base, dirs, files in os.walk(root_dir):
        # skip junk
        dirs[:] = [d for d in dirs if d not in ("__MACOSX", ".git", ".svn")]
        for fn in files:
            if fn.lower().endswith(IMG_EXTS) and not fn.startswith("._"):
                out.append(os.path.join(base, fn))
    out.sort(key=lambda p: natural_key(os.path.basename(p)))
    return out


def load_images_from_uploads(files) -> List[Tuple[str, Image.Image]]:
    imgs = []
    for uf in files:
        try:
            im = Image.open(uf).convert("RGB")
            imgs.append((uf.name, im))
        except Exception as e:
            st.warning(f"이미지 로드 실패: {uf.name} ({e})")
    return imgs


def extract_zip_to_temp(zip_file) -> Tuple[str, List[str]]:
    tmp = tempfile.mkdtemp(prefix="misharp_zip_")
    zpath = os.path.join(tmp, "upload.zip")
    with open(zpath, "wb") as f:
        f.write(zip_file.getbuffer())
    try:
        with zipfile.ZipFile(zpath, "r") as z:
            z.extractall(tmp)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"ZIP 해제 실패: {e}") from e

    img_paths = list_images_recursive(tmp)
    return tmp, img_paths


def pil_resize_to_width_keep_ratio(im: Image.Image, target_w: int) -> Image.Image:
    w, h = im.size
    if w == target_w:
        return im
    scale = target_w / float(w)
    new_h = max(1, int(round(h * scale)))
    return im.resize((target_w, new_h), Image.Resampling.LANCZOS)


def compose_vertical_jpg(
    images: List[Tuple[str, Image.Image]],
    target_w: int,
    top_margin: int,
    bottom_margin: int,
    gap: int,
    bg_color=(255, 255, 255),
    add_footer: bool = False,
    footer_text: str = "",
    footer_font_size_px: int = 22,
    footer_margin_top: int = 24,
):
    """
    IMPORTANT: '이미지 변형/잘라내기 금지' 조건에 부합:
    - 비율 유지 리사이즈(가로만 900 맞춤)
    - 크롭 없음
    - 보정 없음
    """
    resized = []
    for name, im in images:
        rim = pil_resize_to_width_keep_ratio(im, target_w)
        resized.append((name, rim))

    total_h = top_margin + bottom_margin
    if resized:
        total_h += sum(im.size[1] for _, im in resized)
        total_h += gap * (len(resized) - 1)

    footer_h = 0
    if add_footer and footer_text.strip():
        # 간단 계산(대략): 실제 폰트 렌더링은 PSD에서 더 정확
        # JPG에는 footer를 "영역만 확보"하고, 텍스트는 PSD에서 편집 가능하게 두는 걸 추천.
        footer_h = footer_margin_top + int(footer_font_size_px * 2.2)
        total_h += footer_h

    canvas = Image.new("RGB", (target_w, total_h), color=bg_color)

    y = top_margin
    for _, im in resized:
        canvas.paste(im, (0, y))
        y += im.size[1] + gap

    # JPG에 footer를 굳이 "이미지로" 넣는 건 편집성이 떨어져서,
    # 기본은 PSD에서 텍스트 레이어로 추가하도록 설계.
    # (원하면 여기서 PIL ImageDraw로 텍스트 찍는 버전도 추가 가능)

    return canvas, resized, total_h, footer_h


def make_psd_package(
    package_base_name: str,
    ordered_img_paths: List[str],
    target_w: int,
    top_margin: int,
    bottom_margin: int,
    gap: int,
    add_footer: bool,
    footer_text: str,
    footer_font: str,
    footer_font_size: int,
    footer_color_rgb: Tuple[int, int, int],
    footer_align: str,
    footer_margin_top: int,
) -> bytes:
    """
    Create a ZIP package:
    - /images/*.jpg (normalized)
    - manifest.json
    - build_psd_smartobject.jsx
    """
    tmpdir = tempfile.mkdtemp(prefix="misharp_psd_pkg_")
    try:
        images_dir = os.path.join(tmpdir, "images")
        os.makedirs(images_dir, exist_ok=True)

        # copy images into images_dir with stable names (keep original filename)
        normalized = []
        for p in ordered_img_paths:
            fn = os.path.basename(p)
            fn2 = sanitize_name(fn)
            dst = os.path.join(images_dir, fn2)
            shutil.copy2(p, dst)
            normalized.append(dst)

        manifest = {
            "meta": {
                "app": "MISHARP Detailpage Generator v3 (PSD SmartObject Package)",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "layout": {
                "canvas_width_px": int(target_w),
                "top_margin_px": int(top_margin),
                "bottom_margin_px": int(bottom_margin),
                "gap_px": int(gap),
            },
            "footer": {
                "enabled": bool(add_footer and footer_text.strip()),
                "text": footer_text.strip(),
                "font": footer_font.strip(),
                "font_size_pt": int(footer_font_size),
                "color_rgb": [int(footer_color_rgb[0]), int(footer_color_rgb[1]), int(footer_color_rgb[2])],
                "align": footer_align,  # "center" | "left" | "right"
                "margin_top_px": int(footer_margin_top),
            },
            "images": [os.path.join("images", os.path.basename(p)) for p in normalized],
            "output": {
                "psd_name": f"{package_base_name}.psd",
            },
        }

        with open(os.path.join(tmpdir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # write jsx
        jsx_path = os.path.join(tmpdir, "build_psd_smartobject.jsx")
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(PHOTOHOP_JSX_SCRIPT)

        # zip it
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(tmpdir):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, tmpdir)
                    z.write(full, rel)
        mem.seek(0)
        return mem.getvalue()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# =========================
# Photoshop JSX script (embedded)
# =========================
PHOTOHOP_JSX_SCRIPT = r"""#target photoshop
app.displayDialogs = DialogModes.NO;

function readTextFile(f) {
    f.encoding = "UTF8";
    f.open("r");
    var s = f.read();
    f.close();
    return s;
}

function ensureJSON() {
    if (typeof JSON === "undefined") {
        // Minimal JSON polyfill fallback (very small)
        // Most modern Photoshop ExtendScript already supports JSON.
        throw new Error("이 Photoshop 버전은 JSON.parse를 지원하지 않습니다. Photoshop을 최신 버전으로 업데이트해주세요.");
    }
}

function px(v){ return new UnitValue(v, "px"); }

function getImageSizePx(fileObj) {
    // Open to read size then close without saving
    var d = app.open(fileObj);
    var w = d.width.as("px");
    var h = d.height.as("px");
    d.close(SaveOptions.DONOTSAVECHANGES);
    return {w:w, h:h};
}

function placeAsSmartObject(fileObj) {
    // Place Embedded -> creates smart object layer
    var idPlc = charIDToTypeID("Plc ");
    var desc = new ActionDescriptor();
    desc.putPath(charIDToTypeID("null"), fileObj);
    desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa")); // align center
    var idOfst = charIDToTypeID("Ofst");
    var descOfst = new ActionDescriptor();
    descOfst.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0.0);
    descOfst.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0.0);
    desc.putObject(idOfst, idOfst, descOfst);
    executeAction(idPlc, desc, DialogModes.NO);
    return app.activeDocument.activeLayer;
}

function layerBoundsPx(lyr){
    var b = lyr.bounds; // [L,T,R,B]
    return {
        L: b[0].as("px"),
        T: b[1].as("px"),
        R: b[2].as("px"),
        B: b[3].as("px"),
        W: (b[2].as("px") - b[0].as("px")),
        H: (b[3].as("px") - b[1].as("px"))
    };
}

function moveLayerTo(lyr, x, y){
    // Moves layer so its top-left becomes (x,y) in canvas coordinates
    var b = layerBoundsPx(lyr);
    lyr.translate(x - b.L, y - b.T);
}

function resizeLayerToWidth(lyr, targetW){
    var b = layerBoundsPx(lyr);
    if (b.W <= 0.01) return;
    var pct = (targetW / b.W) * 100.0;
    lyr.resize(pct, pct, AnchorPosition.TOPLEFT);
}

function addFooterText(doc, footer, yTop){
    if (!footer.enabled) return 0;

    var textLayer = doc.artLayers.add();
    textLayer.kind = LayerKind.TEXT;
    textLayer.name = "copyright";
    var ti = textLayer.textItem;
    ti.contents = footer.text;

    // Font (best-effort). If missing, Photoshop will fallback.
    try { ti.font = footer.font; } catch(e) {}

    ti.size = footer.font_size_pt; // points
    ti.color.rgb.red = footer.color_rgb[0];
    ti.color.rgb.green = footer.color_rgb[1];
    ti.color.rgb.blue = footer.color_rgb[2];

    // Position: we set x based on align; y is baseline, so add some offset
    var x;
    if (footer.align === "left") x = 16;
    else if (footer.align === "right") x = doc.width.as("px") - 16;
    else x = doc.width.as("px") / 2;

    // baseline y (rough). We'll put baseline a bit below yTop + fontSize
    var baselineY = yTop + (footer.font_size_pt * 2.0);

    ti.position = [px(x), px(baselineY)];

    if (footer.align === "center") ti.justification = Justification.CENTER;
    else if (footer.align === "right") ti.justification = Justification.RIGHT;
    else ti.justification = Justification.LEFT;

    // Return an estimated footer height in px (safe)
    return Math.round(footer.font_size_pt * 2.2) + 8;
}

function main(){
    ensureJSON();

    // Choose manifest.json
    var mf = File.openDialog("manifest.json 선택 (PSD 생성용)", "JSON:*.json");
    if (!mf) return;

    var manifestText = readTextFile(mf);
    var manifest = JSON.parse(manifestText);

    var baseFolder = mf.parent; // package root
    var images = manifest.images;
    if (!images || images.length === 0) throw new Error("manifest에 images가 없습니다.");

    var canvasW = manifest.layout.canvas_width_px;
    var topMargin = manifest.layout.top_margin_px;
    var bottomMargin = manifest.layout.bottom_margin_px;
    var gap = manifest.layout.gap_px;

    var footer = manifest.footer || {enabled:false};

    // Prepass: compute scaled heights
    var sizes = [];
    var totalImagesH = 0;

    for (var i=0; i<images.length; i++){
        var rel = images[i];
        var f = File(baseFolder.fsName + "/" + rel);
        if (!f.exists) throw new Error("이미지 파일을 찾을 수 없습니다: " + f.fsName);

        var sz = getImageSizePx(f);
        var scale = canvasW / sz.w;
        var scaledH = Math.round(sz.h * scale);
        sizes.push({file:f, scaledH:scaledH});
        totalImagesH += scaledH;
    }

    var canvasH = topMargin + totalImagesH + gap*(images.length-1) + bottomMargin;
    if (footer.enabled) canvasH += footer.margin_top_px + Math.round(footer.font_size_pt * 2.2) + 12;

    // Create PSD doc
    var doc = app.documents.add(px(canvasW), px(canvasH), 72, manifest.output.psd_name, NewDocumentMode.RGB, DocumentFill.WHITE);
    doc.activeLayer.name = "background";

    // Place layers
    var y = topMargin;

    for (var j=0; j<sizes.length; j++){
        var f2 = sizes[j].file;
        placeAsSmartObject(f2); // active layer is placed smart object
        var lyr = doc.activeLayer;
        lyr.name = decodeURI(f2.name);

        // resize to width, keep ratio (no crop)
        resizeLayerToWidth(lyr, canvasW);
        // move to top-left at (0,y)
        moveLayerTo(lyr, 0, y);

        // next y
        var b = layerBoundsPx(lyr);
        y += Math.round(b.H) + gap;
    }

    // Footer (text layer) if enabled
    if (footer.enabled){
        y += footer.margin_top_px;
        addFooterText(doc, footer, y);
    }

    // Save PSD next to manifest
    var outPSD = File(baseFolder.fsName + "/" + manifest.output.psd_name);
    var psdSaveOptions = new PhotoshopSaveOptions();
    psdSaveOptions.embedColorProfile = true;
    psdSaveOptions.layers = true;
    doc.saveAs(outPSD, psdSaveOptions, true, Extension.LOWERCASE);

    alert("완료! PSD 생성됨:\n" + outPSD.fsName + "\n\n레이어는 모두 고급개체(스마트 오브젝트)로 살아있습니다.");
}

try {
    main();
} catch(e){
    alert("오류:\n" + e.toString());
}
"""


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="미샵 상세페이지 생성기 v3 (JPG + PSD 패키지)", layout="wide")
st.title("미샵 상세페이지 생성기 v3 (JPG + PSD 고급개체 PSD 패키지)")

st.markdown(
    """
- ✅ **가로 900px 고정**, 세로는 자동(이미지 수에 따라 증가)
- ✅ **자르기/변형/보정 금지** (비율 유지 리사이즈만)
- ✅ **이미지 사이 흰 여백**, 최상단/최하단 여백
- ✅ 업로드: **JPG 여러 장** 또는 **ZIP(자동 해제)**
- ✅ 출력:
  - **상세페이지 JPG 1장**
  - **PSD 패키지(zip)**: `manifest.json + images + build_psd_smartobject.jsx`  
    → PC Photoshop에서 JSX 실행하면 **고급개체 레이어 살아있는 PSD 생성**
"""
)

with st.sidebar:
    st.header("레이아웃 설정")
    target_w = st.number_input("캔버스 가로(px)", min_value=600, max_value=1400, value=900, step=10)
    top_margin = st.number_input("상단 여백(px)", min_value=0, max_value=400, value=80, step=5)
    gap = st.number_input("이미지 사이 여백(px)", min_value=0, max_value=250, value=70, step=5)
    bottom_margin = st.number_input("하단 여백(px)", min_value=0, max_value=400, value=120, step=5)

    st.divider()
    st.header("하단 카피라이트(PSD 텍스트 레이어)")
    add_footer = st.checkbox("PSD에 카피라이트 텍스트 레이어 추가", value=True)
    footer_text = st.text_input(
        "카피라이트 문구",
        value="© MISHARP. All rights reserved.  |  misharp.co.kr",
    )
    footer_font = st.text_input("폰트명(없으면 자동 대체)", value="MalgunGothic")
    footer_font_size = st.number_input("폰트 크기(pt)", min_value=8, max_value=64, value=18, step=1)
    footer_align = st.selectbox("정렬", ["center", "left", "right"], index=0)
    footer_margin_top = st.number_input("이미지 끝~카피라이트 위 여백(px)", min_value=0, max_value=200, value=40, step=5)

    st.divider()
    st.caption("※ JPG 결과물에는 카피라이트를 이미지로 찍지 않고(편집성 ↓), PSD에 텍스트 레이어로 넣습니다.")


tab1, tab2 = st.tabs(["JPG 다중 업로드", "ZIP 업로드"])

uploaded_images = []
base_name = "misharp_detailpage"

with tab1:
    files = st.file_uploader("JPG/PNG 여러 장 업로드", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
    if files:
        uploaded_images = load_images_from_uploads(files)
        if uploaded_images:
            base_name = sanitize_name(os.path.splitext(uploaded_images[0][0])[0])

with tab2:
    zf = st.file_uploader("ZIP 업로드 (압축 해제 후 이미지 자동 탐색)", type=["zip"])
    zip_tmp = None
    zip_paths = []
    if zf:
        try:
            zip_tmp, zip_paths = extract_zip_to_temp(zf)
            if zip_paths:
                # preview: load a few
                st.success(f"ZIP에서 이미지 {len(zip_paths)}개 발견 (폴더 구조 상관없이 재귀 탐색).")
                base_name = sanitize_name(os.path.splitext(os.path.basename(zip_paths[0]))[0])
            else:
                st.error("ZIP 안에서 이미지 파일을 찾지 못했습니다.")
        except Exception as e:
            st.error(str(e))


colA, colB = st.columns([1, 1])

with colA:
    st.subheader("미리보기 / 순서")
    if uploaded_images:
        st.write(f"업로드 이미지: {len(uploaded_images)}개")
        names = [n for n, _ in uploaded_images]
        st.code("\n".join(names[:80]) + ("\n..." if len(names) > 80 else ""))
        st.image([im for _, im in uploaded_images[:6]], caption=[n for n, _ in uploaded_images[:6]], width=240)
    elif zip_paths:
        st.write(f"ZIP 이미지: {len(zip_paths)}개")
        st.code("\n".join([os.path.basename(p) for p in zip_paths[:80]]) + ("\n..." if len(zip_paths) > 80 else ""))
    else:
        st.info("이미지를 업로드하면 미리보기와 출력 버튼이 활성화됩니다.")

with colB:
    st.subheader("출력")

    if (uploaded_images and len(uploaded_images) > 0) or (zip_paths and len(zip_paths) > 0):
        # Build JPG
        if st.button("✅ 상세페이지 JPG 생성", use_container_width=True):
            if uploaded_images:
                images = uploaded_images
            else:
                # load from zip paths
                images = []
                for p in zip_paths:
                    try:
                        im = Image.open(p).convert("RGB")
                        images.append((os.path.basename(p), im))
                    except Exception as e:
                        st.warning(f"이미지 로드 실패: {p} ({e})")
                # base_name from first file
                if images:
                    base_name = sanitize_name(os.path.splitext(images[0][0])[0])

            if not images:
                st.error("유효한 이미지가 없습니다.")
            else:
                canvas, resized, total_h, footer_h = compose_vertical_jpg(
                    images=images,
                    target_w=int(target_w),
                    top_margin=int(top_margin),
                    bottom_margin=int(bottom_margin),
                    gap=int(gap),
                    add_footer=False,  # footer is PSD text layer, not burned into JPG by default
                )
                out = io.BytesIO()
                canvas.save(out, format="JPEG", quality=95, optimize=True)
                out.seek(0)

                out_name = f"{base_name}_detail_{int(target_w)}w.jpg"
                st.success(f"완료! 최종 크기: {int(target_w)} x {total_h}px")
                st.download_button("⬇️ JPG 다운로드", data=out.getvalue(), file_name=out_name, mime="image/jpeg")

        # Build PSD Package
        st.divider()
        if st.button("✅ PSD 패키지(zip) 생성 (고급개체 PSD용)", use_container_width=True):
            if uploaded_images:
                # Save uploaded images into temp, then package
                tmp = tempfile.mkdtemp(prefix="misharp_imgs_")
                ordered_paths = []
                try:
                    for n, im in uploaded_images:
                        fn = sanitize_name(n)
                        p = os.path.join(tmp, fn)
                        im.convert("RGB").save(p, format="JPEG", quality=95)
                        ordered_paths.append(p)

                    pkg = make_psd_package(
                        package_base_name=base_name,
                        ordered_img_paths=ordered_paths,
                        target_w=int(target_w),
                        top_margin=int(top_margin),
                        bottom_margin=int(bottom_margin),
                        gap=int(gap),
                        add_footer=bool(add_footer),
                        footer_text=footer_text,
                        footer_font=footer_font,
                        footer_font_size=int(footer_font_size),
                        footer_color_rgb=(80, 80, 80),
                        footer_align=footer_align,
                        footer_margin_top=int(footer_margin_top),
                    )
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            else:
                # package directly from zip extracted files (already local)
                pkg = make_psd_package(
                    package_base_name=base_name,
                    ordered_img_paths=zip_paths,
                    target_w=int(target_w),
                    top_margin=int(top_margin),
                    bottom_margin=int(bottom_margin),
                    gap=int(gap),
                    add_footer=bool(add_footer),
                    footer_text=footer_text,
                    footer_font=footer_font,
                    footer_font_size=int(footer_font_size),
                    footer_color_rgb=(80, 80, 80),
                    footer_align=footer_align,
                    footer_margin_top=int(footer_margin_top),
                )

            pkg_name = f"{base_name}_PSD_PACKAGE.zip"
            st.success("PSD 패키지 생성 완료! 아래 ZIP을 PC로 받아서 Photoshop에서 JSX를 실행하세요.")
            st.download_button("⬇️ PSD 패키지(zip) 다운로드", data=pkg, file_name=pkg_name, mime="application/zip")

            st.markdown(
                """
### Photoshop에서 PSD 생성하는 방법 (딱 30초)
1) 방금 받은 ZIP을 **압축 해제**
2) Photoshop 실행
3) **파일 → 스크립트 → 찾아보기(Browse)**  
4) 압축 해제 폴더의 `build_psd_smartobject.jsx` 선택
5) 뜨는 창에서 `manifest.json` 선택  
→ 끝! 같은 폴더에 **고급개체 레이어 살아있는 PSD**가 생성됩니다.
"""
            )
    else:
        st.warning("이미지를 먼저 업로드하세요.")
