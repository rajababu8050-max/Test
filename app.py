from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - Money Mindset Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: radial-gradient(circle at center, #0f2310 0%, #030803 100%);
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            position: relative;
            perspective: 1000px;
        }

        .wealth-counter {
            position: absolute;
            top: 25px;
            z-index: 10;
            font-size: 20px;
            font-weight: 900;
            color: #ffd700;
            background: rgba(0, 0, 0, 0.6);
            padding: 10px 25px;
            border-radius: 50px;
            border: 1px solid #ffd700;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
            letter-spacing: 1.5px;
        }

        #moneyCanvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        .card {
            position: relative;
            z-index: 2;
            background: rgba(5, 20, 10, 0.85);
            border: 2px solid #00ff88;
            box-shadow: 0 0 35px rgba(0, 255, 136, 0.4), inset 0 0 20px rgba(255, 215, 0, 0.3);
            padding: 45px 30px;
            border-radius: 25px;
            text-align: center;
            max-width: 600px;
            width: 90%;
            backdrop-filter: blur(12px);
            transition: transform 0.1s ease-out;
            transform-style: preserve-3d;
        }

        .icon-header {
            font-size: 45px;
            margin-bottom: 15px;
            animation: bounce 1.5s infinite;
        }

        @keyframes bounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.15); }
        }

        .quote {
            font-size: 24px;
            font-weight: 900;
            background: linear-gradient(135deg, #ffd700 0%, #00ff88 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
            margin-bottom: 20px;
            line-height: 1.4;
            min-height: 75px;
        }

        .author {
            font-size: 18px;
            font-weight: 800;
            color: #ffffff;
            text-shadow: 0 0 10px #00ff88;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        .particle {
            position: absolute;
            pointer-events: none;
            font-size: 24px;
            z-index: 99;
            animation: pop 0.8s ease-out forwards;
        }

        @keyframes pop {
            0% { opacity: 1; transform: translate(0, 0) scale(1); }
            100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(1.8); }
        }
    </style>
</head>
<body>

    <div class="wealth-counter">WEALTH: <span id="counter">$1,000,000</span></div>

    <canvas id="moneyCanvas"></canvas>

    <div class="card" id="tiltCard">
        <div class="icon-header">🤑 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // Live Wealth Counter
        let count = 1000000;
        setInterval(() => {
            count += Math.floor(Math.random() * 500) + 100;
            document.getElementById('counter').innerText = '$' + count.toLocaleString();
        }, 100);

        // Single Original Quote
        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\\n' ? '<br>' : q[i];
                i++; setTimeout(type, 40);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; setTimeout(type, 60);
            }
        }
        setTimeout(type, 300);

        // Money Rain Effect
        const canvas = document.getElementById('moneyCanvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();

        const currencies = ['$', '₹', '€', '£', '¥', '💰', '💵', '🤑', '💎'];
        const drops = Array.from({length: 60}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height - canvas.height,
            speed: Math.random() * 3 + 2,
            symbol: currencies[Math.floor(Math.random() * currencies.length)],
            size: Math.random() * 20 + 16
        }));

        function drawMoney() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            drops.forEach(d => {
                ctx.font = `${d.size}px sans-serif`;
                ctx.fillStyle = '#00ff88';
                ctx.shadowBlur = 8;
                ctx.shadowColor = '#00ff88';
                ctx.fillText(d.symbol, d.x, d.y);
                d.y += d.speed;
                if(d.y > canvas.height) {
                    d.y = -30;
                    d.x = Math.random() * canvas.width;
                }
            });
            requestAnimationFrame(drawMoney);
        }
        drawMoney();

        // Click Burst Effect
        window.addEventListener('click', (e) => {
            for(let k = 0; k < 12; k++) {
                const p = document.createElement('div');
                p.className = 'particle';
                p.innerText = currencies[Math.floor(Math.random() * currencies.length)];
                p.style.left = e.clientX + 'px';
                p.style.top = e.clientY + 'px';
                const dx = (Math.random() - 0.5) * 300 + 'px';
                const dy = (Math.random() - 0.5) * 300 + 'px';
                p.style.setProperty('--dx', dx);
                p.style.setProperty('--dy', dy);
                document.body.appendChild(p);
                setTimeout(() => p.remove(), 800);
            }
        });

        // 3D Card Tilt Effect
        const card = document.getElementById('tiltCard');
        window.addEventListener('mousemove', (e) => {
            const x = (window.innerWidth / 2 - e.clientX) / 20;
            const y = (window.innerHeight / 2 - e.clientY) / 20;
            card.style.transform = `rotateY(${-x}deg) rotateX(${y}deg)`;
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT
