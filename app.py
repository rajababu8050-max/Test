from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - Realistic Money Mindset Pro</title>
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
        }

        .spotlight {
            position: absolute;
            width: 700px;
            height: 700px;
            background: radial-gradient(circle, rgba(212, 175, 55, 0.15) 0%, rgba(0, 255, 136, 0.08) 40%, transparent 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
            pointer-events: none;
            filter: blur(50px);
            animation: pulseLight 6s ease-in-out infinite alternate;
        }

        @keyframes pulseLight {
            0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.6; }
            100% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
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
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.07), rgba(0, 0, 0, 0.4));
            border: 1px solid rgba(212, 175, 55, 0.5);
            border-top: 1px solid rgba(255, 255, 255, 0.3);
            border-left: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 
                0 30px 60px rgba(0, 0, 0, 0.8),
                0 0 40px rgba(212, 175, 55, 0.2),
                inset 0 0 20px rgba(255, 255, 255, 0.05);
            padding: 50px 35px;
            border-radius: 24px;
            text-align: center;
            max-width: 620px;
            width: 90%;
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            transform-style: preserve-3d;
            transition: transform 0.2s cubic-bezier(0.25, 1, 0.5, 1);
        }

        .icon-header {
            font-size: 55px;
            margin-bottom: 20px;
            filter: drop-shadow(0 10px 15px rgba(0,0,0,0.5));
            animation: floatIcon 3.5s ease-in-out infinite;
        }

        @keyframes floatIcon {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
        }

        .quote {
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(180deg, #FFFFFF 0%, #FFE57F 40%, #D4AF37 70%, #AA7C11 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.6));
            margin-bottom: 25px;
            line-height: 1.45;
            min-height: 75px;
            letter-spacing: 0.5px;
        }

        .author {
            font-size: 19px;
            font-weight: 800;
            color: #50E3C2;
            text-shadow: 0 0 12px rgba(80, 227, 194, 0.6);
            letter-spacing: 4px;
            text-transform: uppercase;
        }

        /* Gold Sparkle Explosion Particle */
        .sparkle {
            position: absolute;
            pointer-events: none;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #FFE57F;
            box-shadow: 0 0 10px #D4AF37, 0 0 20px #FFF;
            z-index: 99;
            animation: burst 0.8s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
        }

        @keyframes burst {
            0% { opacity: 1; transform: translate(0, 0) scale(1); }
            100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(0.2); }
        }
    </style>
</head>
<body onclick="triggerEffects(event)">

    <div class="spotlight"></div>
    <canvas id="moneyCanvas"></canvas>

    <div class="card" id="card3d">
        <div class="icon-header">💎 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // Web Audio API for Crisp Cash Register / Coin Sound Effect
        let audioCtx;
        function playCoinSound() {
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            
            const now = audioCtx.currentTime;
            
            // High metallic chime
            const osc1 = audioCtx.createOscillator();
            const gain1 = audioCtx.createGain();
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(2400, now);
            osc1.frequency.exponentialRampToValueAtTime(1200, now + 0.15);
            gain1.gain.setValueAtTime(0.15, now);
            gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
            
            osc1.connect(gain1);
            gain1.connect(audioCtx.destination);
            osc1.start(now);
            osc1.stop(now + 0.15);

            // Secondary resonance chime
            const osc2 = audioCtx.createOscillator();
            const gain2 = audioCtx.createGain();
            osc2.type = 'triangle';
            osc2.frequency.setValueAtTime(3200, now + 0.05);
            osc2.frequency.exponentialRampToValueAtTime(1600, now + 0.2);
            gain2.gain.setValueAtTime(0.1, now + 0.05);
            gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

            osc2.connect(gain2);
            gain2.connect(audioCtx.destination);
            osc2.start(now + 0.05);
            osc2.stop(now + 0.2);
        }

        // Tap Sparkle Particles & Sound Trigger
        function triggerEffects(e) {
            playCoinSound();

            for (let k = 0; k < 18; k++) {
                const sparkle = document.createElement('div');
                sparkle.className = 'sparkle';
                sparkle.style.left = e.clientX + 'px';
                sparkle.style.top = e.clientY + 'px';

                const angle = Math.random() * Math.PI * 2;
                const dist = Math.random() * 120 + 30;
                const dx = Math.cos(angle) * dist + 'px';
                const dy = Math.sin(angle) * dist + 'px';

                sparkle.style.setProperty('--dx', dx);
                sparkle.style.setProperty('--dy', dy);

                document.body.appendChild(sparkle);
                setTimeout(() => sparkle.remove(), 800);
            }
        }

        // Realistic Background Rain Animation
        const canvas = document.getElementById('moneyCanvas');
        const ctx = canvas.getContext('2d');

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        window.onresize = resize;
        resize();

        const symbols = ['$', '₹', '€', '£', '¥', '💰', '💵', '💎'];
        const particles = Array.from({length: 70}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 18 + 14,
            speedY: Math.random() * 2.5 + 1.2,
            speedX: (Math.random() - 0.5) * 0.5,
            rotation: Math.random() * 360,
            rotSpeed: (Math.random() - 0.5) * 2,
            opacity: Math.random() * 0.7 + 0.3,
            symbol: symbols[Math.floor(Math.random() * symbols.length)]
        }));

        function drawParticles() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            particles.forEach(p => {
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                
                ctx.font = `${p.size}px 'Segoe UI', sans-serif`;
                ctx.fillStyle = `rgba(212, 175, 55, ${p.opacity})`;
                ctx.shadowBlur = 12;
                ctx.shadowColor = 'rgba(212, 175, 55, 0.5)';
                ctx.fillText(p.symbol, 0, 0);
                
                ctx.restore();

                p.y += p.speedY;
                p.x += p.speedX;
                p.rotation += p.rotSpeed;

                if (p.y > canvas.height + 30) {
                    p.y = -30;
                    p.x = Math.random() * canvas.width;
                }
            });

            requestAnimationFrame(drawParticles);
        }
        drawParticles();

        // Typewriter Logic
        const q = "MONEY IS EVERYTHING,\\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\\n' ? '<br>' : q[i];
                i++; setTimeout(type, 45);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; 
                setTimeout(type, 65);
                if (j === a.length) {
                    setTimeout(playCoinSound, 200);
                }
            }
        }
        setTimeout(type, 300);

        // Smooth Parallax Card Shift
        const card = document.getElementById('card3d');
        window.addEventListener('mousemove', (e) => {
            const xAxis = (window.innerWidth / 2 - e.clientX) / 30;
            const yAxis = (window.innerHeight / 2 - e.clientY) / 30;
            card.style.transform = `rotateY(${xAxis}deg) rotateX(${yAxis}deg)`;
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT
