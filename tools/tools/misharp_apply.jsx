#target photoshop
app.displayDialogs = DialogModes.NO;

/*
MISHARP 상세페이지 PSD 생성기 (Smart Object 레이어 유지)

- 사용법:
  1) Streamlit에서 package.zip 다운로드 후 압축 해제
  2) Photoshop → 파일 > 스크립트 > 찾아보기… → misharp_detailpage.jsx 실행
  3) 압축 해제 폴더 선택 (job.json, images/ 폴더가 있어야 함)
  4) output.psd / output.jpg 생성
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
  return app.activeDocument.activeLayer; // placed smart object layer
}

function layerBoundsPx(layer) {
  var b = layer.bounds; // [L,T,R,B] in UnitValue
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
  var dx = x - b.L;
  var dy = y - b.T;
  layer.translate(dx, dy);
}

function savePSDAndJPG(doc, outFolder) {
  // PSD
  var psdFile = new File(outFolder.fsName + "/output.psd");
  var psdOpt = new PhotoshopSaveOptions();
  psdOpt.layers = true;
  doc.saveAs(psdFile, psdOpt, true, Extension.LOWERCASE);

  // JPG
  var jpgFile = new File(outFolder.fsName + "/output.jpg");
  var jpgOpt = new JPEGSaveOptions();
  jpgOpt.quality = 10;
  doc.saveAs(jpgFile, jpgOpt, true, Extension.LOWERCASE);
}

try {
  var jobFolder = Folder.selectDialog("ZIP을 푼 폴더를 선택하세요 (job.json, images/ 필요)");
  if (!jobFolder) throw new Error("폴더 선택 취소");

  var jobFile = new File(jobFolder.fsName + "/job.json");
  if (!jobFile.exists) throw new Error("job.json이 없습니다: " + jobFile.fsName);

  var job = JSON.parse(readTextFile(jobFile));

  var width = job.layout.width;
  var totalHeight = job.layout.total_height;
  if (!width || !totalHeight) throw new Error("job.json에 layout.width 또는 layout.total_height가 없습니다.");

  // 새 문서 생성 (배경 흰색)
  var doc = app.documents.add(
    width,
    totalHeight,
    72,
    "MISHARP_DETAILPAGE",
    NewDocumentMode.RGB,
    DocumentFill.WHITE
  );

  // 이미지들을 순서대로 배치
  var images = job.images;
  if (!images || images.length === 0) throw new Error("job.json에 images 배열이 없습니다.");

  for (var i = 0; i < images.length; i++) {
    var it = images[i];
    var zipName = it.zip_filename; // "images/image_001.jpg"
    var y = it.y;
    var layerName = it.layer_name; // "IMAGE_001"

    var imgFile = new File(jobFolder.fsName + "/" + zipName);
    if (!imgFile.exists) throw new Error("이미지 파일이 없습니다: " + imgFile.fsName);

    var layer = placeFileAsSmartObject(imgFile);
    layer.name = layerName;

    // 폭 맞추고, (0, y)에 붙이기
    scaleLayerToWidth(layer, width);
    moveLayerTo(layer, 0, y);
  }

  // 저장 위치: 선택(또는 jobFolder 그대로 쓰고 싶으면 이 줄을 jobFolder로 고정하면 됨)
  var outFolder = Folder.selectDialog("저장 폴더 선택 (output.psd / output.jpg)");
  if (!outFolder) outFolder = jobFolder;

  savePSDAndJPG(doc, outFolder);

  // 닫기(저장했으니)
  doc.close(SaveOptions.DONOTSAVECHANGES);

  alert("완료! output.psd / output.jpg 생성되었습니다.");

} catch (e) {
  alert("오류:\n" + e.toString());
  try { if (app.documents.length > 0) app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
}
