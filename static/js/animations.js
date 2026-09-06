/* Confetti 與飛星動畫。自行實作，不引入額外套件。
   所有動畫都尊重 prefers-reduced-motion。 */

(function () {
  "use strict";

  var COLORS = ["#FFD166", "#06D6A0", "#118AB2", "#EF476F", "#9B5DE5"];

  function reduced() {
    return (
      window.FamilyReward &&
      window.FamilyReward.prefersReducedMotion &&
      window.FamilyReward.prefersReducedMotion()
    );
  }

  /**
   * 播放一次 Confetti。
   * @param {number} count 紙屑數量
   */
  function confetti(count) {
    if (reduced()) {
      return;
    }
    var pieces = count || 60;
    var layer = document.createElement("div");
    layer.className = "confetti-layer";
    layer.setAttribute("aria-hidden", "true");

    for (var i = 0; i < pieces; i += 1) {
      var piece = document.createElement("span");
      piece.className = "confetti-piece";
      piece.style.left = Math.random() * 100 + "vw";
      piece.style.background = COLORS[i % COLORS.length];
      piece.style.animationDuration = 1800 + Math.random() * 1400 + "ms";
      piece.style.animationDelay = Math.random() * 400 + "ms";
      layer.appendChild(piece);
    }

    document.body.appendChild(layer);
    window.setTimeout(function () {
      layer.remove();
    }, 4000);
  }

  /**
   * 從某個元素飛出星星到集點卡。
   * @param {Element} source 起點元素
   * @param {Element} target 終點元素（集點卡）
   * @param {number} amount 星星數量
   */
  function flyStars(source, target, amount) {
    if (reduced() || !source) {
      return;
    }
    var from = source.getBoundingClientRect();
    var to = target ? target.getBoundingClientRect() : null;
    var total = Math.min(amount || 1, 6);

    for (var i = 0; i < total; i += 1) {
      (function (index) {
        window.setTimeout(function () {
          var star = document.createElement("span");
          star.className = "flying-star";
          star.textContent = "⭐";
          star.setAttribute("aria-hidden", "true");
          star.style.left = from.left + from.width / 2 + "px";
          star.style.top = from.top + "px";
          if (to) {
            star.style.setProperty(
              "--fly-x",
              to.left + to.width / 2 - (from.left + from.width / 2) + "px"
            );
            star.style.setProperty("--fly-y", to.top - from.top + "px");
          }
          document.body.appendChild(star);
          window.setTimeout(function () {
            star.remove();
          }, 1200);
        }, index * 120);
      })(i);
    }
  }

  window.FamilyReward = window.FamilyReward || {};
  window.FamilyReward.confetti = confetti;
  window.FamilyReward.flyStars = flyStars;

  document.addEventListener("DOMContentLoaded", function () {
    // 有慶祝橫幅時播放一次 Confetti。
    // 通知在後端已標記為已讀，所以重新整理不會重播。
    var celebrate = document.querySelector("[data-celebrate]");
    if (celebrate) {
      confetti(80);
      var card = document.querySelector("[data-points-card]");
      flyStars(celebrate, card, parseInt(celebrate.dataset.celebrate, 10) || 1);
    }
  });
})();
