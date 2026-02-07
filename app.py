import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageOps


# =========================
# Config
# =========================
APP_TITLE = "MISHARP 이미지 생성기 v3.2"
MAX_PER_PSD = 6  # A안: 6장 단위 자동분할
DEFAULT_GAP = 300
DEFAULT_TOP_BOTTOM = 300
DEFAULT_BG = (255, 255, 255)

# 안전: PIL 폭/높이 제한(너무 큰 이미지 처리)
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
    # GIF의 경우 첫 프레임만 사용(상세페이지용)
    if getattr(img, "is_animated", False):
        img.seek(0)
    img = img.convert("RGBA")
    return img

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
) -> Tuple[bytes, int, int, List[Tuple[int, int]]]:
    """
    원본 해상도 유지:
    - 각 이미지 크기 그대로 사용
    - 캔버스 폭은 업로드 이미지들 중 '최대 폭'
    - 이미지들은 좌우 중앙 정렬
    """
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
    placements: List[Tuple[int, int]] = []
    for img, (w, h) in zip(pil_images, sizes):
        x = (max_w - w) // 2
        rgb = _to_rgb_on_white(img, bg_rgb)
        canvas.paste(rgb, (x, y))
        placements.append((x, y))
        y += h + gap

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue(), max_w, total_h, sizes

@dataclass
class JobImage:
    zip_filename: str   # e.g. "images/image_001.jpg"
    layer_name: str     # e.g. "IMAGE_001"
    y: int              # top y position in PSD

def _build_jobs_split_6(
    images: List[Tuple[str, bytes]],
    gap: int,
    top: int,
    bottom: int,
) -> List[dict]:
    """
    6장 단위로 job.json을 여러 개 만들기 (PSD 한계 피하기)
    - 원본 크기 유지
    - PSD 폭은 해당 묶음의 최대 폭
    - y는 top부터 누적
    """
    # 이미지 파일만 필터
    only_imgs = [(n, b) for (n, b) in images if _is_image_filename(n)]
    if not only_imgs:
        raise ValueError("이미지 파일(JPG/PNG/WEBP/GIF 등)이 1개 이상 필요합니다.")

    jobs = []
    for part_idx in range(0, len(only_imgs), MAX_PER_PSD):
        chunk = only_imgs[part_idx:part_idx + MAX_PER_PSD]

        # 각 이미지 크기 확인
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
                "scale_to_width": False,  # 원본 유지
            },
            "images": [
                {"zip_filename": im.zip_filename, "layer_name": im.layer_name, "y": im.y}
                for im in imgs_meta
            ],
        }
        jobs.append(job)

    return jobs

