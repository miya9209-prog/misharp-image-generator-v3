#target photoshop
app.displayDialogs = DialogModes.NO;

(function () {
    // =====================
    // 기본값(미샵 표준) - job.json이 있으면 덮어씀
    // =====================
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

    function readTextFile(f) {
        f.encoding = "UTF8";
        if (!f.open("r")) throw new Error("파일을 열 수 없습니다: " + f.fsName);
        var s = f.read();
        f.close();
        return s;
    }

    // ✅ 구버전 Photoshop 대응: JSON.parse가 없으면 eval로 파싱
    // (사내 생성기 job.json만 읽는 전제 / 외부 json 금지)
    function parseJSONCompat(text) {
        text = text.replace(/^\uFEFF/, ""); // BOM 제거
        if (typeof JSON !== "undefined" && JSON.parse) {
            return JSON.parse(text);
        }
        return eval("(" + text + ")");
    }

    function getImageFiles(folder) {
        var files = folder.getFiles(function (f) {
            return f instanceof File && f.name.match(/\.(jpg|jpeg|png)$/i) && f.name.indexOf("._") !== 0;
        });

        // 간단 정렬(파일명 기준)
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

    // =====================
    // 시작
    // =====================
    var baseFolder = File($.fileName).parent;

    // v3 패키지 구조: misharp_detailpage.jsx / job.json / images/
    var imgFolder = new Folder(baseFolder + "/images");
    if (!imgFolder.exists) {
        alert("images 폴더를 찾을 수 없습니다.\nJSX와 같은 폴더에 images 폴더가 있어야 합니다.\n\n경로: " + imgFolder.fsName);
        return;
    }

    // job.json 읽어서 설정 덮어쓰기 (있으면)
    var jobFile = new File(baseFolder + "/job.json");
    if (jobFile.exists) {
        try {
            var jobText = readTextFile(jobFile);
            var job = parseJSONCompat(jobText);

            if (job.canvas_width_px) CANVAS_WIDTH = job.canvas_width_px;
            if (job.top_margin_px != null) TOP_MARGIN = job.top_margin_px;
            if (job.gap_px != null) GAP = job.gap_px;
            if (job.bottom_margin_px != null) BOTTOM_MARGIN = job.bottom_margin_px;

            if (job.footer) {
                if (job.footer.enabled != null) FOOTER_ENABLED = !!job.footer.enabled;
                if (job.footer.text) FOOTER_TEXT = job.footer.text;
                if (job.footer.font) FOOTER_FONT = job.footer.font;
                if (job.footer.font_size_pt) FOOTER_SIZE = job.footer.font_size_pt;
                if (job.footer.color_rgb && job.footer.color_rgb.length === 3) FOOTER_COLOR = job.footer.color_rgb;
                if (job.footer.margin_top_px != null) FOOTER_MARGIN_TOP = job.footer.margin_top_px;
            }
        } catch (e) {
            alert("job.json 읽기 경고(무시하고 진행):\n" + e.toString());
        }
    }

    var images = getImageFiles(imgFolder);
    if (images.length === 0) {
        alert("images 폴더에 이미지가 없습니다.\n\n경로: " + imgFolder.fsName);
        return;
    }

    // 높이 계산(사전)
    var totalImagesH = 0;
    var scaledHeights = [];

    for (var i = 0; i < images.length; i++) {
        var s = getSize(images[i]);
        var scale = CANVAS_WIDTH / s.w;
        var h = Math.round(s.h * scale);
        scaledHeights.push(h);
        totalImagesH += h;
    }

    var footerH = FOOTER_ENABLED ? (FOOTER_MARGIN_TOP + Math.round(FOOTER_SIZE * 2.2) + 12) : 0;
    var canvasH = TOP_MARGIN + totalImagesH + GAP * (images.length - 1) + BOTTOM_MARGIN + footerH;

    // PSD 생성 (레이어 유지)
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

    alert("완료!\nSmart Object 레이어가 살아있는 PSD가 생성되었습니다.\n(job.json이 있으면 설정도 적용됨)");
})();
