#target photoshop
app.displayDialogs = DialogModes.NO;

/*
MISHARP 상세페이지 생성기 (CS6 완전 호환)
- images 폴더 내 이미지를 자동 로드
- 가로 900px 고정 / 비율 유지
- 모든 이미지 Smart Object
- 이미지 사이 여백 / 상단·하단 여백
- 하단 카피라이트 텍스트 레이어
- JSON / job.json / 설정 파일 ❌
*/

(function () {

    // ===== 미샵 고정값 =====
    var CANVAS_WIDTH = 900;
    var TOP_MARGIN = 80;
    var GAP = 70;
    var BOTTOM_MARGIN = 120;

    var FOOTER_TEXT = "© MISHARP. All rights reserved.  |  misharp.co.kr";
    var FOOTER_FONT = "MalgunGothic";
    var FOOTER_SIZE = 18;
    var FOOTER_COLOR = [80, 80, 80];
    var FOOTER_MARGIN_TOP = 40;

    function px(v) { return new UnitValue(v, "px"); }

    function getImageFiles(folder) {
        var files = folder.getFiles(function (f) {
            return f instanceof File && f.name.match(/\.(jpg|jpeg|png)$/i);
        });
        files.sort(function (a, b) { return a.name > b.name ? 1 : -1; });
        return files;
    }

    function getSize(file) {
        var d = app.open(file);
        var w = d.width.as("px");
        var h = d.height.as("px");
        d.close(SaveOptions.DONOTSAVECHANGES);
        return { w: w, h: h };
    }

    function placeSmartObject(file) {
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
        return app.activeDocument.activeLayer;
    }

    function resizeToWidth(layer, targetW) {
        var b = layer.bounds;
        var w = b[2].as("px") - b[0].as("px");
        var scale = (targetW / w) * 100;
        layer.resize(scale, scale, AnchorPosition.TOPLEFT);
    }

    function moveLayer(layer, x, y) {
        var b = layer.bounds;
        layer.translate(x - b[0].as("px"), y - b[1].as("px"));
    }

    // ===== 시작 =====
    var baseFolder = File($.fileName).parent;
    var imgFolder = new Folder(baseFolder + "/images");

    if (!imgFolder.exists) {
        alert("images 폴더를 찾을 수 없습니다.\nJSX와 같은 위치에 images 폴더가 필요합니다.");
        return;
    }

    var images = getImageFiles(imgFolder);
    if (images.length === 0) {
        alert("images 폴더에 이미지가 없습니다.");
        return;
    }

    // 전체 높이 계산
    var totalH = TOP_MARGIN + BOTTOM_MARGIN + FOOTER_MARGIN_TOP + FOOTER_SIZE * 2.2;
    var heights = [];

    for (var i = 0; i < images.length; i++) {
        var s = getSize(images[i]);
        var h = Math.round(s.h * (CANVAS_WIDTH / s.w));
        heights.push(h);
        totalH += h;
        if (i < images.length - 1) totalH += GAP;
    }

    // PSD 생성
    var doc = app.documents.add(
        px(CANVAS_WIDTH),
        px(totalH),
        72,
        "misharp_detailpage",
        NewDocumentMode.RGB,
        DocumentFill.WHITE
    );

    var y = TOP_MARGIN;

    for (var j = 0; j < images.length; j++) {
        placeSmartObject(images[j]);
        var layer = doc.activeLayer;
        layer.name = images[j].name;

        resizeToWidth(layer, CANVAS_WIDTH);
        moveLayer(layer, 0, y);

        y += heights[j] + GAP;
    }

    // 카피라이트
    y += FOOTER_MARGIN_TOP;
    var textLayer = doc.artLayers.add();
    textLayer.kind = LayerKind.TEXT;
    textLayer.name = "copyright";

    var ti = textLayer.textItem;
    ti.contents = FOOTER_TEXT;
    ti.size = FOOTER_SIZE;
    try { ti.font = FOOTER_FONT; } catch (e) {}
    ti.color.rgb.red = FOOTER_COLOR[0];
    ti.color.rgb.green = FOOTER_COLOR[1];
    ti.color.rgb.blue = FOOTER_COLOR[2];
    ti.justification = Justification.CENTER;
    ti.position = [px(CANVAS_WIDTH / 2), px(y + FOOTER_SIZE * 2)];

    alert("완료!\nSmart Object PSD가 생성되었습니다.");

})();
