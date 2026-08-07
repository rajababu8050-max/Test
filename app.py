from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji - Cinematic Money Mindset</title>
    <!-- Three.js Library for Cinematic 3D Graphics -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #020503;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Roboto, Helvetica, sans-serif;
            overflow: hidden;
            position: relative;
            perspective: 1000px;
        }

        #webgl-bg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* Top Wealth Bar */
        .wealth-counter {
            position: absolute;
            top: 20px;
            z-index: 10;
            font-size: 18px;
            font-weight: 900;
            color: #ffd700;
            background: rgba(0, 20, 10, 0.6);
            padding: 10px 25px;
            border-radius: 50px;
            border: 1px solid rgba(255, 215, 0, 0.6);
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.3);
            letter-spacing: 2px;
            backdrop-filter: blur(10px);
        }

        /* Hologram Glass Card */
        .card {
            position: relative;
            z-index: 2;
            background: rgba(5, 15, 10, 0.65);
            border: 1px solid rgba(0, 255, 136, 0.5);
            box-shadow: 0 0 50px rgba(0, 255, 136, 0.25), inset 0 0 30px rgba(255, 215, 0, 0.15);
            padding: 50px 35px;
            border-radius: 20px;
            text-align: center;
            max-width: 650px;
            width: 90%;
            backdrop-filter: blur(16px);
            transform-style: preserve-3d;
            transition: transform 0.1s ease-out;
        }

        .icon-header {
            font-size: 50px;
            margin-bottom: 20px;
            filter: drop-shadow(0 0 15px #ffd700);
            animation: floatIcon 3s ease-in-out infinite;
        }

        @keyframes floatIcon {
            0%, 100% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-8px) scale(1.05); }
        }

        .quote {
            font-size: 26px;
            font-weight: 900;
            background: linear-gradient(135deg, #fff 0%, #ffd700 50%, #00ff88 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 12px rgba(255, 215, 0, 0.4));
            margin-bottom: 20px;
            line-height: 1.4;
            min-height: 75px;
        }

        .author {
            font-size: 18px;
            font-weight: 800;
            color: #00ff88;
            text-shadow: 0 0 15px #00ff88;
            letter-spacing: 4px;
            text-transform: uppercase;
        }
    </style>
</head>
<body>

    <div class="wealth-counter">NET WORTH: <span id="counter">$1,000,000</span></div>

    <!-- WebGL Background Canvas -->
    <canvas id="webgl-bg"></canvas>

    <div class="card" id="tiltCard">
        <div class="icon-header">🤑 💰 💵</div>
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // 1. Three.js Cinematic 3D Graphics Setup
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('webgl-bg'), antialias: true });
        
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0xffd700, 2, 100);
        pointLight.position.set(0, 0, 10);
        scene.add(pointLight);

        // 3D Gold Coins Creation
        const coins = [];
        const coinGeometry = new THREE.CylinderGeometry(0.6, 0.6, 0.1, 32);
        const coinMaterial = new THREE.MeshStandardMaterial({
            color: 0xffd700,
            metalness: 0.9,
            roughness: 0.1
        });

        for (let k = 0; k < 70; k++) {
            const coin = new THREE.Mesh(coinGeometry, coinMaterial);
            coin.position.set(
                (Math.random() - 0.5) * 30,
                (Math.random() - 0.5) * 30,
                (Math.random() - 0.5) * 20
            );
            coin.rotation.x = Math.random() * Math.PI;
            coin.rotation.y = Math.random() * Math.PI;
            coin.rotSpeedX = (Math.random() - 0.5) * 0.03;
            coin.rotSpeedY = (Math.random() - 0.5) * 0.03;
            coin.fallSpeed = Math.random() * 0.05 + 0.02;
            coins.push(coin);
            scene.add(coin);
        }

        camera.position.z = 12;

        // Render Loop
        function animate() {
            requestAnimationFrame(animate);

            coins.forEach(coin => {
                coin.rotation.x += coin.rotSpeedX;
                coin.rotation.y += coin.rotSpeedY;
                coin.position.y -= coin.fallSpeed;

                if (coin.position.y < -15) {
                    coin.position.y = 15;
                    coin.position.x = (Math.random() - 0.5) * 30;
                }
            });

            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // 2. Typing Effect
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

        // 3. Live Wealth Counter
        let count = 1000000;
        setInterval(() => {
            count += Math.floor(Math.random() * 500) + 100;
            document.getElementById('counter').innerText = '$' + count.toLocaleString();
        }, 80);

        // 4. Smooth 3D Card Tilt Effect
        const card = document.getElementById('tiltCard');
        window.addEventListener('mousemove', (e) => {
            const x = (window.innerWidth / 2 - e.clientX) / 25;
            const y = (window.innerHeight / 2 - e.clientY) / 25;
            card.style.transform = `rotateY(${-x}deg) rotateX(${y}deg)`;
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_CONTENT
