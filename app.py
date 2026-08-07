from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - Money Mindset</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: radial-gradient(circle at center, #112211 0%, #050a05 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Montserrat', 'Segoe UI', sans-serif;
            overflow: hidden;
            position: relative;
        }

        /* Matrix / Rain Canvas */
        #moneyCanvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* VIP Card Design */
        .card {
            position: relative;
            z-index: 2;
            background: rgba(5, 20, 10, 0.75);
            border: 2px solid #00ff88;
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.4), inset 0 0 20px rgba(255, 215, 0, 0.3);
            padding: 50px 40px;
            border-radius: 25px;
            text-align: center;
            max-width: 650px;
            width: 90%;
            backdrop-filter: blur(12px);
            animation: float 4s ease-in-out infinite, pulseGlow 2s infinite alternate;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-12px); }
        }

        @keyframes pulseGlow {
            0% { border-color: #00ff88; box-shadow: 0 0 25px rgba(0, 255, 136, 0.4); }
            100% { border-color: #ffd700; box-shadow: 0 0 45px rgba(255, 215, 0, 0.6); }
        }

        .icon-header {
            font-size: 50px;
            margin-bottom: 15px;
            animation: bounce 1.5s infinite;
        }

        @keyframes bounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }

        .quote {
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(135deg, #ffd700 0%, #00ff88 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
            margin-bottom: 25px;
            line-height: 1.4;
            letter-spacing: 1px;
            min-height: 80px;
        }

        .author {
            font-size: 22px;
            font-weight: 800;
            color: #ffffff;
            text-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
            letter-spacing: 4px;
            text-transform: uppercase;
        }
    </style>
</head>
<body>

    <canvas id="moneyCanvas"></canvas>

    <div class="card">
        <div class="icon-header">🤑 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // Money Rain Animation
        const canvas = document.getElementById('moneyCanvas');
        const ctx = canvas.getContext('2d');

        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();

        const currencies = ['$', '₹', '€', '£', '¥', '💰', '💵', '🤑', '💎'];
        const drops = Array.from({length: 70}, () => ({
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
                ctx.fillStyle = d.symbol === '💰' || d.symbol === '💵' || d.symbol === '🤑' ? '#ffffff' : '#00ff88';
                ctx.shadowBlur = 10;
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

        // Typing Effect
        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\\n' ? '<br>' : q[i];
                i++; setTimeout(type, 50);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; setTimeout(type, 70);
            }
        }
        setTimeout(type, 400);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT
