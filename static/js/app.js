/* 共用行為：Flash 關閉、表單防重複送出。
   刻意保持精簡，不做成 3000 行的巨大檔案。 */

(function () {
  "use strict";

  /** 使用者是否偏好減少動態效果。 */
  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  window.FamilyReward = window.FamilyReward || {};
  window.FamilyReward.prefersReducedMotion = prefersReducedMotion;

  document.addEventListener("DOMContentLoaded", function () {
    // Flash 訊息：手動關閉 + 成功訊息自動淡出。
    document.querySelectorAll("[data-flash-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        var flash = button.closest(".flash");
        if (flash) {
          flash.remove();
        }
      });
    });

    document.querySelectorAll(".flash--success").forEach(function (flash) {
      window.setTimeout(function () {
        flash.style.transition = "opacity 400ms ease";
        flash.style.opacity = "0";
        window.setTimeout(function () {
          flash.remove();
        }, 400);
      }, 6000);
    });

    // 集點卡設定：家長一邊輸入就即時顯示「會變成幾張」。
    // 資料由後端以 JSON 放在 data- 屬性，不把使用者文字插進 JS。
    // 沒有 JS 時畫面仍有伺服器算好的現狀，只是少了即時預覽。
    (function () {
      var input = document.querySelector("[data-points-per-card-input]");
      var box = document.querySelector("[data-card-preview]");
      if (!input || !box) {
        return;
      }

      var lifetimes, names;
      try {
        lifetimes = JSON.parse(box.dataset.lifetimes || "[]");
        names = JSON.parse(box.dataset.names || "[]");
      } catch (err) {
        return;
      }

      var slots = box.querySelectorAll("[data-preview-after]");

      function update() {
        var value = parseInt(input.value, 10);
        var valid = !isNaN(value) && value > 0;

        slots.forEach(function (slot, index) {
          if (!valid || index >= lifetimes.length) {
            slot.textContent = "";
            return;
          }
          // 和後端 get_card_progress 一樣的整數運算。
          var cards = Math.floor(lifetimes[index] / value);
          var current = lifetimes[index] % value;
          slot.textContent =
            "→ 會變成 " + cards + " 張（第 " + (cards + 1) + " 張 " +
            current + "/" + value + "）";
        });
      }

      input.addEventListener("input", update);
      update();
    })();

    // 送出後把按鈕鎖起來，避免小孩或家長連按兩次。
    // 後端本來就有防重複保護，這裡只是讓 UI 更明確。
    document.querySelectorAll("form[data-once]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var buttons = form.querySelectorAll("button[type='submit']");
        buttons.forEach(function (button) {
          button.disabled = true;
          if (button.dataset.busyText) {
            button.textContent = button.dataset.busyText;
          }
        });
      });
    });
  });
})();
