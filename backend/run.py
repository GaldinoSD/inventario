from app import create_app

app = create_app()

if __name__ == "__main__":
    # Escuta em todas as interfaces da máquina (LAN/Wi-Fi)
    app.run(host="0.0.0.0", port=5000, debug=True)
