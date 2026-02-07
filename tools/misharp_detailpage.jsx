#target photoshop
app.displayDialogs = DialogModes.NO;

/*
MISHARP 상세페이지 PSD 생성기 (즉시 PSD 오픈)

- 사용법:
  1) Streamlit ZIP 다운로드 → 압축 해제
  2) Photoshop → 파일 > 스크립트 > 찾아보기… → (압축 해제 폴더의) misharp_detailpage.jsx 실행
  3) 바로 PSD가 생성되어 열립니다. (Smart Object 레이어 유지)

※ job.json, images/ 폴더는 jsx와 같은 폴더에 있어야 합니다.
*/

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
  var b = layer.bounds; // [L,T,R,B]
  var L = b[0].as("px");
  var T = b[1].as("px");
  var R = b[2].as("px");
  var B = b[3].as("px");
  return { L: L, T: T, R: R, B: B, W: (R - L), H: (B - T) };
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
  // ✅ 폴더 선택 없이: 이 jsx가 있는 폴더를 작업폴더로 사용
  var jobFolder = File($.fileName).parent;

  var jobFile = new File(jobFolder.fsName + "/job.json");
  if (!jobFile.exists) {
    throw new Error("job.json이 없습니다. jsx와 같은 폴더에 job.json이 있어야 합니다.\n" + jobFile.fsName);
  }

  var job = JSON.parse(readTextFile(jobFile));
  var width = job.layout.width;
  var totalHeight = job.layout.total_height;

  if (!width || !totalHeight) throw new Error("job.json의 layout.width 또는 layout.total_height가 없습니다.");

  // ✅ 새 문서 생성(흰 배경) — 만들자마자 PSD가 '열림'
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

  for (var i = 0; i < images.length; i++) {
    var it = images[i];
    var zipName = it.zip_filename;     // images/image_001.jpg
    var y = it.y;                      // 배치 y좌표
    var layerName = it.layer_name;     // IMAGE_001

    var imgFile = new File(jobFolder.fsName + "/" + zipName);
    if (!imgFile.exists) throw new Error("이미지 파일이 없습니다: " + imgFile.fsName);

    var layer = placeFileAsSmartObject(imgFile);
    layer.name = layerName;

    scaleLayerToWidth(layer, width);
    moveLayerTo(layer, 0, y);
  }

  // ✅ 여기서 저장/닫기/알림을 하지 않음
  // -> "예전처럼" PSD가 그대로 열린 상태로 남음(레이어/고급개체 살아있음)

} catch (e) {
  alert("오류:\n" + e.toString());
}
