#target photoshop

(function () {

    // ===== SILENT / SPEED SETTINGS =====
    var SHOW_DONE_ALERT = false;        // 끝나고 팝업 끄기
    var DO_REFRESH = false;             // 중간 화면 갱신 최소화

    // ===== LAYOUT SETTINGS (v3에서 숫자 치환됨) =====
    var CANVAS_WIDTH = 900;      // px
    var TOP_MARGIN = 80;         // px
    var GAP = 70;                // px
    var BOTTOM_MARGIN = 120;     // px

    var FOOTER_ENABLED = true;
    var FOOTER_TEXT = "© MISHARP. All rights reserved.  |  misharp.co.kr";
    var FOOTER_FONT = "MalgunGothic";
    var FOOTER_SIZE = 18;
    var FOOTER_COLOR = [80, 80, 80];
    var FOOTER_MARGIN_TOP = 40;

    var JPG_QUALITY = 10;        // 1~12


    // ===== helpers =====
    function px(v) { return new UnitValue(v, "px"); }

    function baseName(fileName) {
        var dot = fileName.lastIndexOf(".");
        if (dot > 0) return fileName.substring(0, dot);
        return fileName;
    }

    function sortByName(files) {
        files.sort(function (a, b) {
            return a.name.toLowerCase() > b.name.toLowerCase() ? 1 : -1;
        });
        return files;
    }

    function getImageFiles(folder) {
        var files = folder.getFiles(function (f) {
            return (f instanceof File) && f.name.match(/\.(jpg|jpeg|png)$/i) && f.name.indexOf("._") !== 0;
        });
        return sortByName(files);
    }

    function openToGetSize(file) {
        var d = app.open(file);
        var w = d.width.as("px");
        var h = d.height.as("px");
        d.close(SaveOptions.DONOTSAVECHANGES);
        return { w: w, h: h };
    }

    function placeAsSmartObject(file) {
        // 강제로 "Place Embedded" 를 Dialog 없이 실행
        var oldDialogs = app.displayDialogs;
        app.displayDialogs = DialogModes.NO;

        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

        app.displayDialogs = oldDialogs;
        return app.activeDocument.activeLayer;
    }

    function getLayerW(layer) {
        var b = layer.bounds;
        return (b[2].as("px") - b[0].as("px"));
    }

    function resizeLayerToWidth(layer, targetW) {
        var w = getLayerW(layer);
        if (w <= 0.01) return;
        var scale = (targetW / w) * 100.0;
        layer.resize(scale, scale, AnchorPosition.TOPLEFT);
    }

    function moveLayerTo(layer, x, y) {
        var b = layer.bounds;
        var curX = b[0].as("px");
        var curY = b[1].as("px");
        layer.translate(x - curX, y - curY);
    }

    function addFooter(doc, yTop) {
        if (!FOOTER_ENABLED) return;

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
        ti.position = [px(CANVAS_WIDTH / 2), px(yTop + (FOOTER_SIZE * 2))];
    }

    function savePSD(doc, outFile) {
        var opts = new PhotoshopSaveOptions();
        opts.layers = true;
        opts.embedColorProfile = true;
        doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
    }

    function saveJPGFromPSD(doc, outFile) {
        var dup = doc.duplicate(doc.name + "_jpg", true);
        dup.flatten();

        var jpg = new JPEGSaveOptions();
        jpg.quality = JPG_QUALITY;
        jpg.embedColorProfile = true;

        dup.saveAs(outFile, jpg, true, Extension.LOWERCASE);
        dup.close(SaveOptions.DONOTSAVECHANGES);
    }


    // ===== main =====
    var originalRuler = app.preferences.rulerUnits;
    var oldDialogs = app.displayDialogs;
    var oldUnits = app.preferences.rulerUnits;
    var oldActiveDoc = app.activeDocument;

    // 가장 중요한 부분: "조용히 실행" + "화면 업데이트 최소화"
    app.displayDialogs = DialogModes.NO;
    app.preferences.rulerUnits = Units.PIXELS;

    try {
        var imgFolder = Folder.selectDialog("Select folder containing images (JPG/PNG)");
        if (!imgFolder) return;

        var images = getImageFiles(imgFolder);
        if (!images || images.length === 0) {
            alert("No images found in the selected folder.");
            return;
        }

        var outFolder = Folder.selectDialog("Select output folder to save PSD and JPG");
        if (!outFolder) return;

        var defaultName = baseName(images[0].name);
        var outName = prompt("Output file name (without extension)", defaultName);
        if (!outName || outName.replace(/\s/g, "") === "") outName = defaultName;

        // 1) canvas height 계산 (원본비율 유지)
        var scaledHeights = [];
        var totalImagesH = 0;

        for (var i = 0; i < images.length; i++) {
            var s = openToGetSize(images[i]);
            var hScaled = Math.round(s.h * (CANVAS_WIDTH / s.w));
            if (hScaled < 1) hScaled = 1;
            scaledHeights.push(hScaled);
            totalImagesH += hScaled;
        }

        var footerH = FOOTER_ENABLED ? (FOOTER_MARGIN_TOP + Math.round(FOOTER_SIZE * 2.2) + 12) : 0;
        var canvasH = TOP_MARGIN + totalImagesH + (GAP * (images.length - 1)) + BOTTOM_MARGIN + footerH;

        // 2) 새 PSD 만들기
        var doc = app.documents.add(
            px(CANVAS_WIDTH),
            px(canvasH),
            72,
            "misharp_detailpage",
            NewDocumentMode.RGB,
            DocumentFill.WHITE
        );

        // 화면 업데이트 최소화: background layer 잠금 유지, history도 최소화
        var y = TOP_MARGIN;

        for (var j = 0; j < images.length; j++) {
            var layer = placeAsSmartObject(images[j]);
            layer.name = images[j].name;

            // refresh 제거(움직임/깜빡임 줄이기)
            resizeLayerToWidth(layer, CANVAS_WIDTH);
            moveLayerTo(layer, 0, y);

            y += scaledHeights[j] + GAP;

            if (DO_REFRESH) app.refresh();
        }

        if (FOOTER_ENABLED) {
            y += (FOOTER_MARGIN_TOP - GAP);
            addFooter(doc, y);
        }

        // 3) 저장
        var psdFile = new File(outFolder.fsName + "/" + outName + ".psd");
        var jpgFile = new File(outFolder.fsName + "/" + outName + ".jpg");

        savePSD(doc, psdFile);
        saveJPGFromPSD(doc, jpgFile);

        if (SHOW_DONE_ALERT) {
            alert("Done.\nSaved:\n" + psdFile.fsName + "\n" + jpgFile.fsName);
        }

    } catch (err) {
        alert("Error:\n" + err);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = oldUnits;
        app.preferences.rulerUnits = originalRuler;
    }

})();
