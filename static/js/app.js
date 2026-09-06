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
