from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello(): return "Works"
if __name__ == '__main__':
    print("Starting minimal...")
    app.run(port=5001)
