#target photoshop
app.displayDialogs = DialogModes.NO;
app.bringToFront();

/*
MISHARP 상세페이지 PSD 생성기 (완전 자동)
- ZIP 압축 해제 폴더 안의 misharp_detailpage.jsx 실행하면
  같은 폴더의 job.json을 자동으로 읽고,
  images/ 폴더의 이미지들을 Smart Object로 배치합니다.
*/

function parseJSON(json) {
  // Photoshop ExtendScript 호환 JSON 파서
  return eval("(" + json + ")");
}

function readTextFile(f) {
  f.encoding = "UTF8";
  if (!f.open("r")) throw new Error("파일 열기 실패: " + f.fsName);
  var s = f.read();
  f.close();
  return s;
}

function placeFileAsSmartObject(fileObj) {
  var desc = new ActionDescriptor();
  desc.putPath(charIDToTypeID("null"), fileObj);
  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
  return app.activeDocument.activeLayer;
}

function layerBoundsPx(layer) {
  var b = layer.bounds;
  var L = b[0].as("px"), T = b[1].as("px"), R = b[2].as("px"), B = b[3].as("px");
  return { L: L, T: T, W: (R - L), H: (B - T) };
}

function scaleLayerToWidth(layer, targetW) {
  var b = layerBoundsPx(layer);
  if (b.W <= 0) throw new Error("레이어 폭을 읽을 수 없습니다.");
  var scale = (targetW / b.W) * 100.0;
  layer.resize(scale, scale, AnchorPosition.TOPLEFT);
}

function moveLayerTo(layer, x, y) {
  var b = layerBoundsPx(layer);
  layer.translate(x - b.L, y - b.T);
}

try {
  // ✅ 1) 이 JSX가 있는 폴더 = 작업 폴더
  var jobFolder = File($.fileName).parent;

  // ✅ 2) 팝업 없이 job.json 자동 찾기
  var jobFile = new File(jobFolder.fsName + "/job.json");
  if (!jobFile.exists) {
    throw new Error("job.json이 없습니다. ZIP을 푼 폴더에 job.json이 있어야 합니다.\n" + jobFile.fsName);
  }

  var job = parseJSON(readTextFile(jobFile));
  var width = job.layout.width;
  var totalHeight = job.layout.total_height;

  if (!width || !totalHeight) throw new Error("job.json의 layout.width 또는 layout.total_height가 없습니다.");

  // ✅ 3) 새 문서 생성
  var doc = app.documents.add(
    width,
    totalHeight,
    72,
    "MISHARP_DETAILPAGE",
    NewDocumentMode.RGB,
    DocumentFill.WHITE
  );

  var images = job.images;
  if (!images || images.length === 0) throw new Error("job.json에 images 배열이 없습니다.");

  // ✅ 4) images 배치
  for (var i = 0; i < images.length; i++) {
    var it = images[i];

    // zip_filename이 "images/image_001.jpg" 일 수도 있고 "image_001.jpg" 일 수도 있음.
    // -> 그대로 jobFolder 기준으로 합쳐서 찾는다 (중복 images 방지)
    var rel = it.zip_filename;
    rel = rel.replace(/\\/g, "/"); // 윈도우 역슬래시 대비

    var imgFile = new File(jobFolder.fsName + "/" + rel);

    // 혹시 zip_filename이 images/ 없이 들어오는 경우도 대응
    if (!imgFile.exists) {
      imgFile = new File(jobFolder.fsName + "/images/" + rel);
    }

    if (!imgFile.exists) {
      throw new Error("이미지 파일을 찾을 수 없습니다:\n" + imgFile.fsName);
    }

    var layer = placeFileAsSmartObject(imgFile);
    layer.name = it.layer_name || ("IMAGE_" + (i + 1));

    // width 맞춤 + y 배치
    scaleLayerToWidth(layer, width);
    moveLayerTo(layer, 0, it.y || 0);
  }

  // ✅ 저장/닫기/팝업 없음 → PSD가 그대로 열린 상태로 남음

} catch (e) {
  alert("스크립트 오류:\n" + e.toString());
}
