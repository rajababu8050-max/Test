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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            position: relative;
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
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.4), inset 0 0 20px rgba(255, 215, 0, 0.3);
            padding: 40px 25px;
            border-radius: 25px;
            text-align: center;
            max-width: 600px;
            width: 90%;
            backdrop-filter: blur(12px);
            animation: float 4s ease-in-out infinite, pulseGlow 2s infinite alternate;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }

        @keyframes pulseGlow {
            0% { border-color: #00ff88; box-shadow: 0 0 25px rgba(0, 255, 136, 0.4); }
            100% { border-color: #ffd700; box-shadow: 0 0 45px rgba(255, 215, 0, 0.6); }
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
            min-height: 70px;
        }

        .author {
            font-size: 18px;
            font-weight: 800;
            color: #ffffff;
            text-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 25px;
        }

        .play-btn {
            background: linear-gradient(135deg, #ffd700, #00ff88);
            color: #000;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            font-weight: 900;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.8);
            transition: all 0.2s ease-in-out;
            letter-spacing: 1px;
        }

        .play-btn:active {
            transform: scale(0.95);
        }
    </style>
</head>
<body onclick="enableAudioOnTouch()">

    <canvas id="moneyCanvas"></canvas>

    <div class="card">
        <div class="icon-header">🤑 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
        <button class="play-btn" id="playBtn" onclick="toggleAudio(event)">🔊 TAP TO PLAY MUSIC</button>
    </div>

    <!-- Direct High-Compatibility Audio Stream -->
    <audio id="farziAudio" loop preload="auto">
        <source src="https://codeskulptor-demos.commondatastorage.googleapis.com/assets_sounddog/soundtrack.mp3" type="audio/mpeg">
    </audio>

    <script>
        const audio = document.getElementById('farziAudio');
        const btn = document.getElementById('playBtn');
        let isPlaying = false;

        function enableAudioOnTouch() {
            if (!isPlaying) {
                audio.play().then(() => {
                    isPlaying = true;
                    btn.innerHTML = "⏸ PAUSE MUSIC 🔊";
                    btn.style.background = "#00ff88";
                }).catch(err => console.log("Touch required"));
            }
        }

        function toggleAudio(e) {
            e.stopPropagation();
            if (isPlaying) {
                audio.pause();
                isPlaying = false;
                btn.innerHTML = "▶ PLAY MUSIC 🎵";
                btn.style.background = "linear-gradient(135deg, #ffd700, #00ff88)";
            } else {
                audio.play();
                isPlaying = true;
                btn.innerHTML = "⏸ PAUSE MUSIC 🔊";
                btn.style.background = "#00ff88";
            }
        }

        // Background Money Rain
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
                ctx.fillStyle = d.symbol === '💰' || d.symbol === '💵' || d.symbol === '🤑' ? '#ffffff' : '#00ff88';
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
        setTimeout(type, 300);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT
