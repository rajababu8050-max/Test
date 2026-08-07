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
            top: 20px;
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
            padding: 35px 25px;
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
            margin-bottom: 10px;
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
            margin-bottom: 20px;
        }

        .btn-group {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .action-btn {
            background: linear-gradient(135deg, #ffd700, #00ff88);
            color: #000;
            border: none;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 800;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.6);
            transition: all 0.2s ease-in-out;
        }

        .action-btn:active {
            transform: scale(0.92);
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
        
        <div class="btn-group">
            <button class="action-btn" onclick="nextQuote(event)">NEXT QUOTE 🎲</button>
            <button class="action-btn" id="musicBtn" onclick="toggleAudio(event)">🔊 MUSIC: OFF</button>
        </div>
    </div>

    <!-- Farzi "Paisa Hai Toh" Audio Track -->
    <audio id="farziAudio" loop preload="auto">
        <source src="https://cdnsongs.com/music/data/Hindi_Movies/202301/Farzi/128/Paisa_Hai_Toh_1.mp3" type="audio/mpeg">
    </audio>

    <script>
        const audio = document.getElementById('farziAudio');
        const musicBtn = document.getElementById('musicBtn');
        let isPlaying = false;

        function toggleAudio(e) {
            if (e) e.stopPropagation();
            if (isPlaying) {
                audio.pause();
                isPlaying = false;
                musicBtn.innerText = "🔇 MUSIC: OFF";
                musicBtn.style.background = "linear-gradient(135deg, #ffd700, #00ff88)";
            } else {
                audio.play().then(() => {
                    isPlaying = true;
                    musicBtn.innerText = "🔊 MUSIC: ON";
                    musicBtn.style.background = "#00ff88";
                }).catch(err => console.log("User interaction required"));
            }
        }

        // Live Wealth Counter
        let count = 1000000;
        setInterval(() => {
            count += Math.floor(Math.random() * 500) + 100;
            document.getElementById('counter').innerText = '$' + count.toLocaleString();
        }, 100);

        // Multi-Quotes List
        const quotesList = [
            "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.",
            "PAISA BOLTA NAHI,\\nLEKIN SABKI BOLTI BAND KAR DETA HAI.",
            "WORK HARD IN SILENCE,\\nLET YOUR BANK BALANCE MAKE THE NOISE.",
            "APNA TIME AATA NAHI,\\nPAISE SE LANA PADTA HAI."
        ];
        let currentQuoteIndex = 0;

        function nextQuote(e) {
            if (e) e.stopPropagation();
            currentQuoteIndex = (currentQuoteIndex + 1) % quotesList.length;
            document.getElementById('quoteText').innerHTML = "";
            document.getElementById('authorText').innerHTML = "";
            i = 0; j = 0;
            q = quotesList[currentQuoteIndex];
            type();
        }

        // Typing Effect
        let q = quotesList[0];
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

        // Click Burst Effect & Screen Touch Auto Audio Trigger
        window.addEventListener('click', (e) => {
            if (!isPlaying) {
                toggleAudio();
            }

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
