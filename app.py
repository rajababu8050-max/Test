<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji Quotes</title>
    <style>
        /* CSS Styling */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: #0b0c10;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            position: relative;
        }

        #starCanvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }

        .card {
            position: relative;
            z-index: 2;
            background: rgba(15, 12, 32, 0.85);
            border: 3px solid #ffd700;
            box-shadow: 0 0 30px #ffd700, inset 0 0 15px rgba(255, 215, 0, 0.3);
            padding: 50px 40px;
            border-radius: 20px;
            text-align: center;
            max-width: 600px;
            width: 90%;
            backdrop-filter: blur(8px);
        }

        .quote {
            font-size: 28px;
            font-weight: 800;
            color: #ffd700;
            text-shadow: 0 0 15px #ffd700;
            margin-bottom: 30px;
            line-height: 1.4;
        }

        .author {
            font-size: 20px;
            font-weight: 600;
            color: #66fcf1;
            text-shadow: 0 0 10px #66fcf1;
            letter-spacing: 3px;
            text-transform: uppercase;
        }
    </style>
</head>
<body>

    <canvas id="starCanvas"></canvas>

    <div class="card">
        <div class="quote" id="quoteText"></div>
        <div class="author" id="authorText"></div>
    </div>

    <script>
        // Star Background
        const canvas = document.getElementById('starCanvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();

        const stars = Array.from({length: 100}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            r: Math.random() * 2 + 0.5
        }));

        function draw() {
            ctx.clearRect(0,0, canvas.width, canvas.height);
            ctx.fillStyle = "white";
            stars.forEach(s => { ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI*2); ctx.fill(); });
            requestAnimationFrame(draw);
        }
        draw();

        // Text Animation
        const q = "MONEY IS EVERYTHING,\nIF U HARD WORKING, U DESERVE.";
        const a = "— BY MAUSA JI";
        let i = 0, j = 0;

        function type() {
            if(i < q.length) {
                document.getElementById('quoteText').innerHTML += q[i] === '\n' ? '<br>' : q[i];
                i++; setTimeout(type, 60);
            } else if(j < a.length) {
                document.getElementById('authorText').innerHTML += a[j];
                j++; setTimeout(type, 80);
            }
        }
        type();
    </script>
</body>
</html>
