/* 任務卡互動：按下「我完成了！」時的即時回饋。
   真正的狀態變更由後端處理（PRG），這裡只負責讓小孩看到反應。 */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-task-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var card = form.closest(".task-card");
        var points = parseInt(form.dataset.points, 10) || 1;
        if (card && window.FamilyReward && window.FamilyReward.flyStars) {
          window.FamilyReward.flyStars(
            card,
            document.querySelector("[data-points-card]"),
            points
          );
        }
      });
    });
  });
})();
