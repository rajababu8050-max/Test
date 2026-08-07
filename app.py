from flask import Flask, render_template_string

app = Flask(__name__)

HTML_CODE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mausa Ji Quotes</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0b0c10;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
        }
        .card {
            border: 3px solid #ffd700;
            box-shadow: 0 0 25px #ffd700, inset 0 0 15px #ffd700;
            padding: 50px 30px;
            border-radius: 15px;
            text-align: center;
            background: rgba(15, 12, 32, 0.85);
            max-width: 650px;
            width: 90%;
        }
        .quote {
            font-size: 26px;
            font-weight: bold;
            color: #ffd700;
            text-shadow: 0 0 10px #ffd700;
            margin-bottom: 25px;
            line-height: 1.4;
        }
        .author {
            font-size: 20px;
            font-weight: 600;
            color: #66fcf1;
            text-shadow: 0 0 8px #66fcf1;
            letter-spacing: 2px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="quote">"MONEY IS EVERYTHING,<br>IF U HARD WORKING, U DESERVE."</div>
        <div class="author">— BY MAUSA JI</div>
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_CODE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
