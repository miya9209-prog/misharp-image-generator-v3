#target photoshop
app.displayDialogs = DialogModes.NO;

/*
 * MISHARP PSD 자동 생성기 (v3 최종 UX)
 *
 * 실행 흐름:
 * 1) 템플릿 PSD 선택
 * 2) 치환할 이미지 선택
 * 3) job.json 선택 (상품명)
 * 4) output.psd / output.jpg 생성
 *
 * 템플릿 PSD 조건:
 * - 스마트오브젝트 레이어명: IMAGE_1
 * - 텍스트 레이어명: 상품명
 */

function readTextFile(f) {
  f.encoding = "UTF8";
  if (!f.open("r")) throw new Error("파일 열기 실패: " + f.fsName);
  var s = f.read();
  f.close();
  return s;
}

function findLayerByName(container, name) {
  for (var i = 0; i < container.layers.length; i++) {
    var L = container.layers[i];
    if (L.name === name) return L;
    if (L.typename === "LayerSet") {
      var r = findLayerByName(L, name);
      if (r) return r;
    }
  }
  return null;
}

function replaceTextLayer(doc, layerName, newText) {
  var lyr = findLayerByName(doc, layerName);
  if (!lyr || lyr.kind !== LayerKind.TEXT) return false;
  lyr.textItem.contents = newText;
  return true;
}

function replaceSmartObjectByImage(doc, smartLayerName, imageFile) {
  var lyr = findLayerByName(doc, smartLayerName);
  if (!lyr) throw new Error("스마트오브젝트 레이어 없음: " + smartLayerName);

  doc.activeLayer = lyr;

  // 스마트오브젝트 내용 열기
  executeAction(stringIDToTypeID("placedLayerEditContents"), undefined, DialogModes.NO);

  var soDoc = app.activeDocument;

  // 기존 레이어 제거
  for (var i = soDoc.layers.length - 1; i >= 0; i--) {
    try { soDoc.layers[i].remove(); } catch (e) {}
  }

  // 이미지 Place
  var desc = new ActionDescriptor();
  desc.putPath(charIDToTypeID("null"), imageFile);
  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

  var placed = soDoc.activeLayer;

  // cover 맞춤
  var soW = soDoc.width.as("px"), soH = soDoc.height.as("px");
  var b = placed.bounds;
  var w = (b[2].as("px") - b[0].as("px"));
  var h = (b[3].as("px") - b[1].as("px"));
  var scale = Math.max(soW / w, soH / h) * 100;
  placed.resize(scale, scale, AnchorPosition.MIDDLECENTER);

  // 중앙 정렬
  b = placed.bounds;
  placed.translate(
    soW / 2 - (b[0].as("px") + b[2].as("px")) / 2,
    soH / 2 - (b[1].as("px") + b[3].as("px")) / 2
  );

  soDoc.save();
  soDoc.close(SaveOptions.SAVECHANGES);
  app.activeDocument = doc;
}

function saveOutputs(doc) {
  var baseFolder = Folder.selectDialog("결과 저장 폴더를 선택하세요");
  if (!baseFolder) throw new Error("저장 폴더 선택 취소");

  var psdFile = new File(baseFolder.fsName + "/output.psd");
  var jpgFile = new File(baseFolder.fsName + "/output.jpg");

  var psdOpt = new PhotoshopSaveOptions();
  psdOpt.layers = true;
  doc.saveAs(psdFile, psdOpt, true, Extension.LOWERCASE);

  var jpgOpt = new JPEGSaveOptions();
  jpgOpt.quality = 10;
  doc.saveAs(jpgFile, jpgOpt, true, Extension.LOWERCASE);
}

// ================= 실행 =================

try {
  // 1) PSD 선택
  var psdFile = File.openDialog("템플릿 PSD 선택", "*.psd");
  if (!psdFile) throw new Error("PSD 선택 취소");

  // 2) 이미지 선택
  var imageFile = File.openDialog("치환할 이미지 선택", "*.png;*.jpg;*.jpeg");
  if (!imageFile) throw new Error("이미지 선택 취소");

  // 3) job.json 선택 (상품명)
  var jobFile = File.openDialog("job.json 선택 (상품명)", "*.json");
  if (!jobFile) throw new Error("job.json 선택 취소");

  var job = JSON.parse(readTextFile(jobFile));
  var productName = job.product_name || "";

  // 4) PSD 열기
  var doc = app.open(psdFile);

  // 5) 적용
  replaceTextLayer(doc, "상품명", productName);
  replaceSmartObjectByImage(doc, "IMAGE_1", imageFile);

  // 6) 저장
  saveOutputs(doc);

  // 7) 닫기
  doc.close(SaveOptions.DONOTSAVECHANGES);

  alert("완료! PSD / JPG 생성되었습니다.");

} catch (e) {
  alert("오류 발생:\n" + e.toString());
  try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
}
