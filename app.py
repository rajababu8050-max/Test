import os
from flask import Flask, send_from_directory

app = Flask(__name__)

AUDIO_FILENAME = "song.mp3"

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
            background: #030604;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            overflow: hidden;
            position: relative;
            perspective: 1000px;
            cursor: pointer;
            user-select: none;
        }

        .spotlight {
            position: absolute;
            width: 800px;
            height: 800px;
            background: radial-gradient(circle, rgba(212, 175, 55, 0.2) 0%, rgba(0, 255, 136, 0.1) 40%, transparent 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
            pointer-events: none;
            filter: blur(60px);
            animation: pulseLight 4s ease-in-out infinite alternate;
        }

        @keyframes pulseLight {
            0% { transform: translate(-50%, -50%) scale(0.95); opacity: 0.7; }
            100% { transform: translate(-50%, -50%) scale(1.1); opacity: 1; }
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
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(0, 0, 0, 0.5));
            border: 1px solid rgba(212, 175, 55, 0.6);
            box-shadow: 0 0 50px rgba(0, 0, 0, 0.5), inset 0 0 20px rgba(255, 255, 255, 0.05);
            padding: 60px 40px;
            border-radius: 30px;
            text-align: center;
            max-width: 600px;
            width: 90%;
            backdrop-filter: blur(30px);
            transform-style: preserve-3d;
            transition: transform 0.2s ease-out;
        }

        .card-moving {
            animation: floatAndRotate 4s ease-in-out infinite alternate !important;
        }

        @keyframes floatAndRotate {
            0% {
                transform: translateY(0px) rotateX(0deg) rotateY(0deg) scale(1);
                box-shadow: 0 0 50px rgba(0, 0, 0, 0.5), 0 0 20px rgba(212, 175, 55, 0.3);
            }
            50% {
                transform: translateY(-20px) rotateX(6deg) rotateY(-8deg) scale(1.03);
                box-shadow: 0 25px 60px rgba(0, 255, 136, 0.4), 0 0 40px rgba(212, 175, 55, 0.6);
            }
            100% {
                transform: translateY(15px) rotateX(-6deg) rotateY(8deg) scale(1.01);
                box-shadow: 0 15px 50px rgba(0, 0, 0, 0.7), 0 0 30px rgba(255, 215, 0, 0.5);
            }
        }

        .icon-header {
            font-size: 60px;
            margin-bottom: 25px;
            filter: drop-shadow(0 10px 15px rgba(0,0,0,0.8));
            animation: bounce 3s ease-in-out infinite;
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-12px); }
        }

        /* REALISTIC 3D GOLDEN TEXT */
        .quote {
            font-size: 30px;
            font-weight: 900;
            background: linear-gradient(180deg, #FFFFFF 0%, #FFE57F 30%, #D4AF37 70%, #8A6400 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
            line-height: 1.35;
            min-height: 80px;
            
            /* Multi-layer 3D Extrusion Shadow Effect */
            filter: 
                drop-shadow(1px 1px 0px #b8860b)
                drop-shadow(2px 2px 0px #8b6508)
                drop-shadow(3px 3px 0px #5c4305)
                drop-shadow(4px 4px 2px rgba(0, 0, 0, 0.8))
                drop-shadow(0px 0px 15px rgba(255, 215, 0, 0.6));
            letter-spacing: 1px;
        }

        /* REALISTIC 3D NEON AUTHOR TEXT */
        .author {
            font-size: 21px;
            font-weight: 900;
            color: #00ff88;
            letter-spacing: 5px;
            text-transform: uppercase;
            
            /* 3D Depth & Neon Ambient Emission */
            text-shadow: 
                0px 1px 0px #00a859,
                0px 2px 0px #00753e,
                0px 3px 0px #004223,
                0px 4px 10px rgba(0, 0, 0, 0.9),
                0px 0px 15px #00ff88,
                0px 0px 30px rgba(0, 255, 136, 0.8);
        }

        .sparkle {
            position: absolute;
            pointer-events: none;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #FFE57F;
            z-index: 99;
            animation: burst 0.6s ease-out forwards;
        }

        @keyframes burst {
            0% { opacity: 1; transform: translate(0, 0) scale(1.5); }
            100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(0.3); }
        }
    </style>
</head>
<body onclick="handleScreenTap(event)">

    <div class="spotlight"></div>
    <canvas id="moneyCanvas"></canvas>

    <div class="card" id="card3d">
        <div class="icon-header">💎 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <audio id="bgMusic" loop preload="auto">
        <source src="/audio" type="audio/mpeg">
    </audio>

    <script>
        const bgAudio = document.getElementById('bgMusic');
        let isMusicPlaying = false;

        function handleScreenTap(e) {
            for (let k = 0; k < 20; k++) {
                const sparkle = document.createElement('div');
                sparkle.className = 'sparkle';
                sparkle.style.left = e.clientX + 'px';
                sparkle.style.top = e.clientY + 'px';
                const angle = Math.random() * Math.PI * 2;
                const dist = Math.random() * 150 + 50;
                sparkle.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
                sparkle.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
                document.body.appendChild(sparkle);
                setTimeout(() => sparkle.remove(), 600);
            }

            if (isMusicPlaying) {
                bgAudio.pause();
                isMusicPlaying = false;
            } else {
                bgAudio.play().then(() => isMusicPlaying = true).catch(e => console.log("User tap required"));
            }
        }

        const canvas = document.getElementById('moneyCanvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();

        const symbols = ['$', '₹', '€', '£', '¥', '💰', '💵', '💎'];
        const particles = Array.from({length: 80}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 20 + 16,
            speedY: Math.random() * 8.0 + 5.0,
            symbol: symbols[Math.floor(Math.random() * symbols.length)]
        }));

        function drawParticles() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => {
                ctx.font = `${p.size}px Arial`;
                ctx.fillStyle = 'rgba(212, 175, 55, 0.8)';
                ctx.shadowBlur = 10;
                ctx.shadowColor = '#D4AF37';
                ctx.fillText(p.symbol, p.x, p.y);
                p.y += p.speedY;
                if (p.y > canvas.height) { p.y = -30; p.x = Math.random() * canvas.width; }
            });
            requestAnimationFrame(drawParticles);
        }
        drawParticles();

        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;
        const card = document.getElementById('card3d');

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\\n' ? '<br>' : q[i];
                i++; setTimeout(type, 40);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; setTimeout(type, 60);
            } else {
                card.classList.add('card-moving');
            }
        }
        setTimeout(type, 300);

        window.addEventListener('mousemove', (e) => {
            if (!card.classList.contains('card-moving')) {
                const x = (window.innerWidth / 2 - e.clientX) / 20;
                const y = (window.innerHeight / 2 - e.clientY) / 20;
                card.style.transform = `rotateY(${-x}deg) rotateX(${y}deg)`;
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT

@app.route("/audio")
def serve_audio():
    return send_from_directory(os.getcwd(), AUDIO_FILENAME)

if __name__ == "__main__":
    app.run(debug=True)
