import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import List, Tuple

import streamlit as st
from PIL import Image


# =========================
# Config
# =========================
APP_TITLE = "MISHARP 이미지 생성기 v3.2"
MAX_PER_PSD = 6
DEFAULT_GAP = 300
DEFAULT_TOP_BOTTOM = 300
DEFAULT_BG = (255, 255, 255)

Image.MAX_IMAGE_PIXELS = None


# =========================
# Helpers
# =========================
def _clean_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-.() ]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name or "file"


def _is_image_filename(name: str) -> bool:
    ext = os.path.splitext(name.lower())[1]
    return ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]


def _open_image_bytes(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img.convert("RGBA")


def _to_rgb_on_white(img_rgba: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    bg_img = Image.new("RGBA", img_rgba.size, bg + (255,))
    bg_img.alpha_composite(img_rgba)
    return bg_img.convert("RGB")


def _make_stacked_jpg(
    images: List[Tuple[str, bytes]],
    gap: int,
    top: int,
    bottom: int,
    bg_rgb=(255, 255, 255),
) -> bytes:
    pil_images: List[Image.Image] = []
    sizes: List[Tuple[int, int]] = []

    max_w = 0
    for name, data in images:
        if not _is_image_filename(name):
            continue
        img = _open_image_bytes(data)
        w, h = img.size
        max_w = max(max_w, w)
        pil_images.append(img)
        sizes.append((w, h))

    if not pil_images:
        raise ValueError("이미지 파일(JPG/PNG/WEBP/GIF 등)이 1개 이상 필요합니다.")

    total_h = top + bottom + sum(h for _, h in sizes) + gap * (len(sizes) - 1)
    canvas = Image.new("RGB", (max_w, total_h), bg_rgb)

    y = top
    for img, (w, h) in zip(pil_images, sizes):
        x = (max_w - w) // 2
        rgb = _to_rgb_on_white(img, bg_rgb)
        canvas.paste(rgb, (x, y))
        y += h + gap

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()


@dataclass
class JobImage:
    zip_filename: str
    layer_name: str
    y: int


def _build_jobs_split_6(
    images: List[Tuple[str, bytes]],
    gap: int,
    top: int,
    bottom: int,
) -> List[dict]:
    only_imgs = [(n, b) for (n, b) in images if _is_image_filename(n)]
    if not only_imgs:
        raise ValueError("이미지 파일(JPG/PNG/WEBP/GIF 등)이 1개 이상 필요합니다.")

    jobs = []
    for part_idx in range(0, len(only_imgs), MAX_PER_PSD):
        chunk = only_imgs[part_idx:part_idx + MAX_PER_PSD]

        sizes = []
        max_w = 0
        for n, b in chunk:
            img = _open_image_bytes(b)
            w, h = img.size
            sizes.append((w, h))
            max_w = max(max_w, w)

        total_h = top + bottom + sum(h for _, h in sizes) + gap * (len(sizes) - 1)

        imgs_meta: List[JobImage] = []
        y = top
        for i, ((n, _), (w, h)) in enumerate(zip(chunk, sizes), start=1):
            global_idx = part_idx + i
            ext = os.path.splitext(n)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]:
                ext = ".jpg"
            filename = f"images/image_{global_idx:03d}{ext}"
            layer = f"IMAGE_{global_idx:03d}"
            imgs_meta.append(JobImage(zip_filename=filename.replace("\\", "/"), layer_name=layer, y=y))
            y += h + gap

        job = {
            "version": "misharp_detailpage_job_v3",
            "layout": {
                "width": int(max_w),
                "total_height": int(total_h),
                "top_margin": int(top),
                "bottom_margin": int(bottom),
                "gap": int(gap),
                "background": {"r": 255, "g": 255, "b": 255},
                "center_align": True,
                "scale_to_width": False,
            },
            "images": [
                {"zip_filename": im.zip_filename, "layer_name": im.layer_name, "y": im.y}
                for im in imgs_meta
            ],
        }
        jobs.append(job)

    return jobs


def _make_master_jsx() -> str:
    return r'''#target photoshop
app.displayDialogs = DialogModes.NO;
app.bringToFront();

function parseJSON(txt){ return eval("(" + txt + ")"); }
function readTextFile(f){
  f.encoding="UTF8";
  if(!f.open("r")) throw new Error("파일 열기 실패: " + f.fsName);
  var s=f.read(); f.close(); return s;
}
function placeSmart(fileObj){
  var desc=new ActionDescriptor();
  desc.putPath(charIDToTypeID("null"), fileObj);
  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
  return app.activeDocument.activeLayer;
}
function boundsPx(layer){
  var b=layer.bounds;
  var L=b[0].as("px"), T=b[1].as("px"), R=b[2].as("px"), B=b[3].as("px");
  return {L:L, T:T, W:(R-L), H:(B-T)};
}
function moveTo(layer, x, y){
  var b=boundsPx(layer);
  layer.translate(x - b.L, y - b.T);
}
function runOneFolder(folder){
  var jobFile = new File(folder.fsName + "/job.json");
  if(!jobFile.exists) throw new Error("job.json 없음: " + jobFile.fsName);

  var job = parseJSON(readTextFile(jobFile));
  var width = job.layout.width;
  var totalH = job.layout.total_height;

  var doc = app.documents.add(width, totalH, 72, "MISHARP_DETAILPAGE", NewDocumentMode.RGB, DocumentFill.WHITE);

  var images = job.images;
  for(var i=0;i<images.length;i++){
    var it = images[i];
    var rel = (it.zip_filename || "").replace(/\\/g,"/");
    var imgFile = new File(folder.fsName + "/" + rel);
    if(!imgFile.exists){
      imgFile = new File(folder.fsName + "/images/" + rel);
    }
    if(!imgFile.exists) throw new Error("이미지 파일 못 찾음: " + imgFile.fsName);

    var layer = placeSmart(imgFile);
    layer.name = it.layer_name || ("IMAGE_" + (i+1));

    var b = boundsPx(layer);
    var x = Math.round((width - b.W) / 2);
    moveTo(layer, x, it.y || 0);
  }
}

try{
  var root = File($.fileName).parent;
  var parts = root.getFiles(function(f){
    return (f instanceof Folder) && /^part_\d+$/i.test(f.name);
  });

  if(!parts || parts.length === 0){
    var directJob = new File(root.fsName + "/job.json");
    if(directJob.exists){
      runOneFolder(root);
    } else {
      throw new Error("part_01 폴더도 없고, 루트 job.json도 없습니다.");
    }
  } else {
    parts.sort(function(a,b){
      var na=parseInt(a.name.replace(/\D+/g,""),10);
      var nb=parseInt(b.name.replace(/\D+/g,""),10);
      return na-nb;
    });

    for(var i=0;i<parts.length;i++){
      runOneFolder(parts[i]);
    }
  }

}catch(e){
  alert("MISHARP 스크립트 오류:\n" + e.toString());
}
'''


def _json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _zip_package(
    all_files: List[Tuple[str, bytes]],
    gap: int,
    top: int,
    bottom: int,
) -> bytes:
    jobs = _build_jobs_split_6(all_files, gap=gap, top=top, bottom=bottom)

    only_imgs = [(n, b) for (n, b) in all_files if _is_image_filename(n)]
    image_payloads = []
    for idx, (n, b) in enumerate(only_imgs, start=1):
        ext = os.path.splitext(n)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]:
            ext = ".jpg"
        image_payloads.append((idx, ext, b))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("misharp_detailpage.jsx", _make_master_jsx())
        z.writestr(
            "README.txt",
            "\n".join([
                "MISHARP 상세페이지 패키지",
                "",
                "1) ZIP 압축 해제",
                "2) Photoshop 실행",
                "3) 파일 > 스크립트 > 찾아보기... > misharp_detailpage.jsx 선택",
                "4) PSD가 part_01, part_02 ... 순서대로 자동 생성되어 열립니다 (Smart Object 유지).",
                "",
                f"- 기본 간격(gap): {gap}px",
                f"- 상/하단 여백: {top}px / {bottom}px",
                f"- PSD는 6장 단위로 자동 분할됩니다.",
                "",
                "ⓒ misharpcompany. All rights reserved.",
                "본 프로그램은 미샵컴퍼니 내부 직원 전용입니다.",
            ])
        )

        for pi, job in enumerate(jobs, start=1):
            part_name = f"part_{pi:02d}"
            z.writestr(f"{part_name}/job.json", _json_dumps(job).encode("utf-8"))

            needed = []
            for im in job["images"]:
                base = os.path.basename(im["zip_filename"])
                m = re.search(r"image_(\d+)\.", base, re.IGNORECASE)
                if m:
                    needed.append(int(m.group(1)))
            needed_set = set(needed)

            for idx, ext, data in image_payloads:
                if idx in needed_set:
                    z.writestr(f"{part_name}/images/image_{idx:03d}{ext}", data)

    return buf.getvalue()


# =========================
# Streamlit UI (items -> file_list 로 변경)
# =========================
def init_state():
    if "file_list" not in st.session_state:
        st.session_state.file_list = []
    if "msg" not in st.session_state:
        st.session_state.msg = ""


def add_files(files):
    if not files:
        return
    for f in files:
        name = _clean_filename(f.name)
        data = f.getvalue()
        st.session_state.file_list.append({"name": name, "data": data})


def move_item(idx: int, direction: int):
    items = st.session_state.file_list
    j = idx + direction
    if 0 <= idx < len(items) and 0 <= j < len(items):
        items[idx], items[j] = items[j], items[idx]


def remove_item(idx: int):
    items = st.session_state.file_list
    if 0 <= idx < len(items):
        items.pop(idx)


def clear_all():
    st.session_state.file_list = []


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem; padding-bottom: 2.2rem; max-width: 1080px; }
        h1 { font-size: 34px !important; font-weight: 650 !important; letter-spacing:-0.02em; }
        .subtle { color: rgba(255,255,255,0.70); font-size: 14px; line-height: 1.55; }
        .card { border: 1px solid rgba(255,255,255,0.10); border-radius: 16px; padding: 16px; background: rgba(255,255,255,0.03); }
        .tiny { font-size: 12px; color: rgba(255,255,255,0.65); line-height: 1.45; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("MISHARP 상세페이지 생성기")
    st.markdown(
        "<div class='subtle'>여러 장 이미지를 업로드 → <b>상세페이지 JPG</b>와 <b>PSD 패키지(6장 단위 자동 분할)</b>를 생성합니다.</div>",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        colA, colB = st.columns([1.1, 0.9], gap="large")

        with colA:
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
                if st.button(
                    "목록 전체 비우기",
                    use_container_width=True,
                    disabled=(len(st.session_state.file_list) == 0),
                ):
                    clear_all()

            st.markdown("#### 2) 여백 설정")
            gap = st.number_input("이미지 사이 간격(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)
            top = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_BOTTOM, step=10)
            bottom = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_BOTTOM, step=10)

            st.markdown(
                "<div class='tiny'>※ PSD는 6장 단위로 자동 분할되어 Photoshop 한계를 안정적으로 회피합니다.</div>",
                unsafe_allow_html=True,
            )

        with colB:
            st.markdown("#### 업로드된 목록 (순서 조정)")
            if len(st.session_state.file_list) == 0:
                st.info("아직 목록이 비어 있어요. 업로드 후 ‘업로드 목록에 추가’를 눌러주세요.")
            else:
                for idx, it in enumerate(st.session_state.file_list):
                    row = st.columns([0.18, 0.82], gap="small")
                    with row[0]:
                        up = st.button("↑", key=f"up_{idx}", disabled=(idx == 0))
                        dn = st.button("↓", key=f"dn_{idx}", disabled=(idx == len(st.session_state.file_list) - 1))
                        rm = st.button("삭제", key=f"rm_{idx}")
                        if up:
                            move_item(idx, -1)
                            st.rerun()
                        if dn:
                            move_item(idx, +1)
                            st.rerun()
                        if rm:
                            remove_item(idx)
                            st.rerun()

                    with row[1]:
                        st.markdown(f"**{idx+1:02d}.** {it['name']}")
                        if _is_image_filename(it["name"]):
                            try:
                                img = _open_image_bytes(it["data"])
                                st.image(_to_rgb_on_white(img), use_container_width=True)
                            except Exception:
                                st.caption("미리보기 불가 (이미지 손상 또는 형식 문제)")
                        else:
                            st.caption("이미지 외 파일 — PSD/JPG 생성에는 포함되지 않습니다.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### 3) 생성")

    can_run = any(_is_image_filename(it["name"]) for it in st.session_state.file_list)

    colX, colY = st.columns([1, 1], gap="large")
    with colX:
        make_jpg = st.checkbox("상세페이지 JPG 생성", value=True)
    with colY:
        make_psd_package = st.checkbox("PSD 패키지 ZIP 생성 (Photoshop JSX 포함)", value=True)

    if st.button("생성하기", type="primary", use_container_width=True, disabled=(not can_run)):
        try:
            items = [(it["name"], it["data"]) for it in st.session_state.file_list]

            if make_jpg:
                jpg_bytes = _make_stacked_jpg(items, gap=int(gap), top=int(top), bottom=int(bottom), bg_rgb=DEFAULT_BG)
                st.download_button(
                    "📥 상세페이지 JPG 다운로드",
                    data=jpg_bytes,
                    file_name="misharp_detailpage.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )

            if make_psd_package:
                zip_bytes = _zip_package(items, gap=int(gap), top=int(top), bottom=int(bottom))
                st.download_button(
                    "📥 PSD 패키지 ZIP 다운로드 (JSX 포함)",
                    data=zip_bytes,
                    file_name="misharp_detailpage_package.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

            st.success("완료! 위 버튼으로 다운로드하세요.")

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