def _make_master_jsx() -> str:
    """
    ZIP 루트의 misharp_detailpage.jsx (한 번 실행 → part_* 폴더들 job.json을 자동으로 모두 처리)
    - 팝업 없음
    - JSON.parse 없이 eval 기반 파서
    - Place 후 '원본 크기 유지', 좌우 중앙 정렬, y로 배치
    - PSD는 저장하지 않고 "열린 상태"로 남김 (예전 흐름 복구)
    """
    return r'''#target photoshop
app.displayDialogs = DialogModes.NO;
app.bringToFront();

// MISHARP_MASTER_JSX_V3_2  (ZIP 루트의 이 jsx 하나만 실행하면 됩니다.)

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
      // 혹시 rel이 파일명만 들어온 경우
      imgFile = new File(folder.fsName + "/images/" + rel);
    }
    if(!imgFile.exists) throw new Error("이미지 파일 못 찾음: " + imgFile.fsName);

    var layer = placeSmart(imgFile);
    layer.name = it.layer_name || ("IMAGE_" + (i+1));

    // 원본 유지: resize 하지 않음
    // 좌우 중앙 정렬
    var b = boundsPx(layer);
    var x = Math.round((width - b.W) / 2);
    moveTo(layer, x, it.y || 0);
  }
}

try{
  // 이 JSX가 있는 폴더(=ZIP 루트)
  var root = File($.fileName).parent;

  // part_01, part_02 ... 폴더 자동 탐색
  var parts = root.getFiles(function(f){
    return (f instanceof Folder) && /^part_\d+$/i.test(f.name);
  });

  if(!parts || parts.length === 0){
    // 분할이 없는 경우: root에 job.json이 있을 수 있음
    var directJob = new File(root.fsName + "/job.json");
    if(directJob.exists){
      runOneFolder(root);
    } else {
      throw new Error("part_01 폴더도 없고, 루트 job.json도 없습니다.");
    }
  } else {
    // 정렬 (part_01, part_02 ...)
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

def _zip_package(
    all_files: List[Tuple[str, bytes]],
    gap: int,
    top: int,
    bottom: int,
) -> bytes:
    """
    ZIP 구성:
    - misharp_detailpage.jsx (루트: 한 번 실행)
    - part_01/job.json + images/*
    - part_02/...
    """
    jobs = _build_jobs_split_6(all_files, gap=gap, top=top, bottom=bottom)

    # 이미지들을 전체 인덱스 기준으로 저장하기 위해 다시 size 계산 없이 파일명 규칙대로 매핑
    # job 생성 시 image_001.. 를 전체 인덱스로 만들었으므로, 그 순서대로 파일을 넣는다.
    only_imgs = [(n, b) for (n, b) in all_files if _is_image_filename(n)]
    # 원본 확장자 유지해서 이미지 파일명 구성
    image_payloads = []
    for idx, (n, b) in enumerate(only_imgs, start=1):
        ext = os.path.splitext(n)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]:
            ext = ".jpg"
        image_payloads.append((idx, ext, b))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # master jsx
        z.writestr("misharp_detailpage.jsx", _make_master_jsx())

        # README
        z.writestr(
            "README.txt",
            "\n".join([
                "MISHARP 상세페이지 패키지",
                "",
                "1) ZIP 압축 해제",
                "2) Photoshop 실행",
                "3) 파일 > 스크립트 > 찾아보기... > misharp_detailpage.jsx 선택",
                "4) PSD가 part_01, part_02 ... 순서대로 자동으로 열립니다 (Smart Object 유지).",
                "",
                f"- 기본 간격(gap): {gap}px",
                f"- 상/하단 여백: {top}px / {bottom}px",
                f"- PSD는 6장 단위로 자동 분할됩니다.",
                "",
                "ⓒ misharpcompany. All rights reserved.",
                "본 프로그램은 미샵컴퍼니 내부 직원 전용입니다.",
            ])
        )

        # parts
        # 각 part 폴더에 job.json + images 포함
        # job.json에 들어있는 zip_filename은 images/image_###.ext (전역 인덱스)
        # part 폴더에는 해당 part에 필요한 이미지들만 넣는다.
        global_start = 1
        for pi, job in enumerate(jobs, start=1):
            part_name = f"part_{pi:02d}"
            z.writestr(f"{part_name}/job.json", _json_dumps(job).encode("utf-8"))

            # 이 part에서 필요한 이미지 번호 목록
            needed = []
            for im in job["images"]:
                # im["zip_filename"] = images/image_001.jpg
                base = os.path.basename(im["zip_filename"])
                m = re.search(r"image_(\d+)\.", base, re.IGNORECASE)
                if m:
                    needed.append(int(m.group(1)))

            needed_set = set(needed)
            for idx, ext, data in image_payloads:
                if idx in needed_set:
                    z.writestr(f"{part_name}/images/image_{idx:03d}{ext}", data)

    return buf.getvalue()

def _json_dumps(obj) -> str:
    # json 모듈 대신 최소 의존으로 (Streamlit cloud 환경 안전)
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


# =========================
# Streamlit UI
# =========================
def init_state():
    if "items" not in st.session_state:
        st.session_state.items = []  # list of dict: {name, data}
    if "msg" not in st.session_state:
        st.session_state.msg = ""

def add_files(files):
    if not files:
        return
    for f in files:
        name = _clean_filename(f.name)
        data = f.getvalue()
        st.session_state.items.append({"name": name, "data": data})

def move_item(idx: int, direction: int):
    items = st.session_state.items
    j = idx + direction
    if 0 <= idx < len(items) and 0 <= j < len(items):
        items[idx], items[j] = items[j], items[idx]

def remove_item(idx: int):
    items = st.session_state.items
    if 0 <= idx < len(items):
        items.pop(idx)

def clear_all():
    st.session_state.items = []

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    # --- Minimal feminine UI style ---
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem; padding-bottom: 2.2rem; max-width: 1080px; }
        h1, h2, h3 { letter-spacing: -0.02em; }
        h1 { font-size: 34px !important; font-weight: 650 !important; }
        .subtle { color: rgba(255,255,255,0.70); font-size: 14px; line-height: 1.55; }
        .card { border: 1px solid rgba(255,255,255,0.10); border-radius: 16px; padding: 16px; background: rgba(255,255,255,0.03); }
        .tiny { font-size: 12px; color: rgba(255,255,255,0.65); line-height: 1.45; }
        .btnrow button { height: 36px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("MISHARP 상세페이지 생성기")
    st.markdown(
        "<div class='subtle'>여러 장 이미지를 업로드 → <b>상세페이지 JPG</b>와 <b>Photoshop용 PSD 패키지(6장 단위 자동 분할)</b>를 생성합니다.</div>",
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
                type=None,  # 제한 최소화
                label_visibility="collapsed",
            )
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("업로드 목록에 추가", use_container_width=True):
                    add_files(uploaded)
            with c2:
                if st.button("목록 전체 비우기", use_container_width=True, disabled=(len(st.session_state.items) == 0)):
                    clear_all()
            with c3:
                st.write("")

            st.markdown("#### 2) 여백 설정")
            gap = st.number_input("이미지 사이 간격(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)
            top = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_BOTTOM, step=10)
            bottom = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_BOTTOM, step=10)

            st.markdown("<div class='tiny'>※ PSD는 6장 단위로 자동 분할되어 Photoshop 한계(‘결과가 너무 큼’)를 안정적으로 회피합니다.</div>", unsafe_allow_html=True)

        with colB:
            st.markdown("#### 업로드된 목록 (순서 조정)")
            if len(st.session_state.items) == 0:
                st.info("아직 목록이 비어 있어요. 파일을 업로드 후 ‘업로드 목록에 추가’를 눌러주세요.")
            else:
                # list view with reorder/delete + previews
                for idx, it in enumerate(st.session_state.items):
                    row = st.columns([0.16, 0.54, 0.30], gap="small")
                    with row[0]:
                        up = st.button("↑", key=f"up_{idx}", disabled=(idx == 0))
                        dn = st.button("↓", key=f"dn_{idx}", disabled=(idx == len(st.session_state.items) - 1))
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
                            st.caption("이미지 외 파일 (PSD/JPG/기타) — PSD 패키지 생성에는 포함되지 않습니다.")

                    with row[2]:
                        st.caption(f"파일 크기: {len(it['data'])/1024/1024:.1f} MB")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### 3) 생성")

    can_run = any(_is_image_filename(it["name"]) for it in st.session_state.items)

    colX, colY = st.columns([1, 1], gap="large")
    with colX:
        make_jpg = st.checkbox("상세페이지 JPG 생성", value=True)
    with colY:
        make_psd_package = st.checkbox("PSD 패키지 ZIP 생성 (Photoshop JSX 포함)", value=True)

    if st.button("생성하기", type="primary", use_container_width=True, disabled=(not can_run)):
        try:
            items = [(it["name"], it["data"]) for it in st.session_state.items]

            jpg_bytes = None
            zip_bytes = None

            if make_jpg:
                jpg_bytes, w, h, sizes = _make_stacked_jpg(items, gap=int(gap), top=int(top), bottom=int(bottom), bg_rgb=DEFAULT_BG)

            if make_psd_package:
                zip_bytes = _zip_package(items, gap=int(gap), top=int(top), bottom=int(bottom))

            st.success("완료! 아래에서 다운로드하세요.")

            if jpg_bytes:
                st.download_button(
                    "📥 상세페이지 JPG 다운로드",
                    data=jpg_bytes,
                    file_name="misharp_detailpage.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )

            if zip_bytes:
                st.download_button(
                    "📥 PSD 패키지 ZIP 다운로드 (JSX 포함)",
                    data=zip_bytes,
                    file_name="misharp_detailpage_package.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

                st.markdown(
                    "<div class='tiny'>Photoshop에서 <b>파일 &gt; 스크립트 &gt; 찾아보기...</b>로 ZIP을 풀어 나온 <b>misharp_detailpage.jsx</b>를 실행하면, part_01/part_02... PSD가 연달아 자동 생성되어 열립니다.</div>",
                    unsafe_allow_html=True,
                )

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
