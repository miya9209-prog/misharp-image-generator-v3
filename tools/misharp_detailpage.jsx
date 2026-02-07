#target photoshop
app.displayDialogs = DialogModes.NO;
app.bringToFront();

// MISHARP_AUTO_V9  (이 문구가 ZIP안 JSX에 있으면 최신입니다)

function parseJSON(txt) { return eval("(" + txt + ")"); }
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
  // ✅ JSX가 있는 폴더 기준으로 job.json 자동 탐색
  var jobFolder = File($.fileName).parent;
  var jobFile = new File(jobFolder.fsName + "/job.json");
  if (!jobFile.exists) throw new Error("job.json 없음: " + jobFile.fsName);

  var job = parseJSON(readTextFile(jobFile));
  var width = job.layout.width;
  var totalHeight = job.layout.total_height;

  if (!width || !totalHeight) throw new Error("layout.width/total_height 누락");

  var doc = app.documents.add(
    width, totalHeight, 72,
    "MISHARP_DETAILPAGE",
    NewDocumentMode.RGB,
    DocumentFill.WHITE
  );

  var images = job.images;
  if (!images || images.length === 0) throw new Error("job.images 비어있음");

  for (var i = 0; i < images.length; i++) {
    var it = images[i];
    var rel = (it.zip_filename || "").replace(/\\/g, "/"); // 역슬래시 정리

    // ✅ zip_filename이 "images/image_001.jpg"면 그대로 씀 (images 중복 방지)
    var imgFile = new File(jobFolder.fsName + "/" + rel);

    // ✅ 혹시 zip_filename이 "image_001.jpg"처럼 들어오면 images/ 붙여서 2차 시도
    if (!imgFile.exists) imgFile = new File(jobFolder.fsName + "/images/" + rel);

    if (!imgFile.exists) throw new Error("이미지 파일 못 찾음: " + imgFile.fsName);

    var layer = placeFileAsSmartObject(imgFile);
    layer.name = it.layer_name || ("IMAGE_" + (i + 1));

    scaleLayerToWidth(layer, width);
    moveLayerTo(layer, 0, it.y || 0);
  }

  // ✅ 팝업/저장 없이 PSD는 열린 상태로 남음

} catch (e) {
  alert("스크립트 오류:\n" + e.toString());
}
