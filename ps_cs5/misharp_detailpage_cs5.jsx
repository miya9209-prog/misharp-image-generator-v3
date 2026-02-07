#target photoshop

(function () {

    // ===== SETTINGS =====
    var CANVAS_WIDTH = 900;
    var TOP_MARGIN = 80;
    var GAP = 70;
    var BOTTOM_MARGIN = 120;

    var FOOTER_TEXT = "© MISHARP. All rights reserved.  |  misharp.co.kr";
    var FOOTER_FONT = "MalgunGothic";
    var FOOTER_SIZE = 18;

    var JPG_QUALITY = 10;
    var SHOW_DONE_ALERT = false;

    // ===== helpers =====
    function px(v) { return new UnitValue(v, "px"); }

    function sortFiles(files) {
        files.sort(function (a, b) {
            return a.name.toLowerCase() > b.name.toLowerCase() ? 1 : -1;
        });
        return files;
    }

    function getImages(folder) {
        return sortFiles(folder.getFiles(function (f) {
            return f instanceof File && f.name.match(/\.(jpg|jpeg|png)$/i);
        }));
    }

    function openSize(file) {
        var d = app.open(file);
        var s = { w: d.width.as("px"), h: d.height.as("px") };
        d.close(SaveOptions.DONOTSAVECHANGES);
        return s;
    }

    function placeSO(file) {
        var oldDialogs = app.displayDialogs;
        app.displayDialogs = DialogModes.NO;

        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

        app.displayDialogs = oldDialogs;
        return app.activeDocument.activeLayer;
    }

    function layerWidth(layer) {
        var b = layer.bounds;
        return b[2].as("px") - b[0].as("px");
    }

    function resizeToWidth(layer, w) {
        var scale = (w / layerWidth(layer)) * 100;
        layer.resize(scale, scale, AnchorPosition.TOPLEFT);
    }

    function moveTo(layer, x, y) {
        var b = layer.bounds;
        layer.translate(x - b[0].as("px"), y - b[1].as("px"));
    }

    // ===== STATE SAVE (CS5 SAFE) =====
    var oldDialogs = app.displayDialogs;
    var oldUnits = app.preferences.rulerUnits;
    var oldActiveDoc = (app.documents.length > 0) ? app.activeDocument : null;

    app.displayDialogs = DialogModes.NO;
    app.preferences.rulerUnits = Units.PIXELS;

    try {
        var imgFolder = Folder.selectDialog("이미지 폴더 선택");
        if (!imgFolder) return;

        var imgs = getImages(imgFolder);
        if (imgs.length === 0) {
            alert("이미지가 없습니다.");
            return;
        }

        var outFolder = Folder.selectDialog("저장 폴더 선택");
        if (!outFolder) return;

        var name = prompt("파일명", imgs[0].name.replace(/\.[^\.]+$/, ""));
        if (!name) return;

        var heights = [];
        var totalH = 0;

        for (var i = 0; i < imgs.length; i++) {
            var s = openSize(imgs[i]);
            var h = Math.round(s.h * (CANVAS_WIDTH / s.w));
            heights.push(h);
            totalH += h;
        }

        var canvasH = TOP_MARGIN + totalH + GAP * (imgs.length - 1) + BOTTOM_MARGIN + 80;

        var doc = app.documents.add(
            px(CANVAS_WIDTH),
            px(canvasH),
            72,
            "misharp_detailpage",
            NewDocumentMode.RGB,
            DocumentFill.WHITE
        );

        var y = TOP_MARGIN;

        for (var j = 0; j < imgs.length; j++) {
            var l = placeSO(imgs[j]);
            resizeToWidth(l, CANVAS_WIDTH);
            moveTo(l, 0, y);
            y += heights[j] + GAP;
        }

        // footer
        var t = doc.artLayers.add();
        t.kind = LayerKind.TEXT;
        t.name = "copyright";
        t.textItem.contents = FOOTER_TEXT;
        t.textItem.size = FOOTER_SIZE;
        try { t.textItem.font = FOOTER_FONT; } catch (e) {}
        t.textItem.justification = Justification.CENTER;
        t.textItem.position = [px(CANVAS_WIDTH / 2), px(y + 40)];

        // save
        var psd = new File(outFolder + "/" + name + ".psd");
        var jpg = new File(outFolder + "/" + name + ".jpg");

        var psdOpt = new PhotoshopSaveOptions();
        psdOpt.layers = true;
        doc.saveAs(psd, psdOpt, true);

        var dup = doc.duplicate();
        dup.flatten();
        var jpgOpt = new JPEGSaveOptions();
        jpgOpt.quality = JPG_QUALITY;
        dup.saveAs(jpg, jpgOpt, true);
        dup.close(SaveOptions.DONOTSAVECHANGES);

        if (SHOW_DONE_ALERT) alert("완료");

    } catch (e) {
        alert("에러:\n" + e);
    } finally {
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = oldUnits;
        if (oldActiveDoc) app.activeDocument = oldActiveDoc;
    }

})();
fix: CS5 error 1302 (no activeDocument) + stable silent run
