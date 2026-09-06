/* 月曆。

刻意不引入 FullCalendar：這裡只需要「一個月 + 每天幾個數字」，
自行實作反而更小、更快，也不必依賴 CDN 是否可連線。
資料來自 GET /api/calendar?year=&month=，child_id 由後端從 session 決定。 */

(function () {
  "use strict";

  var WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

  function pad(value) {
    return value < 10 ? "0" + value : String(value);
  }

  function buildCell(className, content) {
    var cell = document.createElement("div");
    cell.className = className;
    if (content) {
      cell.textContent = content;
    }
    return cell;
  }

  function render(container, year, month, summaries, todayIso, dayUrlBase) {
    container.innerHTML = "";

    var byDate = {};
    summaries.forEach(function (item) {
      byDate[item.date] = item;
    });

    WEEKDAYS.forEach(function (label) {
      container.appendChild(buildCell("calendar-head", label));
    });

    var first = new Date(year, month - 1, 1);
    var daysInMonth = new Date(year, month, 0).getDate();
    var leading = first.getDay();

    for (var i = 0; i < leading; i += 1) {
      container.appendChild(buildCell("calendar-cell calendar-cell--empty", ""));
    }

    for (var day = 1; day <= daysInMonth; day += 1) {
      var iso = year + "-" + pad(month) + "-" + pad(day);
      var summary = byDate[iso];
      var classes = ["calendar-cell"];

      if (iso === todayIso) {
        classes.push("calendar-cell--today");
      }
      if (summary && summary.totalTasks > 0 && summary.approvedTasks === summary.totalTasks) {
        classes.push("calendar-cell--all-done");
      }

      var cell = document.createElement("a");
      cell.className = classes.join(" ");
      cell.href = dayUrlBase + iso;

      var dayLabel = document.createElement("span");
      dayLabel.className = "calendar-cell__day";
      dayLabel.textContent = String(day);
      cell.appendChild(dayLabel);

      if (summary && summary.totalTasks > 0) {
        var stat = document.createElement("span");
        stat.className = "calendar-cell__stat";
        stat.textContent = "✅ " + summary.approvedTasks + "/" + summary.totalTasks;
        cell.appendChild(stat);

        if (summary.earnedPoints > 0) {
          var points = document.createElement("span");
          points.className = "calendar-cell__points";
          points.textContent = "⭐ +" + summary.earnedPoints;
          cell.appendChild(points);
        }
        cell.setAttribute(
          "aria-label",
          month + " 月 " + day + " 日，完成 " + summary.approvedTasks +
            " / " + summary.totalTasks + " 個任務，取得 " + summary.earnedPoints + " 點"
        );
      } else {
        cell.setAttribute("aria-label", month + " 月 " + day + " 日，沒有任務");
      }

      container.appendChild(cell);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var container = document.querySelector("[data-calendar]");
    if (!container) {
      return;
    }

    var year = parseInt(container.dataset.year, 10);
    var month = parseInt(container.dataset.month, 10);
    var todayIso = container.dataset.today;
    var dayUrlBase = container.dataset.dayUrl;
    var status = document.querySelector("[data-calendar-status]");

    fetch("/api/calendar?year=" + year + "&month=" + month, {
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("calendar request failed");
        }
        return response.json();
      })
      .then(function (data) {
        render(container, year, month, data, todayIso, dayUrlBase);
        if (status) {
          status.remove();
        }
      })
      .catch(function () {
        // 網路或伺服器異常時仍畫出月曆，只是沒有統計數字。
        render(container, year, month, [], todayIso, dayUrlBase);
        if (status) {
          status.textContent = "行事曆的星星資料載入慢了一點，再重新整理看看 🌈";
        }
      });
  });
})();
