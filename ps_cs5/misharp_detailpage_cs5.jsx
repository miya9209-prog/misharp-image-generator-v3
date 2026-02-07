#target photoshop
app.displayDialogs = DialogModes.NO;

(function () {

    // SETTINGS
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

    var JPG_QUALITY = 10; // 1~12

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
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), file);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);
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

    // MAIN
    var originalRuler = app.preferences.rulerUnits;
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
        if (!outName || outName.replace(/\s/g, "") === "") {
            outName = defaultName;
        }

        // measure canvas height
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

        var doc = app.documents.add(
            px(CANVAS_WIDTH),
            px(canvasH),
            72,
            "misharp_detailpage",
            NewDocumentMode.RGB,
            DocumentFill.WHITE
        );

        // stack
        var y = TOP_MARGIN;

        for (var j = 0; j < images.length; j++) {
            var layer = placeAsSmartObject(images[j]);
            layer.name = images[j].name;

            app.refresh();
            resizeLayerToWidth(layer, CANVAS_WIDTH);
            app.refresh();
            moveLayerTo(layer, 0, y);
            app.refresh();

            y += scaledHeights[j] + GAP;
        }

        if (FOOTER_ENABLED) {
            y += (FOOTER_MARGIN_TOP - GAP);
            addFooter(doc, y);
        }

        var psdFile = new File(outFolder.fsName + "/" + outName + ".psd");
        var jpgFile = new File(outFolder.fsName + "/" + outName + ".jpg");

        savePSD(doc, psdFile);
        saveJPGFromPSD(doc, jpgFile);

        alert("Done.\nSaved:\n" + psdFile.fsName + "\n" + jpgFile.fsName);

    } catch (err) {
        alert("Error:\n" + err);
    } finally {
        app.preferences.rulerUnits = originalRuler;
    }

})();
