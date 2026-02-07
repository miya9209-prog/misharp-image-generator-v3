#target photoshop
app.displayDialogs = DialogModes.NO;
app.bringToFront();

function parseJSON(txt){ return eval("(" + txt + ")"); }

function readTextFile(f){
  f.encoding = "UTF8";
  if(!f.open("r")) throw new Error("파일 열기 실패: " + f.fsName);
  var s = f.read();
  f.close();
  return s;
}

function boundsPx(layer){
  var b = layer.bounds;
  var L = b[0].as("px"), T = b[1].as("px"), R = b[2].as("px"), B = b[3].as("px");
  return {L:L, T:T, W:(R-L), H:(B-T)};
}

function moveTo(layer, x, y){
  var b = boundsPx(layer);
  layer.translate(x - b.L, y - b.T);
}

// ✅ CS6 호환 Smart Object 변환
function convertToSmartObjectActiveLayer(){
  try{
    var idnewPlacedLayer = stringIDToTypeID("newPlacedLayer");
    executeAction(idnewPlacedLayer, undefined, DialogModes.NO);
  }catch(e){
    // 구버전 대비(대부분 CS6는 위가 됨)
    try{
      var id = stringIDToTypeID("convertToSmartObject");
      executeAction(id, undefined, DialogModes.NO);
    }catch(e2){
      // 실패해도 일단 진행
    }
  }
}

// ✅ Place 대신: 이미지 열기 → 전체복사 → 대상 문서에 붙여넣기 → 스마트오브젝트 변환
function pasteImageAsSmartObject(targetDoc, imgFile){
  var src = app.open(imgFile);
  app.activeDocument = src;

  // 배경만 있는 경우 activeLayer 그대로
  src.selection.selectAll();
  src.selection.copy();

  app.activeDocument = targetDoc;
  var pasted = targetDoc.paste();
  targetDoc.activeLayer = pasted;

  convertToSmartObjectActiveLayer();

  // 소스 닫기
  app.activeDocument = src;
  src.close(SaveOptions.DONOTSAVECHANGES);

  app.activeDocument = targetDoc;
  return targetDoc.activeLayer;
}

function runOneFolder(folder){
  var jobFile = new File(folder.fsName + "/job.json");
  if(!jobFile.exists) throw new Error("job.json 없음: " + jobFile.fsName);

  var job = parseJSON(readTextFile(jobFile));
  var width = job.layout.width;
  var totalH = job.layout.total_height;

  var doc = app.documents.add(width, totalH, 72, "MISHARP_DETAILPAGE", NewDocumentMode.RGB, DocumentFill.WHITE);

  var images = job.images;
  for(var i=0; i<images.length; i++){
    var it = images[i];
    var rel = (it.zip_filename || "").replace(/\\/g, "/");
    var imgFile = new File(folder.fsName + "/" + rel);
    if(!imgFile.exists){
      imgFile = new File(folder.fsName + "/images/" + rel);
    }
    if(!imgFile.exists) throw new Error("이미지 파일 못 찾음: " + imgFile.fsName);

    var layer = pasteImageAsSmartObject(doc, imgFile);
    layer.name = it.layer_name || ("IMAGE_" + (i+1));

    var b = boundsPx(layer);
    var x = Math.round((width - b.W) / 2);
    moveTo(layer, x, it.y || 0);
  }

  // ✅ PSD를 "열어둔 상태"로 두고 끝 (형준님이 바로 저장/수정 가능)
  // 자동저장을 원하면 여기서 doc.saveAs(...) 추가하면 됩니다.
}

try{
  // ✅ 스크립트 파일이 있는 폴더 = ZIP을 푼 루트여야 함
  var root = File($.fileName).parent;

  // part_01, part_02... 자동 탐색
  var parts = root.getFiles(function(f){
    return (f instanceof Folder) && /^part_\d+$/i.test(f.name);
  });

  if(parts && parts.length > 0){
    parts.sort(function(a,b){
      var na = parseInt(a.name.replace(/\D+/g,""), 10);
      var nb = parseInt(b.name.replace(/\D+/g,""), 10);
      return na - nb;
    });
    for(var i=0; i<parts.length; i++){
      runOneFolder(parts[i]);
    }
  }else{
    // 분할이 없는 경우(이미지 <= 6) 루트 job.json 지원
    var directJob = new File(root.fsName + "/job.json");
    if(directJob.exists){
      runOneFolder(root);
    }else{
      throw new Error("part_01 폴더도 없고 루트 job.json도 없습니다. ZIP을 '그대로' 푼 폴더에서 실행했는지 확인하세요.");
    }
  }

}catch(e){
  alert("MISHARP 스크립트 오류:\n" + e.toString());
}
