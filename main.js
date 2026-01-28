class LottoDisplay extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --number-bg-color: #f0f0f0;
          --number-text-color: #333;
          --shadow-color: rgba(0,0,0,0.1);
        }
        :host-context(body.dark-mode) {
          --number-bg-color: #5a5a5a;
          --number-text-color: #f0f2f5;
          --shadow-color: rgba(0,0,0,0.7);
        }
        .lotto-numbers {
          display: flex;
          justify-content: center;
          gap: 1rem;
          flex-wrap: wrap;
        }
        .number {
          width: 50px;
          height: 50px;
          border-radius: 50%;
          background-color: var(--number-bg-color);
          display: flex;
          justify-content: center;
          align-items: center;
          font-size: 1.5rem;
          font-weight: bold;
          color: var(--number-text-color);
          box-shadow: 0 4px 8px var(--shadow-color);
          transition: all 0.3s ease;
        }
      </style>
      <div class="lotto-numbers"></div>
    `;
  }

  displayNumbers(numbers) {
    const container = this.shadowRoot.querySelector('.lotto-numbers');
    container.innerHTML = '';
    numbers.forEach((number, index) => {
        setTimeout(() => {
            const numberDiv = document.createElement('div');
            numberDiv.className = 'number';
            numberDiv.textContent = number;
            container.appendChild(numberDiv);
        }, index * 200);
    });
  }
}

customElements.define('lotto-display', LottoDisplay);

document.getElementById('generator-btn').addEventListener('click', () => {
  const lottoDisplay = document.querySelector('lotto-display');
  lottoDisplay.displayNumbers(generateLottoNumbers());
});

function generateLottoNumbers() {
  const numbers = new Set();
  while (numbers.size < 6) {
    numbers.add(Math.floor(Math.random() * 45) + 1);
  }
  return Array.from(numbers).sort((a, b) => a - b);
}

document.getElementById('theme-toggle').addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const themeToggle = document.getElementById('theme-toggle');
    if (document.body.classList.contains('dark-mode')) {
        themeToggle.textContent = '☀️';
    } else {
        themeToggle.textContent = '🌙';
    }
});
