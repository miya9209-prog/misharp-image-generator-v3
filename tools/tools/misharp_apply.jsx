#target photoshop
app.displayDialogs = DialogModes.NO;

/**
 * MISHARP PSD 자동 생성기 (v3 동일 UX)
 * - 실행 흐름:
 *   1) 템플릿 PSD 선택
 *   2) 작업 폴더 선택 (input.png, job.json)
 *   3) IMAGE_1 스마트오브젝트 교체 + 상품명 텍스트 치환
 *   4) output.psd / output.jpg 저장
 *
 * 요구 파일(작업폴더):
 *   - input.png
 *   - job.json  (예: {"product_name": "..."})
 *
 * PSD 템플릿 조건:
 *   - 스마트오브젝트 레이어 이름: IMAGE_1
 *   - 텍스트 레이어 이름: 상품명
 */

function readTextFile(f) {
  f.encoding = "UTF8";
  if (!f.open("r")) throw new Error("파일을 열 수 없음: " + f.fsName);
  var s = f.read();
  f.close();
  return s;
}

function findLayerByName(container, name) {
  // container: Document or LayerSet
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
  if (!lyr) return false;
  if (lyr.kind !== LayerKind.TEXT) return false;
  lyr.textItem.contents = newText;
  return true;
}

/**
 * 스마트 오브젝트(고급개체) 내용 교체: IMAGE_1 → input.png
 * - cover 방식(캔버스 채우기)로 중앙 정렬
 */
function replaceSmartObjectContentsByImage(doc, smartLayerName, imageFile) {
  var lyr = findLayerByName(doc, smartLayerName);
  if (!lyr) throw new Error("스마트 오브젝트 레이어를 찾을 수 없음: " + smartLayerName);

  doc.activeLayer = lyr;

  // 스마트오브젝트 내용 열기
  var idEdit = stringIDToTypeID("placedLayerEditContents");
  executeAction(idEdit, undefined, DialogModes.NO);

  // 활성 문서는 스마트오브젝트(PSB)
  var soDoc = app.activeDocument;

  // 기존 레이어 삭제(가능한 범위)
  for (var i = soDoc.layers.length - 1; i >= 0; i--) {
    try { soDoc.layers[i].remove(); } catch (e) {}
  }

  // 이미지 Place(임베드)
  var desc = new ActionDescriptor();
  desc.putPath(charIDToTypeID("null"), imageFile);
  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

  var placed = soDoc.activeLayer;

  // 캔버스에 맞춰 cover 스케일
  var soW = soDoc.width.as("px"), soH = soDoc.height.as("px");
  var b = placed.bounds; // [L,T,R,B]
  var w = (b[2].as("px") - b[0].as("px"));
  var h = (b[3].as("px") - b[1].as("px"));
  if (w <= 0 || h <= 0) throw new Error("배치된 이미지의 크기를 읽을 수 없습니다.");

  var scale = Math.max(soW / w, soH / h) * 100;
  placed.resize(scale, scale, AnchorPosition.MIDDLECENTER);

  // 중앙 이동
  b = placed.bounds;
  var left = b[0].as("px"), top = b[1].as("px"), right = b[2].as("px"), bottom = b[3].as("px");
  var curCX = (left + right) / 2;
  var curCY = (top + bottom) / 2;
  var targetCX = soW / 2;
  var targetCY = soH / 2;
  placed.translate(targetCX - curCX, targetCY - curCY);

  // 저장/닫기
  soDoc.save();
  soDoc.close(SaveOptions.SAVECHANGES);

  // 원문서 복귀
  app.activeDocument = doc;
}

function saveOutputs(doc, outFolder) {
  // PSD 저장
  var psdFile = new File(outFolder.fsName + "/output.psd");
  var psdOpt = new PhotoshopSaveOptions();
  psdOpt.layers = true;
  doc.saveAs(psdFile, psdOpt, true, Extension.LOWERCASE);

  // JPG 저장(원본 해상도 유지)
  var jpgFile = new File(outFolder.fsName + "/output.jpg");
  var jpgOpt = new JPEGSaveOptions();
  jpgOpt.quality = 10;
  doc.saveAs(jpgFile, jpgOpt, true, Extension.LOWERCASE);
}

// ======================= 실행 =======================

try {
  // (1) 템플릿 PSD 선택 (v3 동일 UX)
  var psdFile = File.openDialog("템플릿 PSD 파일을 선택하세요", "PSD:*.psd");
  if (!psdFile) {
    alert("PSD 선택이 취소되었습니다.");
    throw new Error("Canceled PSD selection");
  }

  // (2) 작업 폴더 선택 (input.png, job.json)
  var jobFolder = Folder.selectDialog("작업 폴더를 선택하세요 (input.png / job.json)");
  if (!jobFolder) {
    alert("작업 폴더 선택이 취소되었습니다.");
    throw new Error("Canceled folder selection");
  }

  var inputImg = new File(jobFolder.fsName + "/input.png");
  var jobJson = new File(jobFolder.fsName + "/job.json");

  if (!inputImg.exists) {
    alert("작업 폴더에 input.png가 없습니다.\n폴더: " + jobFolder.fsName);
    throw new Error("Missing input.png");
  }
  if (!jobJson.exists) {
    alert("작업 폴더에 job.json이 없습니다.\n폴더: " + jobFolder.fsName);
    throw new Error("Missing job.json");
  }

  var job = JSON.parse(readTextFile(jobJson));
  var productName = job["product_name"] || "";

  // (3) PSD 열기
  var doc = app.open(psdFile);

  // (4) 텍스트 치환
  var okText = replaceTextLayer(doc, "상품명", productName);
  if (!okText) {
    // 텍스트 레이어가 없더라도 작업은 계속 진행할 수 있게 경고만
    alert("경고: '상품명' 텍스트 레이어를 찾지 못했거나 텍스트 레이어가 아닙니다.\n계속 진행합니다.");
  }

  // (5) 스마트오브젝트 치환
  replaceSmartObjectContentsByImage(doc, "IMAGE_1", inputImg);

  // (6) 저장
  saveOutputs(doc, jobFolder);

  // (7) 닫기(원본 PSD는 변경 저장하지 않음)
  doc.close(SaveOptions.DONOTSAVECHANGES);

  alert("완료!\n" +
        "폴더에 output.psd / output.jpg가 생성되었습니다.\n\n" +
        "폴더: " + jobFolder.fsName);

} catch (e) {
  alert("오류 발생:\n" + e.toString());
  try { if (app.documents.length > 0) app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
}
