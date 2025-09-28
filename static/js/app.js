(function () {
  const CONFETTI_COLORS = [
    "#ff6b6b",
    "#feca57",
    "#48dbfb",
    "#1dd1a1",
    "#5f27cd",
    "#ff9ff3",
  ];

  function launchConfetti() {
    const pieces = 40;
    for (let i = 0; i < pieces; i += 1) {
      const piece = document.createElement("span");
      piece.className = "confetti-piece";
      piece.style.left = `${Math.random() * 100}vw`;
      piece.style.backgroundColor = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
      piece.style.animationDuration = `${2 + Math.random()}s`;
      piece.style.animationDelay = `${Math.random() * 0.5}s`;
      piece.style.transform = `rotate(${Math.random() * 360}deg)`;
      document.body.appendChild(piece);
      window.setTimeout(() => {
        piece.remove();
      }, 3500);
    }
  }

  function attachConfettiTriggers() {
    const triggers = document.querySelectorAll("[data-confetti-trigger]");
    triggers.forEach((trigger) => {
      const activate = () => {
        trigger.classList.add("active");
        launchConfetti();
        window.setTimeout(() => trigger.classList.remove("active"), 1200);
      };

      trigger.addEventListener("click", activate);
      trigger.addEventListener("keypress", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", attachConfettiTriggers);
})();
