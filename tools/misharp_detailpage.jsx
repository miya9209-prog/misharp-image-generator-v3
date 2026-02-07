#target photoshop
app.bringToFront();

// ------------------------------
// JSON.parse polyfill (필수)
// ------------------------------
function parseJSON(json) {
    return eval("(" + json + ")");
}

// ------------------------------
// File select
// ------------------------------
var jobFile = File.openDialog("job.json 파일을 선택하세요", "*.json");
if (!jobFile) {
    alert("job.json을 선택하지 않았습니다.");
    exit();
}

jobFile.open("r");
var jsonText = jobFile.read();
jobFile.close();

var job = parseJSON(jsonText);

// ------------------------------
// Create document
// ------------------------------
var doc = app.documents.add(
    job.layout.width,
    job.layout.total_height,
    72,
    "MISHARP_DETAILPAGE",
    NewDocumentMode.RGB,
    DocumentFill.WHITE
);

// ------------------------------
// Place images as Smart Objects
// ------------------------------
var baseFolder = jobFile.parent;
var imagesFolder = Folder(baseFolder + "/images");

for (var i = 0; i < job.images.length; i++) {
    var info = job.images[i];
    var imgFile = File(imagesFolder + "/" + info.zip_filename);

    if (!imgFile.exists) {
        alert("이미지 파일을 찾을 수 없습니다:\n" + imgFile.fsName);
        continue;
    }

    // Place
    var desc = new ActionDescriptor();
    desc.putPath(charIDToTypeID("null"), imgFile);
    desc.putEnumerated(
        charIDToTypeID("FTcs"),
        charIDToTypeID("QCSt"),
        charIDToTypeID("Qcsa")
    );
    executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

    var layer = doc.activeLayer;
    layer.name = info.layer_name;

    // Position
    var bounds = layer.bounds;
    var layerWidth = bounds[2].as("px") - bounds[0].as("px");
    var layerHeight = bounds[3].as("px") - bounds[1].as("px");

    var dx = -bounds[0].as("px");
    var dy = info.y - bounds[1].as("px");

    layer.translate(dx, dy);
}

// ------------------------------
// Done
// ------------------------------
alert("PSD 생성 완료!\n모든 이미지는 Smart Object로 배치되었습니다.");
