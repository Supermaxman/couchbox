// An hour-by-hour chart for the day details: a line (temperature, wind) with an optional dashed
// second line (feels like, gusts), or bars (chance of rain). Values are labelled every few
// hours; `mark` draws a line at one hour (the one picked on Today).
import QtQuick

Canvas {
    id: chart
    property var values: []
    property var values2: []                 // dashed (optional)
    property var labels: []                  // under the x axis
    property string kind: "line"             // line | bars
    property color color: W.warm
    property color color2: W.dim
    property real minValue: NaN               // NaN: from the data
    property real maxValue: NaN
    property string suffix: ""
    property int every: 3                    // label every n-th value
    property int mark: -1
    property real fontPx: 20 * W.u
    property string emptyText: ""            // said over the chart when every value is 0

    onValuesChanged: requestPaint()
    onValues2Changed: requestPaint()
    onMarkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        const n = values.length;
        if (!n) return;
        const top = fontPx * 1.7, bottom = fontPx * 1.8, left = fontPx * 0.6, right = fontPx * 0.6;
        const h = height - top - bottom, w = width - left - right;
        const all = values.concat(values2 || []).filter(v => v !== null && v !== undefined);
        let lo = isNaN(minValue) ? Math.min(...all) : minValue;
        let hi = isNaN(maxValue) ? Math.max(...all) : maxValue;
        if (isNaN(minValue)) lo -= (hi - lo) * 0.15 + 1;
        if (isNaN(maxValue)) hi += (hi - lo) * 0.1 + 1;
        const step = w / n;
        const X = i => left + step * (i + 0.5);
        const Y = v => top + h - (v - lo) / Math.max(1e-6, hi - lo) * h;

        // guide lines
        ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.07);
        ctx.lineWidth = 1;
        for (let g = 0; g <= 2; g++) {
            const y = top + h * g / 2;
            ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + w, y); ctx.stroke();
        }
        if (mark >= 0 && mark < n) {
            ctx.fillStyle = Qt.rgba(0.49, 0.83, 0.99, 0.12);
            ctx.fillRect(X(mark) - step / 2, top - fontPx * 1.4, step, h + fontPx * 1.4);
        }

        ctx.font = "600 " + Math.round(fontPx) + "px Inter, sans-serif";
        ctx.textAlign = "center";
        if (kind === "bars") {
            for (let i = 0; i < n; i++) {
                const v = values[i] || 0;
                const y = Y(v);
                ctx.fillStyle = Qt.rgba(color.r, color.g, color.b, 0.25 + 0.75 * Math.min(1, v / Math.max(1, hi)));
                ctx.fillRect(X(i) - step * 0.32, y, step * 0.64, top + h - y);
                if (i % every === 0 && v > 0) {
                    ctx.fillStyle = color;
                    ctx.fillText(Math.round(v) + suffix, X(i), y - fontPx * 0.45);
                }
            }
        } else {
            // the area under the line, then the line
            const grad = ctx.createLinearGradient(0, top, 0, top + h);
            grad.addColorStop(0, Qt.rgba(color.r, color.g, color.b, 0.28));
            grad.addColorStop(1, Qt.rgba(color.r, color.g, color.b, 0));
            ctx.beginPath();
            ctx.moveTo(X(0), top + h);
            for (let i = 0; i < n; i++) ctx.lineTo(X(i), Y(values[i]));
            ctx.lineTo(X(n - 1), top + h);
            ctx.closePath();
            ctx.fillStyle = grad;
            ctx.fill();
            if (values2 && values2.length === n) {
                ctx.strokeStyle = color2;
                ctx.lineWidth = 2.5 * W.u;
                ctx.setLineDash([6, 6]);
                ctx.beginPath();
                for (let i = 0; i < n; i++) i ? ctx.lineTo(X(i), Y(values2[i])) : ctx.moveTo(X(i), Y(values2[i]));
                ctx.stroke();
                ctx.setLineDash([]);
            }
            ctx.strokeStyle = color;
            ctx.lineWidth = 4 * W.u;
            ctx.lineJoin = "round";
            ctx.beginPath();
            for (let i = 0; i < n; i++) i ? ctx.lineTo(X(i), Y(values[i])) : ctx.moveTo(X(i), Y(values[i]));
            ctx.stroke();
            for (let i = 0; i < n; i += every) {
                ctx.fillStyle = color;
                ctx.beginPath(); ctx.arc(X(i), Y(values[i]), 5 * W.u, 0, Math.PI * 2); ctx.fill();
                ctx.fillStyle = "#fafafa";
                ctx.fillText(Math.round(values[i]) + suffix, X(i), Y(values[i]) - fontPx * 0.6);
            }
        }
        if (emptyText && values.every(v => !v)) {
            ctx.fillStyle = "#71717a";
            ctx.font = "500 " + Math.round(fontPx * 1.1) + "px Inter, sans-serif";
            ctx.fillText(emptyText, left + w / 2, top + h / 2);
        }
        ctx.fillStyle = "#a1a1aa";
        ctx.font = "500 " + Math.round(fontPx * 0.92) + "px Inter, sans-serif";
        for (let i = 0; i < labels.length; i += every)
            ctx.fillText(labels[i], X(i), height - fontPx * 0.35);
    }
}
