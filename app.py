import os
from flask import Flask, send_from_directory

app = Flask(__name__)

# Main folder me rakhi audio file ka naam
AUDIO_FILENAME = "song.mp3"

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - 3D Hologram Edition</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: #020403;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            overflow: hidden;
            position: relative;
            perspective: 1200px;
            cursor: pointer;
            user-select: none;
        }

        .spotlight {
            position: absolute;
            width: 800px;
            height: 800px;
            background: radial-gradient(circle, rgba(212, 175, 55, 0.25) 0%, rgba(0, 255, 136, 0.12) 40%, transparent 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
            pointer-events: none;
            filter: blur(60px);
            animation: pulseLight 4s ease-in-out infinite alternate;
        }

        @keyframes pulseLight {
            0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.7; }
            100% { transform: translate(-50%, -50%) scale(1.15); opacity: 1; }
        }

        #moneyCanvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* 3D Glass Container */
        .card {
            position: relative;
            z-index: 2;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.65));
            border: 2px solid rgba(212, 175, 55, 0.7);
            box-shadow: 
                0 0 50px rgba(0, 255, 136, 0.3),
                0 30px 80px rgba(0, 0, 0, 0.9),
                inset 0 0 30px rgba(212, 175, 55, 0.2);
            padding: 60px 35px;
            border-radius: 30px;
            text-align: center;
            max-width: 650px;
            width: 92%;
            backdrop-filter: blur(35px);
            transform-style: preserve-3d;
            transition: transform 0.1s ease-out;
        }

        .icon-header {
            font-size: 65px;
            margin-bottom: 25px;
            filter: drop-shadow(0 15px 20px rgba(0,0,0,0.8));
            transform: translateZ(50px);
            animation: bounce 3s ease-in-out infinite;
        }

        @keyframes bounce {
            0%, 100% { transform: translateZ(50px) translateY(0px); }
            50% { transform: translateZ(70px) translateY(-12px); }
        }

        /* 3D Pop-out Text Base */
        .quote {
            font-size: 30px;
            font-weight: 900;
            line-height: 1.4;
            min-height: 90px;
            margin-bottom: 30px;
            transform-style: preserve-3d;
            perspective: 800px;
        }

        /* Single Letter 3D Rotation Animation */
        .char-3d {
            display: inline-block;
            background: linear-gradient(180deg, #FFFFFF 0%, #FFE57F 35%, #D4AF37 70%, #996B00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            
            /* Out-of-Screen 3D Depth Shadows */
            text-shadow: 
                0 1px 0 #c49a22,
                0 2px 0 #ab8418,
                0 3px 0 #8f6c0f,
                0 4px 0 #735407,
                0 12px 25px rgba(0, 0, 0, 0.9),
                0 0 20px rgba(255, 215, 0, 0.8);

            animation: rotateIn3D 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            transform-origin: center center;
        }

        @keyframes rotateIn3D {
            0% {
                opacity: 0;
                transform: translateZ(-200px) rotateY(-180deg) rotateX(90deg) scale(0.2);
                filter: blur(10px);
            }
            100% {
                opacity: 1;
                transform: translateZ(80px) rotateY(0deg) rotateX(0deg) scale(1.1);
                filter: blur(0px);
            }
        }

        .author {
            font-size: 22px;
            font-weight: 900;
            color: #00ff88;
            transform: translateZ(60px);
            text-shadow: 
                0 0 10px #00ff88,
                0 0 25px #00ff88,
                0 5px 15px rgba(0,0,0,0.9);
            letter-spacing: 5px;
            text-transform: uppercase;
        }

        .sparkle {
            position: absolute;
            pointer-events: none;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #FFE57F;
            z-index: 99;
            box-shadow: 0 0 15px #ffd700;
            animation: burst 0.6s ease-out forwards;
        }

        @keyframes burst {
            0% { opacity: 1; transform: translate(0, 0) scale(1.8); }
            100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(0.2); }
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

    <!-- Audio Source -->
    <audio id="bgMusic" loop preload="auto">
        <source src="/audio" type="audio/mpeg">
    </audio>

    <script>
        const bgAudio = document.getElementById('bgMusic');
        let isMusicPlaying = false;

        function handleScreenTap(e) {
            // Gold Sparkles Burst
            for (let k = 0; k < 20; k++) {
                const sparkle = document.createElement('div');
                sparkle.className = 'sparkle';
                sparkle.style.left = e.clientX + 'px';
                sparkle.style.top = e.clientY + 'px';
                const angle = Math.random() * Math.PI * 2;
                const dist = Math.random() * 160 + 40;
                sparkle.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
                sparkle.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
                document.body.appendChild(sparkle);
                setTimeout(() => sparkle.remove(), 600);
            }

            // Audio Toggle
            if (isMusicPlaying) {
                bgAudio.pause();
                isMusicPlaying = false;
            } else {
                bgAudio.play().then(() => isMusicPlaying = true).catch(e => console.log("Touch needed for audio"));
            }
        }

        // Fast Money Rain
        const canvas = document.getElementById('moneyCanvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();

        const symbols = ['$', '₹', '€', '£', '¥', '💰', '💵', '💎'];
        const particles = Array.from({length: 85}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 22 + 16,
            speedY: Math.random() * 9.0 + 5.5,
            symbol: symbols[Math.floor(Math.random() * symbols.length)]
        }));

        function drawParticles() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => {
                ctx.font = `${p.size}px Arial`;
                ctx.fillStyle = 'rgba(212, 175, 55, 0.85)';
                ctx.shadowBlur = 12;
                ctx.shadowColor = '#D4AF37';
                ctx.fillText(p.symbol, p.x, p.y);
                p.y += p.speedY;
                if (p.y > canvas.height) { p.y = -30; p.x = Math.random() * canvas.width; }
            });
            requestAnimationFrame(drawParticles);
        }
        drawParticles();

        // 3D Rotating Letter-by-Letter Typing Effect
        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        
        const quoteContainer = document.getElementById('quoteText');
        const authorContainer = document.getElementById('authorText');

        let charIndex = 0;
        let authorIndex = 0;

        function type3DQuote() {
            if (charIndex < q.length) {
                const char = q[charIndex];
                if (char === '\\n') {
                    quoteContainer.appendChild(document.createElement('br'));
                } else {
                    const span = document.createElement('span');
                    span.className = 'char-3d';
                    span.innerHTML = char === ' ' ? '&nbsp;' : char;
                    quoteContainer.appendChild(span);
                }
                charIndex++;
                setTimeout(type3DQuote, 50);
            } else if (authorIndex < a.length) {
                const char = a[authorIndex];
                const span = document.createElement('span');
                span.style.display = 'inline-block';
                span.innerHTML = char === ' ' ? '&nbsp;' : char;
                authorContainer.appendChild(span);
                authorIndex++;
                setTimeout(type3DQuote, 70);
            }
        }

        setTimeout(type3DQuote, 300);

        // 3D Parallax Card Motion
        const card = document.getElementById('card3d');
        window.addEventListener('mousemove', (e) => {
            const x = (window.innerWidth / 2 - e.clientX) / 18;
            const y = (window.innerHeight / 2 - e.clientY) / 18;
            card.style.transform = `rotateY(${-x}deg) rotateX(${y}deg)`;
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
