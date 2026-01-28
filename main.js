class LottoDisplay extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
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
          background-color: #f0f0f0;
          display: flex;
          justify-content: center;
          align-items: center;
          font-size: 1.5rem;
          font-weight: bold;
          color: #333;
          box-shadow: 0 4px 8px rgba(0,0,0,0.1);
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
            numberDiv.style.backgroundColor = this.getNumberColor(number);
            numberDiv.style.color = 'white';
            container.appendChild(numberDiv);
        }, index * 200);
    });
  }

  getNumberColor(number) {
    if (number <= 10) return '#f39c12'; // 주황색
    if (number <= 20) return '#3498db'; // 파란색
    if (number <= 30) return '#e74c3c'; // 빨간색
    if (number <= 40) return '#2ecc71'; // 녹색
    return '#9b59b6'; // 보라색
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
