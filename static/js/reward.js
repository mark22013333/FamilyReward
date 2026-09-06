/* 禮物頁面互動。 */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-reward-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        if (window.FamilyReward && window.FamilyReward.confetti) {
          window.FamilyReward.confetti(30);
        }
      });
    });
  });
})();
