from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - Billionaire Mindset</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: #020403;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            position: relative;
            perspective: 1200px;
        }

        /* Ambient Glow Background */
        .ambient-light {
            position: absolute;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(0,255,136,0.15) 0%, rgba(255,215,0,0.1) 40%, transparent 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
            pointer-events: none;
            animation: pulseGlow 4s ease-in-out infinite alternate;
        }

        @keyframes pulseGlow {
            0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.5; }
            100% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
        }

        #canvas-bg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* Top Wealth Counter */
        .wealth-counter {
            position: absolute;
            top: 25px;
            z-index: 10;
            font-size: 22px;
            font-weight: 900;
            color: #ffd700;
            background: rgba(0, 15, 8, 0.85);
            padding: 12px 30px;
            border-radius: 50px;
            border: 2px solid #ffd700;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5), inset 0 0 10px rgba(255, 215, 0, 0.3);
            letter-spacing: 2px;
            backdrop-filter: blur(10px);
            text-shadow: 0 0 10px #ffd700;
        }

        /* Futuristic VIP Card */
        .card {
            position: relative;
            z-index: 2;
            background: linear-gradient(145deg, rgba(5, 25, 12, 0.9), rgba(2, 10, 5, 0.95));
            border: 2px solid #00ff88;
            box-shadow: 
                0 0 40px rgba(0, 255, 136, 0.4),
                inset 0 0 25px rgba(255, 215, 0, 0.2),
                0 20px 50px rgba(0,0,0,0.8);
            padding: 55px 40px;
            border-radius: 28px;
            text-align: center;
            max-width: 650px;
            width: 90%;
            backdrop-filter: blur(20px);
            transform-style: preserve-3d;
            transition: transform 0.1s ease-out;
        }

        .card::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, #ffd700, transparent, #00ff88);
            border-radius: 30px;
            z-index: -1;
            opacity: 0.5;
        }

        .icon-header {
            font-size: 55px;
            margin-bottom: 20px;
            filter: drop-shadow(0 0 15px #ffd700);
            animation: bounce 2s ease-in-out infinite;
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-10px) scale(1.1); }
        }

        .quote {
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(135deg, #ffffff 0%, #ffd700 50%, #00ff88 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 15px rgba(255, 215, 0, 0.5));
            margin-bottom: 25px;
            line-height: 1.4;
            min-height: 80px;
            letter-spacing: 1px;
        }

        .author {
            font-size: 20px;
            font-weight: 900;
            color: #00ff88;
            text-shadow: 0 0 15px #00ff88, 0 0 30px #00ff88;
            letter-spacing: 4px;
            text-transform: uppercase;
        }

        /* Particle Explosion */
        .particle {
            position: absolute;
            pointer-events: none;
            font-size: 26px;
            z-index: 99;
            font-weight: bold;
            animation: burst 0.8s ease-out forwards;
        }

        @keyframes burst {
            0% { opacity: 1; transform: translate(0, 0) scale(1) rotate(0deg); }
            100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(2) rotate(360deg); }
        }
    </style>
</head>
<body>

    <div class="ambient-light"></div>
    <div class="wealth-counter">NET WORTH: <span id="counter">$1,000,000</span></div>

    <canvas id="canvas-bg"></canvas>

    <div class="card" id="tiltCard">
        <div class="icon-header">🤑 💎 💰</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // 1. High Performance Fast Canvas Matrix Rain
        const canvas = document.getElementById('canvas-bg');
        const ctx = canvas.getContext('2d');

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        window.onresize = resize;
        resize();

        const symbols = ['$', '₹', '€', '£', '¥', '💰', '💵', '🤑', '💎', '👑', '777'];
        const columns = Math.floor(canvas.width / 25);
        const drops = Array.from({length: columns}, () => Math.random() * -100);

        function drawRain() {
            ctx.fillStyle = 'rgba(2, 4, 3, 0.15)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.font = '18px monospace';

            for (let i = 0; i < drops.length; i++) {
                const text = symbols[Math.floor(Math.random() * symbols.length)];
                const x = i * 25;
                const y = drops[i] * 25;

                ctx.fillStyle = (i % 3 === 0) ? '#ffd700' : '#00ff88';
                ctx.shadowBlur = 10;
                ctx.shadowColor = ctx.fillStyle;
                ctx.fillText(text, x, y);

                if (y > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
            requestAnimationFrame(drawRain);
        }
        drawRain();

        // 2. Typing Effect
        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\\n' ? '<br>' : q[i];
                i++; setTimeout(type, 35);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; setTimeout(type, 50);
            }
        }
        setTimeout(type, 300);

        // 3. Ultra Fast Live Wealth Counter
        let count = 1000000;
        setInterval(() => {
            count += Math.floor(Math.random() * 800) + 200;
            document.getElementById('counter').innerText = '$' + count.toLocaleString();
        }, 70);

        // 4. Interactive Tap Shockwave & Cash Burst
        window.addEventListener('click', (e) => {
            for(let k = 0; k < 15; k++) {
                const p = document.createElement('div');
                p.className = 'particle';
                p.innerText = symbols[Math.floor(Math.random() * symbols.length)];
                p.style.left = e.clientX + 'px';
                p.style.top = e.clientY + 'px';
                
                const angle = Math.random() * Math.PI * 2;
                const distance = Math.random() * 200 + 50;
                const dx = Math.cos(angle) * distance + 'px';
                const dy = Math.sin(angle) * distance + 'px';

                p.style.setProperty('--dx', dx);
                p.style.setProperty('--dy', dy);
                document.body.appendChild(p);
                setTimeout(() => p.remove(), 800);
            }
        });

        // 5. 3D Dynamic Card Tilt Motion
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
