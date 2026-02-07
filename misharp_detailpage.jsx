#target photoshop
app.displayDialogs = DialogModes.NO;

(function () {

    // ===== MISHARP 고정 레이아웃 =====
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

    function getImages(folder) {
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

    function placeSO(file) {
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
        return app.activeDocument.activeLayer;
    }

    function resizeToWidth(layer) {
        var b = layer.bounds;
        var w = b[2].as("px") - b[0].as("px");
        var scale = (CANVAS_WIDTH / w) * 100;
        layer.resize(scale, scale, AnchorPosition.TOPLEFT);
    }

    function moveLayer(layer, x, y) {
        var b = layer.bounds;
        layer.translate(x - b[0].as("px"), y - b[1].as("px"));
    }

    // ===== 실행 =====
    var folder = Folder.selectDialog("상세페이지에 사용할 이미지 폴더를 선택하세요");
    if (!folder) return;

    var images = getImages(folder);
    if (images.length === 0) {
        alert("선택한 폴더에 이미지가 없습니다.");
        return;
    }

    var heights = [];
    var totalH = TOP_MARGIN + BOTTOM_MARGIN + FOOTER_MARGIN_TOP + FOOTER_SIZE * 2;

    for (var i = 0; i < images.length; i++) {
        var s = getSize(images[i]);
        var h = Math.round(s.h * (CANVAS_WIDTH / s.w));
        heights.push(h);
        totalH += h;
        if (i < images.length - 1) totalH += GAP;
    }

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
        placeSO(images[j]);
        var layer = doc.activeLayer;
        layer.name = images[j].name;

        resizeToWidth(layer);
        moveLayer(layer, 0, y);

        y += heights[j] + GAP;
    }

    // footer
    y += FOOTER_MARGIN_TOP;
    var t = doc.artLayers.add();
    t.kind = LayerKind.TEXT;
    t.name = "copyright";
    var ti = t.textItem;
    ti.contents = FOOTER_TEXT;
    ti.size = FOOTER_SIZE;
    try { ti.font = FOOTER_FONT; } catch (e) {}
    ti.color.rgb.red = FOOTER_COLOR[0];
    ti.color.rgb.green = FOOTER_COLOR[1];
    ti.color.rgb.blue = FOOTER_COLOR[2];
    ti.justification = Justification.CENTER;
    ti.position = [px(CANVAS_WIDTH / 2), px(y + FOOTER_SIZE * 2)];

    alert("완료! Smart Object PSD가 생성되었습니다.");

})();
