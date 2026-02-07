#target photoshop
app.displayDialogs = DialogModes.NO;

(function () {

    // ====== 미샵 기본값(고정) ======
    var CANVAS_WIDTH = 900;
    var TOP_MARGIN = 80;
    var GAP = 70;
    var BOTTOM_MARGIN = 120;

    var FOOTER_ENABLED = true;
    var FOOTER_TEXT = "© MISHARP. All rights reserved.  |  misharp.co.kr";
    var FOOTER_FONT = "MalgunGothic";
    var FOOTER_SIZE = 18;
    var FOOTER_COLOR = [80, 80, 80];
    var FOOTER_MARGIN_TOP = 40;

    function px(v) { return new UnitValue(v, "px"); }

    function getImageFiles(folder) {
        var files = folder.getFiles(function (f) {
            return (f instanceof File) && f.name.match(/\.(jpg|jpeg|png)$/i) && f.name.indexOf("._") !== 0;
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
        // Place Embedded => Smart Object 레이어
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
        return app.activeDocument.activeLayer;
    }

    function resizeToWidth(layer, targetW) {
        var b = layer.bounds;
        var w = b[2].as("px") - b[0].as("px");
        if (w <= 0.01) return;
        var scale = (targetW / w) * 100;
        layer.resize(scale, scale, AnchorPosition.TOPLEFT);
    }

    function moveLayer(layer, x, y) {
        var b = layer.bounds;
        layer.translate(x - b[0].as("px"), y - b[1].as("px"));
    }

    function addFooter(doc, y) {
        if (!FOOTER_ENABLED) return;

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
    }

    // ====== 여기서부터 “그때 방식” ======
    // JSX 실행하면 이미지 폴더만 선택 -> 바로 PSD 생성
    var imgFolder = Folder.selectDialog("images 폴더를 선택하세요 (JPG/PNG가 들어있는 폴더)");
    if (!imgFolder) return;

    var images = getImageFiles(imgFolder);
    if (images.length === 0) {
        alert("선택한 폴더에 이미지(JPG/PNG)가 없습니다.");
        return;
    }

    // 전체 높이 계산
    var totalImagesH = 0;
    var scaledHeights = [];
    for (var i = 0; i < images.length; i++) {
        var s = getSize(images[i]);
        var h = Math.round(s.h * (CANVAS_WIDTH / s.w));
        scaledHeights.push(h);
        totalImagesH += h;
    }

    var footerH = FOOTER_ENABLED ? (FOOTER_MARGIN_TOP + Math.round(FOOTER_SIZE * 2.2) + 12) : 0;
    var canvasH = TOP_MARGIN + totalImagesH + GAP * (images.length - 1) + BOTTOM_MARGIN + footerH;

    // PSD 생성
    var doc = app.documents.add(
        px(CANVAS_WIDTH),
        px(canvasH),
        72,
        "misharp_detailpage",
        NewDocumentMode.RGB,
        DocumentFill.WHITE
    );

    var y = TOP_MARGIN;

    // 이미지 배치(모두 Smart Object)
    for (var j = 0; j < images.length; j++) {
        placeSmartObject(images[j]);
        var layer = doc.activeLayer;
        layer.name = images[j].name;

        resizeToWidth(layer, CANVAS_WIDTH);
        moveLayer(layer, 0, y);

        y += scaledHeights[j] + GAP;
    }

    // 카피라이트
    if (FOOTER_ENABLED) {
        y += FOOTER_MARGIN_TOP;
        addFooter(doc, y);
    }

    alert("완료!\nSmart Object 레이어가 살아있는 PSD가 생성되었습니다.");

})();
