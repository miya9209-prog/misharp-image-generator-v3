#target photoshop
app.displayDialogs = DialogModes.NO;

function readTextFile(f) {
  f.encoding = "UTF8";
  f.open("r");
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

function replaceSmartObjectContentsByImage(doc, smartLayerName, imageFile) {
  var lyr = findLayerByName(doc, smartLayerName);
  if (!lyr) throw new Error("스마트 오브젝트 레이어를 찾을 수 없음: " + smartLayerName);

  doc.activeLayer = lyr;

  // placedLayerEditContents (스마트오브젝트 내용 열기)
  var idEdit = stringIDToTypeID("placedLayerEditContents");
  executeAction(idEdit, undefined, DialogModes.NO);

  // 이제 활성 문서는 스마트오브젝트(PSB)
  var soDoc = app.activeDocument;

  // 기존 레이어 삭제 (가능한 범위에서)
  for (var i = soDoc.layers.length - 1; i >= 0; i--) {
    try { soDoc.layers[i].remove(); } catch (e) {}
  }

  // 이미지 Place(임베드)
  var desc = new ActionDescriptor();
  desc.putPath(charIDToTypeID("null"), imageFile);
  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

  // 캔버스에 cover 맞춤(중앙 기준 확대/이동)
  var placed = soDoc.activeLayer;
  var soW = soDoc.width.as("px"), soH = soDoc.height.as("px");

  var b = placed.bounds; // [L,T,R,B]
  var w = (b[2].as("px") - b[0].as("px"));
  var h = (b[3].as("px") - b[1].as("px"));
  var scale = Math.max(soW / w, soH / h) * 100;
  placed.resize(scale, scale, AnchorPosition.MIDDLECENTER);

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

  // 원문서로 복귀
  app.activeDocument = doc;
}

function saveOutputs(doc, outFolder) {
  var psdFile = new File(outFolder.fsName + "/output.psd");
  var psdOpt = new PhotoshopSaveOptions();
  psdOpt.layers = true;
  doc.saveAs(psdFile, psdOpt, true, Extension.LOWERCASE);

  var jpgFile = new File(outFolder.fsName + "/output.jpg");
  var jpgOpt = new JPEGSaveOptions();
  jpgOpt.quality = 10;
  doc.saveAs(jpgFile, jpgOpt, true, Extension.LOWERCASE);
}

// ===== 실행 =====
var jobFolder = Folder.selectDialog("ZIP을 푼 폴더를 선택하세요 (template.psd / input.png / job.json)");
if (!jobFolder) { alert("취소됨"); throw new Error("Canceled"); }

var templatePsd = new File(jobFolder.fsName + "/template.psd");
var inputImg = new File(jobFolder.fsName + "/input.png");
var jobJson = new File(jobFolder.fsName + "/job.json");

if (!templatePsd.exists) { alert("template.psd 없음"); throw new Error("No template.psd"); }
if (!inputImg.exists) { alert("input.png 없음"); throw new Error("No input.png"); }
if (!jobJson.exists) { alert("job.json 없음"); throw new Error("No job.json"); }

var job = JSON.parse(readTextFile(jobJson));
var productName = job["product_name"] || "";

var doc = app.open(templatePsd);

// 텍스트
replaceTextLayer(doc, "상품명", productName);

// 스마트오브젝트
replaceSmartObjectContentsByImage(doc, "IMAGE_1", inputImg);

// 저장
saveOutputs(doc, jobFolder);

// 닫기(이미 saveAs로 출력했으므로 원본은 저장 안 함)
doc.close(SaveOptions.DONOTSAVECHANGES);

alert("완료! output.psd / output.jpg 생성되었습니다.");
